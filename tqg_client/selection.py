"""Selection log: trial count N, book legs k, and Deflated Sharpe Ratio.

Harness-owned. Agents must not treat chat memory as a substitute for
``artifacts/selection.json``.

DSR follows Bailey & López de Prado (2014). It uses N (and family N). It does
not adjust for k. DSR is not expected out-of-sample Sharpe.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .lab_index import params_fingerprint
from .run_state import load_strategy_spec

SCHEMA_VERSION = 1
SELECTION_RELPATH = "artifacts/selection.json"
RETURNS_IS_RELPATH = "artifacts/returns_is.json"
DSR_NOTE = (
    "DSR is the probability the observed IS Sharpe exceeds the expected maximum "
    "under N trials (Bailey & López de Prado 2014). It is not expected OOS Sharpe. "
    "k is unadjusted."
)
EULER_GAMMA = 0.5772156649015329

_BREAKDOWN_KEYS = (
    "baseline_evals",
    "psa_cells",
    "cea_cells",
    "mc_sims",
    "related_run_priors",
    "manual_declared",
    "inline_grid",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def empty_selection() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "n_trials": 0,
        "n_trials_family": 0,
        "n_legs": 1,
        "n_adaptive_rounds": 0,
        "breakdown": {k: 0 for k in _BREAKDOWN_KEYS},
        "legs": [],
        "events": [],
        "recorded_grids": [],
        "last_fingerprint": None,
        "dsr": None,
        "null_baseline": None,
        "novy_marx": None,
        "cs_shuffle": None,
        "manufacturing": None,
        "crowding": None,
    }


def selection_path(run_root: Path) -> Path:
    return Path(run_root) / SELECTION_RELPATH


def load_selection(run_root: Path) -> dict[str, Any]:
    data = _read_json(selection_path(run_root))
    if not data:
        return empty_selection()
    base = empty_selection()
    base.update(data)
    breakdown = dict(base.get("breakdown") or {})
    for key in _BREAKDOWN_KEYS:
        breakdown.setdefault(key, 0)
    base["breakdown"] = breakdown
    base.setdefault("events", [])
    base.setdefault("recorded_grids", [])
    base.setdefault("legs", [])
    return base


def save_selection(run_root: Path, data: dict[str, Any]) -> Path:
    path = selection_path(run_root)
    _write_json(path, data)
    return path


def seed_selection(run_root: Path) -> Path:
    path = selection_path(run_root)
    if path.is_file():
        return path
    return save_selection(run_root, empty_selection())


# --- Normal CDF / PPF (Acklam) so we do not require scipy --------------------

def _norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-float(x) / math.sqrt(2.0))


def _norm_ppf(p: float) -> float:
    """Acklam's inverse normal CDF, relative error ~1e-9."""
    if p <= 0.0:
        return float("-inf")
    if p >= 1.0:
        return float("inf")
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577459334971e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464858e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]
    plow = 0.02425
    phigh = 1.0 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    )


def sharpe_from_returns(returns: pd.Series, annualization: float) -> float:
    r = pd.Series(returns).dropna().astype(float)
    if len(r) < 2:
        return 0.0
    vol = float(r.std(ddof=1))
    if vol == 0.0 or not np.isfinite(vol):
        return 0.0
    return float(np.sqrt(float(annualization)) * r.mean() / vol)


