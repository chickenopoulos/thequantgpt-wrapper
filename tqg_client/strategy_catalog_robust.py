"""Robust catalog evaluation: PSA plateau selection, IS/OOS metrics, confidence."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import vectorbt as vbt

from tqg_client.strategy_psa_core import (
    PsaResult,
    PsaSpec,
    _find_stable_center,
    _grid_param_combos,
    _merge_params,
)
from tqg_client.strategy_sweep_core import FEE, OOS, SLIPPAGE, SkipStrategy, _ann_factor

REPO = Path(__file__).resolve().parents[1]


@dataclass
class PeriodMetrics:
    sharpe: float = 0.0
    max_dd: float = 0.0
    cagr: float = 0.0
    trades: int = 0
    profit_factor: float = 0.0


@dataclass
class RobustEval:
    id: str
    name: str
    description: str
    universe: str
    asset_class: str
    status: str
    selection_mode: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    is_metrics: PeriodMetrics = field(default_factory=PeriodMetrics)
    oos_metrics: PeriodMetrics = field(default_factory=PeriodMetrics)
    cost_stress_oos: PeriodMetrics = field(default_factory=PeriodMetrics)
    psa_status: str = ""
    psa_stable_cells: int = 0
    psa_grid_cells: int = 0
    baseline_is_sharpe: float | None = None
    robustness_guardrails: str = ""
    robustness_confidence: float = 0.0
    note: str = ""


def load_strategy_descriptions(path: Path | None = None) -> dict[str, tuple[str, str]]:
    """Return {id: (title, logic)} from the research catalog markdown."""
    path = path or (REPO / "docs" / "research" / "implementable-strategies-from-sources.md")
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    rows = re.findall(
        r"\|\s*([A-Z]+-\d+)\s*\|\s*\*\*([^*]+)\*\*\s*\|\s*([^|]+)\|",
        text,
    )
    out: dict[str, tuple[str, str]] = {}
    for sid, title, logic in rows:
        out[sid] = (title.strip(), logic.strip())
    return out


def _period_from_returns(
    returns: pd.Series,
    *,
    ann: int,
    trades: int = 0,
    profit_factor: float = 0.0,
) -> PeriodMetrics:
    r = returns.dropna()
    if r.empty or len(r) < 5:
        return PeriodMetrics(trades=trades, profit_factor=profit_factor)
    cum = (1 + r).cumprod()
    dd = cum / cum.cummax() - 1
    vol = float(r.std())
    sharpe = float(np.sqrt(ann) * r.mean() / vol) if vol > 0 else 0.0
    cagr = float(cum.iloc[-1] ** (ann / len(r)) - 1) if len(r) > 0 else 0.0
    return PeriodMetrics(
        sharpe=sharpe,
        max_dd=float(dd.min()) if len(dd) else 0.0,
        cagr=cagr,
        trades=trades,
        profit_factor=profit_factor,
    )


def metrics_from_signals(
    close: pd.Series,
    entries: pd.Series,
    exits: pd.Series,
    *,
    symbol: str,
    asset_class: str,
    interval: str,
    short_entries: pd.Series | None = None,
    short_exits: pd.Series | None = None,
    fee_mult: float = 1.0,
    period: str = "full",
) -> PeriodMetrics:
    ann = _ann_factor(symbol, asset_class, interval)
    freq = "1H" if interval == "1h" else "1D"
    close = close.astype(float)
    pf = vbt.Portfolio.from_signals(
        close,
        entries=entries.fillna(False).astype(bool),
        exits=exits.fillna(False).astype(bool),
        short_entries=short_entries.fillna(False).astype(bool) if short_entries is not None else False,
        short_exits=short_exits.fillna(False).astype(bool) if short_exits is not None else False,
        fees=FEE * fee_mult,
        slippage=SLIPPAGE * fee_mult,
        freq=freq,
    )
    raw = pf.returns()
    if isinstance(raw, pd.DataFrame):
        raw = raw.iloc[:, 0]
    rets = pd.Series(np.asarray(raw).astype(float).ravel(), index=close.index, name="returns")
    if period == "is":
        mask = rets.index < OOS
    elif period == "oos":
        mask = rets.index >= OOS
    else:
        mask = pd.Series(True, index=rets.index)
    period_rets = rets.loc[mask]
    trades, pf_val = _trade_count_pf(pf, period_rets.index.min() if len(period_rets) else None, period_rets.index.max() if len(period_rets) else None)
    return _period_from_returns(period_rets, ann=ann, trades=trades, profit_factor=pf_val)


def _trade_count_pf(pf: vbt.Portfolio, start, end) -> tuple[int, float]:
    try:
        trades = pf.trades.records_readable.copy()
    except Exception:
        return 0, 0.0
    if trades.empty or start is None or end is None:
        return 0, 0.0
    entry_ts = pd.to_datetime(trades["Entry Timestamp"], utc=True)
    trades = trades.loc[(entry_ts >= start) & (entry_ts <= end)]
    if trades.empty:
        return 0, 0.0
    pnls = trades["Return"].astype(float)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gp = float(wins.sum()) if not wins.empty else 0.0
    gl = float(abs(losses.sum())) if not losses.empty else 0.0
    pf_val = gp / gl if gl > 0 else 0.0
    return int(len(trades)), pf_val


def metrics_from_returns_series(
    returns: pd.Series,
    *,
    symbol: str,
    asset_class: str,
    interval: str,
    period: str = "full",
) -> PeriodMetrics:
    ann = _ann_factor(symbol, asset_class, interval)
    r = returns.copy()
    if period == "is":
        r = r.loc[r.index < OOS]
    elif period == "oos":
        r = r.loc[r.index >= OOS]
    active = int((r.fillna(0) != 0).sum())
    return _period_from_returns(r, ann=ann, trades=active, profit_factor=0.0)


def evaluate_params(spec: PsaSpec, params: dict[str, Any], *, fee_mult: float = 1.0) -> tuple[PeriodMetrics, PeriodMetrics]:
    out = spec.build(params)
    if spec.mode == "returns":
        returns = out if isinstance(out, pd.Series) else out[0]
        # Fee mult approximated by scaling returns slightly when fee_mult != 1
        if fee_mult != 1.0:
            returns = returns * (1.0 - 0.002 * (fee_mult - 1.0))
        return (
            metrics_from_returns_series(
                returns, symbol=spec.symbol, asset_class=spec.asset_class, interval=spec.interval, period="is"
            ),
            metrics_from_returns_series(
                returns, symbol=spec.symbol, asset_class=spec.asset_class, interval=spec.interval, period="oos"
            ),
        )
    close, entries, exits = out[0], out[1], out[2]
    short_entries = out[3] if len(out) > 3 else None
    short_exits = out[4] if len(out) > 4 else None
    kw = dict(
        close=close,
        entries=entries,
        exits=exits,
        symbol=spec.symbol,
        asset_class=spec.asset_class,
        interval=spec.interval,
        short_entries=short_entries,
        short_exits=short_exits,
        fee_mult=fee_mult,
    )
    return metrics_from_signals(**kw, period="is"), metrics_from_signals(**kw, period="oos")


def _soft_select(rows: list[dict[str, Any]], spec: PsaSpec) -> dict[str, Any] | None:
    """Best IS cell under soft robustness floors when no stable plateau exists."""
    min_trades = max(5, int(spec.min_trades * 0.5))
    candidates = [
        r
        for r in rows
        if r.get("Sharpe", 0) is not None
        and float(r.get("num_trades", 0) or 0) >= min_trades
        and float(r.get("profit_factor", 0) or 0) >= 1.0
    ]
    if not candidates:
        candidates = [
            r
            for r in rows
            if float(r.get("num_trades", 0) or 0) >= min_trades and float(r.get("Sharpe", -999)) > -999
        ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: float(r.get("Sharpe", 0)) + 0.25 * float(r.get("profit_factor", 0) or 0))


def _psa_grid_rows(spec: PsaSpec) -> tuple[list[dict[str, Any]], float | None]:
    """Replay PSA grid (IS-only) and return rows + baseline Sharpe."""
    from tqg_client.strategy_psa_core import _is_metrics_from_returns, _is_metrics_from_signals

    combos = _grid_param_combos(spec.grid)
    rows: list[dict[str, Any]] = []
    for combo in combos:
        params = _merge_params(spec.baseline, combo)
        try:
            out = spec.build(params)
        except Exception as e:
            rows.append({**combo, "Sharpe": 0.0, "profit_factor": 0.0, "num_trades": 0.0, "error": str(e)[:80]})
            continue
        if spec.mode == "returns":
            returns = out if isinstance(out, pd.Series) else out[0]
            m = _is_metrics_from_returns(
                returns, symbol=spec.symbol, asset_class=spec.asset_class, interval=spec.interval
            )
        else:
            close, entries, exits = out[0], out[1], out[2]
            short_entries = out[3] if len(out) > 3 else None
            short_exits = out[4] if len(out) > 4 else None
            m = _is_metrics_from_signals(
                close,
                entries,
                exits,
                symbol=spec.symbol,
                asset_class=spec.asset_class,
                interval=spec.interval,
                short_entries=short_entries,
                short_exits=short_exits,
            )
        rows.append({**combo, **m})

    baseline_row = None
    for r in rows:
        if all(r.get(k) == v for k, v in spec.baseline.items() if k in spec.grid):
            baseline_row = r
            break
    baseline_sharpe = float(baseline_row["Sharpe"]) if baseline_row else None
    return rows, baseline_sharpe


def select_from_grid(
    spec: PsaSpec, rows: list[dict[str, Any]], baseline_sharpe: float
) -> tuple[dict[str, Any], str, PsaResult]:
    """Pick robust params from an IS-only grid; prefer stable plateau, else soft max Sharpe."""
    center, stable_n = _find_stable_center(
        rows,
        baseline_sharpe,
        sharpe_tolerance=spec.sharpe_tolerance,
        min_pf=spec.min_pf,
        min_trades=float(spec.min_trades),
        min_stable_cells=spec.min_stable_cells,
    )
    if center is not None:
        params = {k: center[k] for k in spec.grid}
        psa = PsaResult(
            spec.id,
            spec.name,
            spec.universe,
            spec.asset_class,
            status="STABLE",
            rep_sharpe=float(center["Sharpe"]),
            rep_pf=float(center["profit_factor"]),
            rep_trades=float(center["num_trades"]),
            rep_params=params,
            baseline_sharpe=baseline_sharpe,
            stable_cells=stable_n,
            grid_cells=len(rows),
        )
        return params, "psa_stable_plateau", psa

    soft = _soft_select(rows, spec)
    if soft is not None:
        params = {k: soft[k] for k in spec.grid}
        psa = PsaResult(
            spec.id,
            spec.name,
            spec.universe,
            spec.asset_class,
            status="NO_STABLE",
            baseline_sharpe=baseline_sharpe,
            stable_cells=stable_n,
            grid_cells=len(rows),
            note=f"soft-selected; stable<{spec.min_stable_cells}",
        )
        return params, "soft_grid_max_robust_sharpe", psa

    psa = PsaResult(
        spec.id,
        spec.name,
        spec.universe,
        spec.asset_class,
        status="NO_STABLE",
        baseline_sharpe=baseline_sharpe,
        stable_cells=stable_n,
        grid_cells=len(rows),
        note="baseline fallback",
    )
    return dict(spec.baseline), "baseline_fallback", psa


def robustness_confidence(
    *,
    psa: PsaResult,
    selection_mode: str,
    is_m: PeriodMetrics,
    oos_m: PeriodMetrics,
    stress_m: PeriodMetrics,
) -> float:
    score = 0.0

    if psa.status == "STABLE" and psa.grid_cells > 0:
        score += 40.0 * (psa.stable_cells / max(psa.grid_cells, 1))
    elif selection_mode == "soft_grid_max_robust_sharpe":
        score += 15.0
    elif selection_mode == "baseline_only":
        score += 5.0

    if oos_m.sharpe > 0.5:
        score += 15.0
    elif oos_m.sharpe > 0:
        score += 8.0

    gap = abs(is_m.sharpe - oos_m.sharpe)
    if gap < 0.5:
        score += 15.0
    elif gap < 1.0:
        score += 10.0
    elif gap < 1.5:
        score += 5.0

    if oos_m.sharpe != 0:
        retention = stress_m.sharpe / oos_m.sharpe if oos_m.sharpe > 0 else 0.0
        if retention >= 0.7:
            score += 15.0
        elif retention >= 0.5:
            score += 10.0
        elif retention >= 0.3:
            score += 5.0
    elif stress_m.sharpe >= oos_m.sharpe:
        score += 5.0

    if oos_m.trades >= 30:
        score += 10.0
    elif oos_m.trades >= 15:
        score += 6.0
    elif oos_m.trades >= 5:
        score += 3.0

    if is_m.profit_factor >= 1.2:
        score += 5.0

    return float(max(0.0, min(100.0, round(score, 1))))


def guardrails_used(psa: PsaResult, selection_mode: str) -> str:
    parts = [
        "OOS cut-off 2025-01-01 (no OOS tuning)",
        "signal lag ≥1 bar",
        "fees 4.5bps + slip 5bps",
        "cost stress 2× fees/slip on OOS",
    ]
    if psa.status == "STABLE":
        parts.append(
            f"PSA IS plateau (Sharpe≥baseline−0.05, PF≥1.2, trades≥min; "
            f"{psa.stable_cells}/{psa.grid_cells} stable cells)"
        )
        parts.append("rep params = plateau center (Sharpe+0.25×PF), not grid peak")
    elif selection_mode == "soft_grid_max_robust_sharpe":
        parts.append("PSA grid searched IS-only; no stable plateau — soft floors PF≥1.0 + min trades")
        parts.append("selected max (Sharpe+0.25×PF) under soft floors")
    elif selection_mode == "baseline_only":
        parts.append("no PSA grid / data skip — baseline params only")
    else:
        parts.append("baseline params (PSA NO_STABLE / fallback)")
    return "; ".join(parts)


def evaluate_spec(spec: PsaSpec, descriptions: dict[str, tuple[str, str]] | None = None) -> RobustEval:
    descriptions = descriptions or {}
    title, logic = descriptions.get(spec.id, (spec.name, ""))
    desc = f"{title}: {logic}".strip(": ")

    if spec.skip_reason or spec.build is None or not spec.grid:
        reason = spec.skip_reason or "no PSA grid defined"
        return RobustEval(
            id=spec.id,
            name=spec.name,
            description=desc,
            universe=spec.universe,
            asset_class=spec.asset_class,
            status="SKIP",
            selection_mode="skipped",
            psa_status="SKIP",
            robustness_guardrails=guardrails_used(
                PsaResult(spec.id, spec.name, spec.universe, spec.asset_class, "SKIP"),
                "baseline_only",
            ),
            robustness_confidence=0.0,
            note=reason,
        )

    try:
        rows, baseline_sharpe = _psa_grid_rows(spec)
        if baseline_sharpe is None:
            baseline_sharpe = 0.0
        params, mode, psa = select_from_grid(spec, rows, baseline_sharpe)
        params = _merge_params(spec.baseline, params)
        is_m, oos_m = evaluate_params(spec, params, fee_mult=1.0)
        _, stress_m = evaluate_params(spec, params, fee_mult=2.0)
    except SkipStrategy as e:
        return RobustEval(
            id=spec.id,
            name=spec.name,
            description=desc,
            universe=spec.universe,
            asset_class=spec.asset_class,
            status="SKIP",
            psa_status="SKIP",
            note=str(e.reason),
            robustness_confidence=0.0,
            robustness_guardrails="data unavailable",
        )
    except Exception as e:
        return RobustEval(
            id=spec.id,
            name=spec.name,
            description=desc,
            universe=spec.universe,
            asset_class=spec.asset_class,
            status="ERROR",
            psa_status="ERROR",
            note=str(e)[:160],
            robustness_confidence=0.0,
            robustness_guardrails="evaluation error",
        )

    conf = robustness_confidence(
        psa=psa, selection_mode=mode, is_m=is_m, oos_m=oos_m, stress_m=stress_m
    )
    status = "OK"
    if oos_m.trades == 0 and is_m.trades == 0:
        status = "NO_TRADES"

    return RobustEval(
        id=spec.id,
        name=spec.name,
        description=desc,
        universe=spec.universe,
        asset_class=spec.asset_class,
        status=status,
        selection_mode=mode,
        params=params,
        is_metrics=is_m,
        oos_metrics=oos_m,
        cost_stress_oos=stress_m,
        psa_status=psa.status,
        psa_stable_cells=psa.stable_cells,
        psa_grid_cells=psa.grid_cells,
        baseline_is_sharpe=psa.baseline_sharpe,
        robustness_guardrails=guardrails_used(psa, mode),
        robustness_confidence=conf,
        note=psa.note or "",
    )
