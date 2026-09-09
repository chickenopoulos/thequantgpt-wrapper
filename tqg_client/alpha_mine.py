"""Formulaic alpha mining pipeline: evaluate, steer, mutate, optional OOS book."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .alpha_eval import book_returns, combine_signals, score_signal, split_is_oos
from .alpha_ops import (
    catalog_payload,
    derive_fields,
    evaluate_expr,
    replace_last_int,
    substitute_params,
)
from .alpha_seeds import seeds_for_packs
from .market_data import default_annualization, load_ohlcv_panel
from .run_state import (
    load_run_state,
    load_strategy_spec,
    merge_execution_feedback,
    run_root_from_state,
    save_run_state,
)
from .selection import after_execution, persist_is_returns, record_trials

SCHEMA_VERSION = 1
ALPHAS_RELPATH = "artifacts/alphas.json"
MOMENTUM_EXPR = "cs_rank(ts_sum(ret, 20))"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _fingerprint(item: dict[str, Any]) -> str:
    params = item.get("params") if isinstance(item.get("params"), dict) else {}
    expr = substitute_params(str(item.get("expr") or ""), params)
    return f"{item.get('id')}|{expr}"


def _wrap_neutralize(expr: str) -> str:
    body = expr.strip()
    if body.startswith("cs_demean(") and body.endswith(")"):
        return body
    return f"cs_demean({body})"


def load_formulas_file(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("formulas"), list):
        items = raw["formulas"]
    elif isinstance(raw, list):
        items = raw
    else:
        raise ValueError(f"{path} must be a list or an object with formulas[]")
    out: list[dict[str, Any]] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict) or not item.get("expr"):
            raise ValueError(f"Formula {i} needs an expr")
        row = dict(item)
        row.setdefault("id", f"A{i+1:02d}")
        row.setdefault("description", "")
        row.setdefault("tags", [])
        row.setdefault("status", "active")
        out.append(row)
    return out


def _oos_ts(value: str | None) -> str:
    return str(value or "2025-01-01")


def _load_panel(spec: dict[str, Any], *, panel_path: Path | None, top_n: int | None, min_bars: int) -> tuple[dict[str, pd.DataFrame], str]:
    universe = spec.get("universe") if isinstance(spec.get("universe"), dict) else {}
    path = Path(panel_path or universe.get("path") or "")
    if not str(path):
        raise ValueError("Need --panel or strategy_spec.universe.path")
    oos = _oos_ts(spec.get("oos_start_ts"))
    n = int(top_n if top_n is not None else universe.get("top_n") or 50)
    fields = load_ohlcv_panel(
        path,
        interval=spec.get("interval") or "1d",
        min_bars=min_bars,
        top_n=n,
        liquidity_end=oos,
    )
    return derive_fields(fields), str(path)


def _momentum_panel(fields: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return evaluate_expr(MOMENTUM_EXPR, fields)


def evaluate_items(
    items: list[dict[str, Any]],
    fields: dict[str, pd.DataFrame],
    *,
    oos_start: str,
    annualization: float,
    include_oos: bool,
    lag: int = 1,
) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame]]:
    momentum = _momentum_panel(fields)
    close = fields["close"]
    scored: list[dict[str, Any]] = []
    panels: dict[str, pd.DataFrame] = {}
    for item in items:
        expr = str(item["expr"])
        params = item.get("params") if isinstance(item.get("params"), dict) else {}
        try:
            signal = evaluate_expr(expr, fields, params=params)
        except Exception as exc:  # noqa: BLE001
            scored.append(
                {
                    **{k: item.get(k) for k in ("id", "expr", "description", "tags", "parent_id")},
                    "status": "invalid",
                    "error": str(exc),
                    "is": None,
                    "oos": None,
                    "corr_momentum": None,
                    "flags": ["invalid"],
                    "fingerprint": _fingerprint(item),
                }
            )
            continue
        metrics = score_signal(
            signal,
            close,
            oos_start=oos_start,
            annualization=annualization,
            lag=lag,
            momentum=momentum,
            include_oos=include_oos,
        )
        row = {
            "id": item["id"],
            "expr": substitute_params(expr, params),
            "description": item.get("description") or "",
            "tags": list(item.get("tags") or []),
            "parent_id": item.get("parent_id"),
            "status": item.get("status") or "active",
            "is": metrics["is"],
            "oos": metrics["oos"],
            "corr_momentum": metrics["corr_momentum"],
            "flags": list(metrics["flags"] or []),
            "lag_bars": metrics["lag_bars"],
            "fingerprint": _fingerprint(item),
        }
        scored.append(row)
        panels[str(item["id"])] = signal
    return scored, panels


def _merge_history(previous: dict[str, Any] | None, scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hist = []
    if previous and isinstance(previous.get("alphas"), list):
        hist = list(previous["alphas"])
    by_fp = {str(row.get("fingerprint") or _fingerprint(row)): row for row in hist if isinstance(row, dict)}
    for row in scored:
        by_fp[str(row["fingerprint"])] = row
    return list(by_fp.values())


def _write_spec(
    run_root: Path,
    *,
    panel_path: str,
    oos_start: str,
    n_assets: int,
    top_n: int,
    annualization: float,
    asset_class: str,
    book_ids: list[str],
    interval: str,
    extra_operands: list[str] | None = None,
) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "workflow": "formulaic_alpha",
        "strategy_type": "FORMULAIC_ALPHA",
        "symbol": "PANEL",
        "interval": interval,
        "asset_class": asset_class,
        "annualization": annualization,
        "oos_start_ts": oos_start,
        "universe": {"path": panel_path, "n_assets": n_assets, "top_n": top_n},
        "params": {"lag_bars": 1},
    }
    if extra_operands:
        spec["universe"]["extra_operands"] = list(extra_operands)
    if book_ids:
        spec["signals"] = list(book_ids)
    path = run_root / "strategy_spec.json"
    path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    return spec


def _metrics_from_scored(
    scored: list[dict[str, Any]],
    *,
    include_oos: bool,
    book_id: str | None,
) -> dict[str, Any]:
    active = [r for r in scored if r.get("status") == "active" and r.get("is")]
    pick = None
    if book_id:
        pick = next((r for r in scored if r.get("id") == book_id), None)
    if pick is None and active:
        pick = max(active, key=lambda r: (r["is"] or {}).get("rank_ic") or float("-inf"))
    metrics: dict[str, Any] = {}
    if pick and pick.get("is"):
        block = pick["is"]
        metrics["in_sample"] = {
            "RankIC": block.get("rank_ic"),
            "IC": block.get("ic"),
            "Sharpe": block.get("sharpe"),
            "turnover": block.get("turnover"),
            "n_days": block.get("n_days"),
            "alpha_id": pick.get("id"),
        }
    if include_oos and pick and pick.get("oos"):
        block = pick["oos"]
        metrics["out_of_sample"] = {
            "RankIC": block.get("rank_ic"),
            "IC": block.get("ic"),
            "Sharpe": block.get("sharpe"),
            "turnover": block.get("turnover"),
            "n_days": block.get("n_days"),
            "alpha_id": pick.get("id"),
        }
    return metrics


def run_alpha_mine(
    run_id: str,
    *,
    panel_path: Path | str | None = None,
    formulas: list[dict[str, Any]] | None = None,
    packs: list[str] | None = None,
    drop_ids: list[str] | None = None,
    keep_ids: list[str] | None = None,
    neutralize: bool = False,
    mutate_id: str | None = None,
    windows: list[int] | None = None,
    book_ids: list[str] | None = None,
    reveal_oos: bool = False,
    top_n: int | None = None,
    min_bars: int = 60,
    asset_class: str | None = None,
    oos_start: str | None = None,
) -> dict[str, Any]:
    state = load_run_state(run_id)
    run_root = run_root_from_state(state)
    spec = load_strategy_spec(run_root) or {}
    if oos_start:
        spec["oos_start_ts"] = oos_start
    spec.setdefault("oos_start_ts", state.oos_start_ts or "2025-01-01")
    spec.setdefault("interval", (state.defaults or {}).get("interval") or "1d")

    fields, resolved_panel = _load_panel(
        spec, panel_path=Path(panel_path) if panel_path else None, top_n=top_n, min_bars=min_bars
    )
    n_assets = int(fields["close"].shape[1])
    inferred_class = asset_class or spec.get("asset_class")
    if not inferred_class:
        names = list(fields["close"].columns)
        inferred_class = "crypto" if names and str(names[0]).upper().endswith("USDT") else "equity"
    ann = float(spec.get("annualization") or default_annualization(str(fields["close"].columns[0]), asset_class=inferred_class))
    oos = _oos_ts(spec.get("oos_start_ts"))

    previous = _read_json(run_root / ALPHAS_RELPATH)
    items: list[dict[str, Any]] = []
    if formulas:
        items.extend(formulas)
    elif packs is not None or previous is None:
        items.extend(seeds_for_packs(packs))
    elif previous and isinstance(previous.get("alphas"), list):
        for row in previous["alphas"]:
            if isinstance(row, dict) and row.get("expr") and row.get("status") != "invalid":
                items.append(
                    {
                        "id": row["id"],
                        "expr": row["expr"],
                        "description": row.get("description") or "",
                        "tags": row.get("tags") or [],
                        "status": row.get("status") or "active",
                        "parent_id": row.get("parent_id"),
                    }
                )

    drop = {str(x) for x in (drop_ids or [])}
    keep = {str(x) for x in (keep_ids or [])} if keep_ids else None
    filtered: list[dict[str, Any]] = []
    for item in items:
        ident = str(item["id"])
        if ident in drop:
            item = dict(item)
            item["status"] = "dropped"
        if keep is not None and ident not in keep and item.get("status") != "dropped":
            item = dict(item)
            item["status"] = "dropped"
        if neutralize and item.get("status") != "dropped":
            item = dict(item)
            item["expr"] = _wrap_neutralize(str(item["expr"]))
            item["id"] = ident if ident.endswith("n") or "demean" in str(item["expr"]) else f"{ident}n"
            item["parent_id"] = item.get("parent_id") or ident
        filtered.append(item)

    if mutate_id:
        parent = next((x for x in filtered if str(x["id"]) == mutate_id), None)
        if parent is None and previous:
            for row in previous.get("alphas") or []:
                if isinstance(row, dict) and str(row.get("id")) == mutate_id:
                    parent = {
                        "id": row["id"],
                        "expr": row["expr"],
                        "description": row.get("description") or "",
                        "tags": row.get("tags") or [],
                        "status": "active",
                    }
                    break
        if parent is None:
            raise ValueError(f"Unknown mutate id {mutate_id}")
        win = windows or [10, 20, 40]
        for w in win:
            child = dict(parent)
            try:
                new_expr = replace_last_int(str(parent["expr"]), int(w))
            except ValueError as exc:
                raise ValueError(f"Cannot mutate {mutate_id}: {exc}") from exc
            if new_expr == str(parent["expr"]):
                continue
            child["expr"] = new_expr
            child["id"] = f"{parent['id']}_w{w}"
            child["parent_id"] = parent["id"]
            child["status"] = "active"
            child["description"] = f"Window mutant of {parent['id']} w={w}"
            filtered.append(child)

    to_score = [x for x in filtered if x.get("status") != "dropped"]
    scored, panels = evaluate_items(
        to_score,
        fields,
        oos_start=oos,
        annualization=ann,
        include_oos=reveal_oos,
    )
    dropped_rows = []
    for item in filtered:
        if item.get("status") == "dropped":
            dropped_rows.append(
                {
                    "id": item["id"],
                    "expr": item.get("expr"),
                    "description": item.get("description") or "",
                    "tags": item.get("tags") or [],
                    "parent_id": item.get("parent_id"),
                    "status": "dropped",
                    "is": None,
                    "oos": None,
                    "corr_momentum": None,
                    "flags": ["dropped"],
                    "fingerprint": _fingerprint(item),
                }
            )
    scored.extend(dropped_rows)

    merged = _merge_history(previous, scored)
    prev_fps = set()
    if previous and isinstance(previous.get("alphas"), list):
        prev_fps = {str(r.get("fingerprint")) for r in previous["alphas"] if isinstance(r, dict)}
    new_scored = [
        r
        for r in scored
        if r.get("status") != "dropped" and str(r.get("fingerprint")) not in prev_fps
    ]
    new_n = len(new_scored)

    book = book_ids or []
    book_panel = None
    book_metrics = None
    if book:
        missing = [i for i in book if i not in panels]
        if missing:
            raise ValueError(f"Book ids not in the scored active set: {missing}")
        book_panel = combine_signals([panels[i] for i in book])
        book_metrics = score_signal(
            book_panel,
            fields["close"],
            oos_start=oos,
            annualization=ann,
            lag=1,
            momentum=_momentum_panel(fields),
            include_oos=reveal_oos,
        )
        book_metrics = {
            "ids": list(book),
            "k": len(book),
            "lag_bars": 1,
            "is": book_metrics["is"],
            "oos": book_metrics["oos"],
            "corr_momentum": book_metrics["corr_momentum"],
            "flags": book_metrics["flags"],
        }

    operators = catalog_payload()
    extra_operands = sorted(set(fields) - set(operators["operands"]))
    if extra_operands:
        operators = dict(operators)
        operators["operands"] = list(operators["operands"]) + extra_operands

    artifact = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": _utc_now(),
        "panel": resolved_panel,
        "n_assets": n_assets,
        "oos_start_ts": oos,
        "oos_revealed": bool(reveal_oos),
        "lag_bars": 1,
        "annualization": ann,
        "operators": operators,
        "alphas": merged,
        "book": book_metrics,
        "note": (
            "OOS metrics are omitted until --reveal-oos. Rank on in-sample Rank IC only. "
            "Every newly scored formula increments N."
        ),
    }
    _write_json(run_root / ALPHAS_RELPATH, artifact)

    spec_out = _write_spec(
        run_root,
        panel_path=resolved_panel,
        oos_start=oos,
        n_assets=n_assets,
        top_n=int(top_n or n_assets),
        annualization=ann,
        asset_class=inferred_class,
        book_ids=book,
        interval=str(spec.get("interval") or "1d"),
        extra_operands=extra_operands,
    )
    metrics = _metrics_from_scored(scored, include_oos=reveal_oos, book_id=None)
    if book_metrics:
        metrics["in_sample"] = {
            "RankIC": book_metrics["is"].get("rank_ic"),
            "IC": book_metrics["is"].get("ic"),
            "Sharpe": book_metrics["is"].get("sharpe"),
            "turnover": book_metrics["is"].get("turnover"),
            "n_days": book_metrics["is"].get("n_days"),
            "alpha_id": "+".join(book),
        }
        if reveal_oos and book_metrics.get("oos"):
            metrics["out_of_sample"] = {
                "RankIC": book_metrics["oos"].get("rank_ic"),
                "IC": book_metrics["oos"].get("ic"),
                "Sharpe": book_metrics["oos"].get("sharpe"),
                "turnover": book_metrics["oos"].get("turnover"),
                "n_days": book_metrics["oos"].get("n_days"),
                "alpha_id": "+".join(book),
            }
    (run_root / "artifacts").mkdir(parents=True, exist_ok=True)
    if metrics:
        _write_json(run_root / "artifacts" / "metrics.json", metrics)

    if book_panel is not None:
        rets = book_returns(book_panel, fields["close"], lag=1)
        is_rets, _ = split_is_oos(rets.to_frame("r"), oos)
        persist_is_returns(run_root, is_rets.iloc[:, 0])
    elif panels:
        active_ids = [r["id"] for r in scored if r.get("status") == "active" and r["id"] in panels]
        if active_ids:
            combo = combine_signals([panels[i] for i in active_ids])
            rets = book_returns(combo, fields["close"], lag=1)
            is_rets, _ = split_is_oos(rets.to_frame("r"), oos)
            persist_is_returns(run_root, is_rets.iloc[:, 0])

    if new_n:
        record_trials(
            run_root,
            new_n,
            kind="inline_grid",
            script="tqg_alpha_mine.py",
            formulas=[r.get("id") for r in new_scored],
        )

    after_execution(
        run_root,
        run_id=run_id,
        script="tqg_alpha_mine.py",
        completed_step="baseline",
        namespace={"strategy_spec": spec_out},
        count_baseline=False,
    )

    feedback = {
        "success": True,
        "validation_passed": True,
        "completed_step": "baseline",
        "strategy_spec": spec_out,
        "artifacts": {
            "alphas": ALPHAS_RELPATH,
            "metrics": "artifacts/metrics.json",
            "selection": "artifacts/selection.json",
        },
        "n_new_formulas": new_n,
        "n_assets": n_assets,
        "oos_revealed": reveal_oos,
    }
    state = merge_execution_feedback(state, feedback)
    save_run_state(state)
    return {
        "run_id": run_id,
        "artifact": artifact,
        "n_new_formulas": new_n,
        "n_assets": n_assets,
        "oos_revealed": reveal_oos,
        "leaderboard": _leaderboard(scored, reveal_oos=reveal_oos),
    }


def _leaderboard(scored: list[dict[str, Any]], *, reveal_oos: bool) -> list[dict[str, Any]]:
    rows = [r for r in scored if r.get("status") == "active" and r.get("is")]
    rows.sort(key=lambda r: (r["is"] or {}).get("rank_ic") or float("-inf"), reverse=True)
    out = []
    for r in rows:
        item = {
            "id": r["id"],
            "expr": r["expr"],
            "description": r.get("description"),
            "is_rank_ic": (r["is"] or {}).get("rank_ic"),
            "is_sharpe": (r["is"] or {}).get("sharpe"),
            "corr_momentum": r.get("corr_momentum"),
            "flags": r.get("flags") or [],
        }
        if reveal_oos:
            item["oos_rank_ic"] = (r.get("oos") or {}).get("rank_ic")
            item["oos_sharpe"] = (r.get("oos") or {}).get("sharpe")
        out.append(item)
    return out