def probabilistic_sharpe(
    sr_period: float,
    sr_star_period: float,
    n_obs: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Bailey & López de Prado PSR. ``sr_*`` are *per-period* Sharpes."""
    n = int(n_obs)
    if n < 2:
        return float("nan")
    sr = float(sr_period)
    g3 = float(skew)
    g4 = float(kurtosis)
    inside = 1.0 - g3 * sr + ((g4 - 1.0) / 4.0) * sr * sr
    if inside <= 0.0:
        return float("nan")
    z = (sr - float(sr_star_period)) * math.sqrt(n - 1) / math.sqrt(inside)
    return float(_norm_cdf(z))


def expected_max_sharpe(
    n_trials: int,
    n_obs: int,
    sr_period: float,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """E[max SR] under N independent trials (per-period). N=1 → 0."""
    n = max(1, int(n_trials))
    if n <= 1:
        return 0.0
    n_obs = int(n_obs)
    if n_obs < 2:
        return 0.0
    sr = float(sr_period)
    g3 = float(skew)
    g4 = float(kurtosis)
    inside = 1.0 - g3 * sr + ((g4 - 1.0) / 4.0) * sr * sr
    var = inside / (n_obs - 1)
    if var <= 0.0:
        return 0.0
    # Φ^{-1}(1-1/N) and Φ^{-1}(1-1/(N e))
    p1 = 1.0 - 1.0 / n
    p2 = 1.0 - 1.0 / (n * math.e)
    z = (1.0 - EULER_GAMMA) * _norm_ppf(p1) + EULER_GAMMA * _norm_ppf(p2)
    return float(math.sqrt(var) * z)


def deflated_sharpe(
    returns_is: pd.Series | np.ndarray | None,
    *,
    sharpe_is: float | None = None,
    n_trials: int,
    annualization: float = 365,
    n_obs: int | None = None,
    skew: float | None = None,
    kurtosis: float | None = None,
) -> dict[str, Any]:
    """Deflated Sharpe Ratio. ``sharpe_is`` is the *annualized* IS Sharpe."""
    n_trials_used = max(1, int(n_trials))
    r = None
    if returns_is is not None:
        r = pd.Series(returns_is).dropna().astype(float)
        if r.empty:
            r = None
    if r is not None:
        n_obs = int(len(r)) if n_obs is None else int(n_obs)
        if skew is None:
            skew = float(r.skew()) if n_obs >= 3 else 0.0
        if kurtosis is None:
            # pandas .kurt() is Fisher excess; Bailey uses Pearson kurtosis
            kurtosis = float(r.kurtosis()) + 3.0 if n_obs >= 4 else 3.0
        if sharpe_is is None:
            sharpe_is = sharpe_from_returns(r, annualization)
    if n_obs is None or n_obs < 2:
        return {
            "method": "bailey_lopezdeprado_2014",
            "error": "missing_is_returns",
            "n_trials_used": n_trials_used,
            "note": DSR_NOTE,
        }
    ann = float(annualization) if annualization and annualization > 0 else 1.0
    sr_ann = 0.0 if sharpe_is is None else float(sharpe_is)
    sr_period = sr_ann / math.sqrt(ann)
    g3 = 0.0 if skew is None or not np.isfinite(skew) else float(skew)
    g4 = 3.0 if kurtosis is None or not np.isfinite(kurtosis) else float(kurtosis)
    sr0_period = expected_max_sharpe(n_trials_used, n_obs, sr_period, g3, g4)
    psr0 = probabilistic_sharpe(sr_period, 0.0, n_obs, g3, g4)
    dsr = probabilistic_sharpe(sr_period, sr0_period, n_obs, g3, g4)
    return {
        "method": "bailey_lopezdeprado_2014",
        "sharpe_is": sr_ann,
        "n_obs": int(n_obs),
        "n_trials_used": n_trials_used,
        "annualization": ann,
        "skew": g3,
        "excess_kurtosis": g4 - 3.0,
        "sr0": sr0_period * math.sqrt(ann),
        "psr": psr0,
        "dsr": dsr,
        "note": DSR_NOTE,
    }


def count_legs(strategy_spec: dict[str, Any] | None) -> tuple[int, list[dict[str, Any]]]:
    spec = strategy_spec or {}
    sel = spec.get("selection") if isinstance(spec.get("selection"), dict) else {}
    signals = spec.get("signals")
    legs: list[dict[str, Any]] = []
    if isinstance(signals, list) and signals:
        raw: list[tuple[str, float]] = []
        for i, item in enumerate(signals):
            if isinstance(item, str):
                raw.append((item, 1.0))
            elif isinstance(item, dict):
                weight = item.get("weight", 1.0)
                try:
                    w = float(weight)
                except (TypeError, ValueError):
                    w = 1.0
                if w == 0.0:
                    continue
                ident = str(item.get("id") or item.get("name") or f"leg_{i}")
                raw.append((ident, w))
        total = sum(abs(w) for _, w in raw) or 1.0
        legs = [
            {"id": ident, "weight": w / total, "source": "strategy_spec.signals"}
            for ident, w in raw
        ]
        if legs:
            return len(legs), legs

    weights = spec.get("ensemble_weights")
    if isinstance(weights, dict):
        items = []
        for key, val in weights.items():
            try:
                w = float(val)
            except (TypeError, ValueError):
                continue
            if w == 0.0:
                continue
            items.append((str(key), w))
        total = sum(abs(w) for _, w in items) or 1.0
        legs = [
            {"id": ident, "weight": w / total, "source": "ensemble_weights"}
            for ident, w in items
        ]
        if legs:
            return len(legs), legs
    if isinstance(weights, list):
        items = []
        for i, val in enumerate(weights):
            try:
                w = float(val)
            except (TypeError, ValueError):
                continue
            if w == 0.0:
                continue
            items.append((f"leg_{i}", w))
        total = sum(abs(w) for _, w in items) or 1.0
        legs = [
            {"id": ident, "weight": w / total, "source": "ensemble_weights"}
            for ident, w in items
        ]
        if legs:
            return len(legs), legs

    ranking = spec.get("ranking") if isinstance(spec.get("ranking"), dict) else {}
    sub = ranking.get("sub_scores")
    if isinstance(sub, list) and sub:
        n = len(sub)
        legs = [
            {
                "id": str(item.get("id") or item.get("name") or item) if isinstance(item, dict) else str(item),
                "weight": 1.0 / n,
                "source": "ranking.sub_scores",
            }
            for item in sub
        ]
        return n, legs

    declared = sel.get("n_legs")
    if isinstance(declared, int) and declared >= 1:
        return declared, [{"id": f"leg_{i}", "weight": 1.0 / declared, "source": "selection.n_legs"} for i in range(declared)]

    return 1, []


def persist_is_returns(run_root: Path, returns: pd.Series) -> Path:
    r = pd.Series(returns).dropna()
    datetime_index = isinstance(r.index, pd.DatetimeIndex)
    if datetime_index:
        index = [i.isoformat() if hasattr(i, "isoformat") else str(i) for i in r.index]
    else:
        index = [str(i) for i in r.index]
    payload = {
        "index": index,
        "index_kind": "datetime" if datetime_index else "raw",
        "values": [None if (v is None or (isinstance(v, float) and not np.isfinite(v))) else float(v) for v in r.tolist()],
    }
    path = Path(run_root) / RETURNS_IS_RELPATH
    _write_json(path, payload)
    return path


def load_is_returns(run_root: Path) -> pd.Series | None:
    raw = _read_json(Path(run_root) / RETURNS_IS_RELPATH)
    if not raw:
        return None
    idx = raw.get("index") or []
    vals = raw.get("values") or []
    if not idx or len(idx) != len(vals):
        return None
    try:
        index = pd.to_datetime(idx, utc=True) if raw.get("index_kind") == "datetime" else pd.Index(idx)
    except (ValueError, TypeError):
        index = pd.Index(idx)
    return pd.Series(vals, index=index, dtype=float)


def record_event(
    run_root: Path,
    *,
    kind: str,
    n_increment: int = 0,
    script: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append an event and bump the matching breakdown counter."""
    data = load_selection(run_root)
    inc = max(0, int(n_increment))
    breakdown = data.setdefault("breakdown", {k: 0 for k in _BREAKDOWN_KEYS})
    kind_to_key = {
        "baseline_eval": "baseline_evals",
        "psa_grid": "psa_cells",
        "cea_grid": "cea_cells",
        "mc_sims": "mc_sims",
        "inline_grid": "inline_grid",
        "manual_declared": "manual_declared",
        "replay": None,
    }
    key = kind_to_key.get(kind)
    if key:
        breakdown[key] = int(breakdown.get(key) or 0) + inc
    if kind != "mc_sims" and kind != "replay":
        data["n_trials"] = int(data.get("n_trials") or 0) + inc
    event = {
        "at": _utc_now(),
        "kind": kind,
        "script": script,
        "n_increment": inc,
    }
    if extra:
        event.update(extra)
    events = list(data.get("events") or [])
    events.append(event)
    data["events"] = events
    save_selection(run_root, data)
    return data


def record_trials(
    run_root: Path,
    n: int,
    *,
    kind: str = "inline_grid",
    script: str | None = None,
    **meta: Any,
) -> dict[str, Any]:
    """Escape hatch for in-script candidate loops the harness cannot see."""
    return record_event(run_root, kind=kind, n_increment=int(n), script=script, extra=meta or None)


def _product_len(grid: Any) -> int | None:
    if isinstance(grid, dict) and grid:
        n = 1
        for val in grid.values():
            if isinstance(val, (list, tuple)):
                n *= max(len(val), 1)
            else:
                return None
        return n
    if isinstance(grid, list) and grid:
        return len(grid)
    return None


def detect_grid_from_obj(obj: Any, *, path: str = "") -> tuple[str, int] | None:
    """Return (kind, n) for a PSA/CEA/MC artifact blob."""
    if not isinstance(obj, dict):
        return None
    inner = obj
    for wrap in ("parameter_sensitivity", "psa", "cost_effect", "monte_carlo"):
        nested = obj.get(wrap)
        if isinstance(nested, dict):
            inner = nested
            break
    if "grid_cells" in inner:
        try:
            n = int(inner["grid_cells"])
        except (TypeError, ValueError):
            n = 0
        if n > 0:
            return "psa_grid", n
    if "n_permutations" in inner:
        try:
            n = int(inner["n_permutations"])
        except (TypeError, ValueError):
            n = 0
        if n > 0:
            return "psa_grid", n
    prod = _product_len(inner.get("parameter_grid") or inner.get("grid"))
    if prod and prod > 1:
        return "psa_grid", prod
    for key in ("cost_levels", "tested_costs", "cost_grid"):
        val = inner.get(key)
        if isinstance(val, list) and len(val) > 0:
            return "cea_grid", len(val)
    if "n_simulations" in inner:
        try:
            n = int(inner["n_simulations"])
        except (TypeError, ValueError):
            n = 0
        if n > 0:
            return "mc_sims", n
    name = path.lower()
    if "psa" in name or "parameter_sensitivity" in name:
        prod = _product_len(inner.get("rows") or inner.get("results"))
        if prod and prod > 1:
            return "psa_grid", prod
    return None


def _artifact_signature(path: Path, n: int) -> str:
    try:
        st = path.stat()
        return f"{st.st_mtime_ns}:{st.st_size}:{n}"
    except OSError:
        return f"missing:{n}"


def scan_grid_artifacts(run_root: Path) -> list[tuple[str, int, str, str]]:
    """[(kind, n, relpath, signature), ...] for newly seen robustness grids."""
    art = Path(run_root) / "artifacts"
    if not art.is_dir():
        return []
    found: list[tuple[str, int, str, str]] = []
    for path in sorted(art.glob("*.json")):
        if path.name in {"metrics.json", "selection.json", "returns_is.json"}:
            continue
        obj = _read_json(path)
        if not obj:
            continue
        detected = detect_grid_from_obj(obj, path=path.name)
        if not detected:
            continue
        kind, n = detected
        rel = f"artifacts/{path.name}"
        found.append((kind, n, rel, _artifact_signature(path, n)))
    return found


def _flow_rounds(run_root: Path) -> int:
    flow = _read_json(Path(run_root) / "flow.json") or {}
    turns = flow.get("turns") or []
    return len(turns) if isinstance(turns, list) else 0


def _spec_fingerprint(run_root: Path, spec: dict[str, Any] | None) -> str:
    spec = spec or {}
    params = spec.get("params") if isinstance(spec.get("params"), dict) else {}
    return params_fingerprint(
        workflow=spec.get("workflow"),
        strategy_type=spec.get("strategy_type"),
        symbol=spec.get("symbol"),
        interval=spec.get("interval"),
        params=params,
    )


def family_n(
    run_id: str,
    run_root: Path,
    n_trials: int,
    *,
    runs_dir: Path | None = None,
) -> tuple[int, int]:
    """Return (n_trials_family, related_run_priors)."""
    run_json = _read_json(Path(run_root) / "run.json") or {}
    related = list(run_json.get("related_runs") or [])
    spec = load_strategy_spec(run_root) or {}
    symbol = str(run_json.get("symbol") or spec.get("symbol") or "")
    strategy_type = str(run_json.get("strategy_type") or spec.get("strategy_type") or "")
    base = Path(runs_dir) if runs_dir is not None else Path(run_root).parent
    seen: set[str] = set()
    priors = 0
    for other_id in related:
        if not other_id or other_id == run_id or other_id in seen:
            continue
        seen.add(str(other_id))
        other_root = base / str(other_id)
        other_spec = load_strategy_spec(other_root) or {}
        other_json = _read_json(other_root / "run.json") or {}
        other_symbol = str(other_json.get("symbol") or other_spec.get("symbol") or "")
        other_type = str(other_json.get("strategy_type") or other_spec.get("strategy_type") or "")
        if symbol and other_symbol and symbol.upper() != other_symbol.upper():
            continue
        if strategy_type and other_type and strategy_type != other_type:
            continue
        other_sel = load_selection(other_root)
        priors += int(other_sel.get("n_trials") or 0)
    return int(n_trials) + int(priors), int(priors)


def _extract_pf_returns(pf: Any) -> pd.Series | None:
    if pf is None:
        return None
    try:
        rets = pf.returns()
    except Exception:
        return None
    if isinstance(rets, pd.DataFrame):
        if rets.empty:
            return None
        rets = rets.iloc[:, 0]
    if not isinstance(rets, pd.Series):
        return None
    return rets.dropna().astype(float)


def _extract_pf_position(pf: Any) -> pd.Series | None:
    for name in ("asset", "assets", "shares"):
        attr = getattr(pf, name, None)
        if attr is None:
            continue
        try:
            val = attr() if callable(attr) else attr
        except Exception:
            continue
        if isinstance(val, pd.DataFrame):
            if val.empty:
                continue
            val = val.iloc[:, 0]
        if isinstance(val, pd.Series) and not val.empty:
            return val.astype(float)
    return None


def _slice_is(series: pd.Series, oos_start: str | None) -> pd.Series:
    if not oos_start:
        return series
    try:
        ts = pd.Timestamp(oos_start)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        idx = series.index
        if isinstance(idx, pd.DatetimeIndex):
            if idx.tz is None:
                series = series.copy()
                series.index = idx.tz_localize("UTC")
            return series.loc[series.index < ts]
    except Exception:
        return series
    return series


def _annualization(spec: dict[str, Any] | None, namespace: dict[str, Any] | None) -> float:
    if namespace and namespace.get("ann_factor"):
        try:
            return float(namespace["ann_factor"])
        except (TypeError, ValueError):
            pass
    spec = spec or {}
    for key in ("annualization", "ann_factor"):
        if spec.get(key):
            try:
                return float(spec[key])
            except (TypeError, ValueError):
                continue
    from .market_data import default_annualization

    return float(
        default_annualization(str(spec.get("symbol") or ""), asset_class=spec.get("asset_class"))
    )


def _metrics_sharpe_is(run_root: Path) -> float | None:
    metrics = _read_json(Path(run_root) / "artifacts" / "metrics.json") or {}
    block = metrics.get("in_sample") if isinstance(metrics.get("in_sample"), dict) else {}
    for key in ("Sharpe", "sharpe"):
        val = block.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val)
    return None


def patch_metrics_selection(run_root: Path, data: dict[str, Any]) -> None:
    path = Path(run_root) / "artifacts" / "metrics.json"
    metrics = _read_json(path) or {}
    dsr = data.get("dsr") if isinstance(data.get("dsr"), dict) else {}
    metrics["selection"] = {
        "n_trials": int(data.get("n_trials") or 0),
        "n_trials_family": int(data.get("n_trials_family") or 0),
        "n_legs": int(data.get("n_legs") or 1),
        "dsr": dsr.get("dsr") if dsr else None,
        "path": SELECTION_RELPATH,
    }
    _write_json(path, metrics)


def _classify_script(script: str | None, completed_step: str | None) -> str:
    name = (script or "").lower()
    step = (completed_step or "").lower()
    blob = f"{name} {step}"
    if any(tok in blob for tok in ("psa", "parameter_sensitivity")):
        return "psa"
    if any(tok in blob for tok in ("cea", "cost_effect", "cost_stress")):
        return "cea"
    if any(tok in blob for tok in ("monte", "reshuffle", "mc_")):
        return "mc"
    return "baseline"


def after_execution(
    run_root: Path,
    *,
    run_id: str,
    script: str | None = None,
    completed_step: str | None = None,
    namespace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update the selection log after a successful harness run."""
    namespace = namespace or {}
    spec = load_strategy_spec(run_root) or namespace.get("strategy_spec") or {}
    data = load_selection(run_root)
    fp = _spec_fingerprint(run_root, spec if isinstance(spec, dict) else None)
    class_ = _classify_script(script, completed_step)

    new_grids = scan_grid_artifacts(run_root)
    recorded = list(data.get("recorded_grids") or [])
    recorded_sigs = {str(item.get("signature")) for item in recorded if isinstance(item, dict)}
    saw_selection_grid = False
    for kind, n, rel, sig in new_grids:
        if sig in recorded_sigs:
            continue
        record_event(
            run_root,
            kind=kind,
            n_increment=n,
            script=script,
            extra={"path": rel, "grid_cells": n} if kind != "mc_sims" else {"path": rel, "n_simulations": n},
        )
        recorded.append({"path": rel, "signature": sig, "kind": kind, "n": n})
        recorded_sigs.add(sig)
        if kind in {"psa_grid", "cea_grid"}:
            saw_selection_grid = True
        data = load_selection(run_root)

    if class_ == "baseline" and not saw_selection_grid:
        last_fp = data.get("last_fingerprint")
        if last_fp and last_fp == fp and int(data.get("n_trials") or 0) > 0:
            record_event(run_root, kind="replay", n_increment=0, script=script, extra={"fingerprint": fp})
        else:
            record_event(run_root, kind="baseline_eval", n_increment=1, script=script, extra={"fingerprint": fp})
        data = load_selection(run_root)

    data["last_fingerprint"] = fp
    data["recorded_grids"] = recorded

    spec_sel = spec.get("selection") if isinstance(spec.get("selection"), dict) else {}
    declared = spec_sel.get("manual_declared_trials")
    already = int((data.get("breakdown") or {}).get("manual_declared") or 0)
    if isinstance(declared, int) and declared > already:
        record_event(
            run_root,
            kind="manual_declared",
            n_increment=declared - already,
            script=script,
        )
        data = load_selection(run_root)
        data["recorded_grids"] = recorded
        data["last_fingerprint"] = fp

    k, legs = count_legs(spec if isinstance(spec, dict) else None)
    data["n_legs"] = k
    data["legs"] = legs
    data["n_adaptive_rounds"] = _flow_rounds(run_root)
    fam, priors = family_n(run_id, run_root, int(data.get("n_trials") or 0))
    data["n_trials_family"] = fam
    data["breakdown"]["related_run_priors"] = priors

    oos = spec.get("oos_start_ts") if isinstance(spec, dict) else None
    pf = namespace.get("pf")
    rets = _extract_pf_returns(pf)
    if rets is not None:
        persist_is_returns(run_root, _slice_is(rets, oos))
    is_rets = load_is_returns(run_root)
    ann = _annualization(spec if isinstance(spec, dict) else None, namespace)
    sharpe_is = _metrics_sharpe_is(run_root)
    n_for_dsr = max(int(data.get("n_trials_family") or 0), int(data.get("n_trials") or 0), 1)
    if is_rets is not None and len(is_rets.dropna()) >= 2:
        data["dsr"] = deflated_sharpe(
            is_rets,
            sharpe_is=sharpe_is,
            n_trials=n_for_dsr,
            annualization=ann,
        )
    elif sharpe_is is not None:
        data["dsr"] = {
            "method": "bailey_lopezdeprado_2014",
            "sharpe_is": sharpe_is,
            "n_trials_used": n_for_dsr,
            "error": "missing_is_returns",
            "note": DSR_NOTE,
        }
    else:
        data["dsr"] = {
            "method": "bailey_lopezdeprado_2014",
            "n_trials_used": n_for_dsr,
            "error": "missing_is_returns",
            "note": DSR_NOTE,
        }

    if k > 1:
        from .novy_marx import novy_marx_note

        data["novy_marx"] = novy_marx_note(k=k)
    else:
        data["novy_marx"] = None

    close = namespace.get("close")
    pos = _extract_pf_position(pf)
    asset_rets = None
    if isinstance(close, pd.Series) and len(close) > 2:
        asset_rets = _slice_is(close.astype(float).pct_change(), oos)
    if is_rets is not None and (asset_rets is not None or pos is not None):
        from .null_baseline import random_entry_matched_hold

        if pos is not None and oos:
            pos = _slice_is(pos, oos)
        try:
            data["null_baseline"] = random_entry_matched_hold(
                asset_returns=asset_rets if asset_rets is not None else is_rets,
                position=pos,
                strategy_returns=is_rets,
                n_sims=200,
                seed=42,
                annualization=ann,
                strategy_sharpe_is=sharpe_is if sharpe_is is not None else (
                    sharpe_from_returns(is_rets, ann) if is_rets is not None else None
                ),
            )
        except Exception as exc:  # noqa: BLE001
            data["null_baseline"] = {"method": "random_entry_matched_hold", "error": str(exc)}

    save_selection(run_root, data)
    if (Path(run_root) / "artifacts" / "metrics.json").is_file():
        patch_metrics_selection(run_root, data)
    return data


def grandfather_stub(run_root: Path) -> dict[str, Any]:
    data = empty_selection()
    data["n_trials"] = 1
    data["n_trials_family"] = 1
    data["n_legs"] = 1
    data["grandfathered"] = True
    data["dsr"] = {
        "method": "bailey_lopezdeprado_2014",
        "error": "grandfathered_missing_log",
        "n_trials_used": 1,
        "note": DSR_NOTE,
    }
    data["events"] = [
        {
            "at": _utc_now(),
            "kind": "grandfathered",
            "script": None,
            "n_increment": 1,
            "note": "Synthesized because selection.json was missing at package time.",
        }
    ]
    save_selection(run_root, data)
    if (Path(run_root) / "artifacts" / "metrics.json").is_file():
        patch_metrics_selection(run_root, data)
    return data


def format_selection_block(data: dict[str, Any] | None) -> str:
    data = data or empty_selection()
    dsr = data.get("dsr") if isinstance(data.get("dsr"), dict) else {}
    dsr_v = dsr.get("dsr")
    dsr_s = f"{dsr_v:.2f}" if isinstance(dsr_v, (int, float)) else "n/a"
    null = data.get("null_baseline") if isinstance(data.get("null_baseline"), dict) else {}
    p95 = null.get("sharpe_is_p95")
    pct = null.get("strategy_is_percentile")
    null_s = ""
    if isinstance(p95, (int, float)):
        null_s = f"\nNull IS p95: {p95:.2f}"
        if isinstance(pct, (int, float)):
            null_s += f"  (strategy percentile {pct:.2f})"
    nm = data.get("novy_marx") if isinstance(data.get("novy_marx"), dict) else None
    nm_s = ""
    if nm:
        nm_s = f"\nNovy-Marx k-multiplier: {nm.get('combination_multiplier')}"
    return (
        f"N (this run / family): {data.get('n_trials')} / {data.get('n_trials_family')}\n"
        f"k (legs): {data.get('n_legs')}\n"
        f"DSR (N=family): {dsr_s}"
        f"{null_s}{nm_s}"
    )
