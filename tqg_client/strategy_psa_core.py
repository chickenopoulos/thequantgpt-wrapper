"""Parameter sensitivity analysis (PSA) engine for strategy catalog batch runs."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

import numpy as np
import pandas as pd
import vectorbt as vbt

from tqg_client.strategy_sweep_core import FEE, OOS, SLIPPAGE, _ann_factor

Mode = Literal["signals", "returns"]


@dataclass
class PsaSpec:
    id: str
    name: str
    universe: str
    asset_class: str
    symbol: str
    interval: str = "1d"
    mode: Mode = "signals"
    baseline: dict[str, float | int] = field(default_factory=dict)
    grid: dict[str, list[float | int]] = field(default_factory=dict)
    min_trades: int = 30
    min_stable_cells: int = 3
    sharpe_tolerance: float = 0.05
    min_pf: float = 1.2
    build: Callable[..., tuple[pd.Series, pd.Series, pd.Series | None, pd.Series | None] | pd.Series] = None
    skip_reason: str | None = None


@dataclass
class PsaResult:
    id: str
    name: str
    universe: str
    asset_class: str
    status: str
    rep_sharpe: float | None = None
    rep_pf: float | None = None
    rep_trades: float | None = None
    rep_params: dict[str, float | int] | None = None
    baseline_sharpe: float | None = None
    stable_cells: int = 0
    grid_cells: int = 0
    note: str = ""


def _is_metrics_from_signals(
    close: pd.Series,
    entries: pd.Series,
    exits: pd.Series,
    *,
    symbol: str,
    asset_class: str,
    interval: str,
    short_entries: pd.Series | None = None,
    short_exits: pd.Series | None = None,
) -> dict[str, float]:
    ann = _ann_factor(symbol, asset_class, interval)
    pf = vbt.Portfolio.from_signals(
        close.astype(float),
        entries=entries.fillna(False).astype(bool),
        exits=exits.fillna(False).astype(bool),
        short_entries=short_entries.fillna(False).astype(bool) if short_entries is not None else False,
        short_exits=short_exits.fillna(False).astype(bool) if short_exits is not None else False,
        fees=FEE,
        slippage=SLIPPAGE,
        freq="1H" if interval == "1h" else "1D",
    )
    rets = pf.returns().loc[pf.returns().index < OOS]
    r = rets.dropna()
    if r.empty:
        return {
            "Sharpe": 0.0,
            "CAGR": 0.0,
            "MaxDD": 0.0,
            "num_trades": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
        }

    cum = (1 + r).cumprod()
    dd = cum / cum.cummax() - 1
    vol = r.std()
    sharpe = float(np.sqrt(ann) * r.mean() / vol) if vol > 0 else 0.0
    cagr = float((cum.iloc[-1]) ** (ann / len(r)) - 1) if len(r) > 0 else 0.0

    trades = pf.trades.records_readable.copy()
    if not trades.empty:
        entry_ts = pd.to_datetime(trades["Entry Timestamp"], utc=True)
        trades = trades.loc[entry_ts < OOS]
    if trades.empty:
        return {
            "Sharpe": sharpe,
            "CAGR": cagr,
            "MaxDD": float(dd.min()),
            "num_trades": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
        }

    pnls = trades["Return"].astype(float)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_profit = wins.sum() if not wins.empty else 0.0
    gross_loss = abs(losses.sum()) if not losses.empty else 0.0
    pf_val = float(gross_profit / gross_loss) if gross_loss > 0 else 0.0

    return {
        "Sharpe": sharpe,
        "CAGR": cagr,
        "MaxDD": float(dd.min()),
        "num_trades": float(len(trades)),
        "win_rate": float((pnls > 0).mean()),
        "profit_factor": pf_val,
    }


def _is_metrics_from_returns(
    returns: pd.Series,
    *,
    symbol: str,
    asset_class: str,
    interval: str,
) -> dict[str, float]:
    ann = _ann_factor(symbol, asset_class, interval)
    r = returns.loc[returns.index < OOS].dropna()
    if r.empty or len(r) < 30:
        return {
            "Sharpe": 0.0,
            "CAGR": 0.0,
            "MaxDD": 0.0,
            "num_trades": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
        }
    cum = (1 + r).cumprod()
    dd = cum / cum.cummax() - 1
    vol = r.std()
    sharpe = float(np.sqrt(ann) * r.mean() / vol) if vol > 0 else 0.0
    cagr = float(cum.iloc[-1] ** (ann / len(r)) - 1)
  # approximate activity as non-zero return days
    active = int((r != 0).sum())
    return {
        "Sharpe": sharpe,
        "CAGR": cagr,
        "MaxDD": float(dd.min()),
        "num_trades": float(active),
        "win_rate": 0.0,
        "profit_factor": 0.0,
    }


def _grid_param_combos(grid: dict[str, list[float | int]]) -> list[dict[str, float | int]]:
    keys = list(grid.keys())
    values = [grid[k] for k in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def _merge_params(baseline: dict[str, float | int], override: dict[str, float | int]) -> dict[str, float | int]:
    merged = dict(baseline)
    merged.update(override)
    return merged


def _find_stable_center(
    rows: list[dict[str, Any]],
    baseline_sharpe: float,
    *,
    sharpe_tolerance: float,
    min_pf: float,
    min_trades: float,
    min_stable_cells: int,
) -> tuple[dict[str, Any] | None, int]:
    sharpe_floor = baseline_sharpe - sharpe_tolerance
    stable = [
        r
        for r in rows
        if r["Sharpe"] >= sharpe_floor and r["profit_factor"] >= min_pf and r["num_trades"] >= min_trades
    ]
    if len(stable) < min_stable_cells:
        return None, len(stable)

    center = max(stable, key=lambda r: r["Sharpe"] + 0.25 * r["profit_factor"])
    return center, len(stable)


def run_psa(spec: PsaSpec) -> PsaResult:
    if spec.skip_reason:
        return PsaResult(
            spec.id,
            spec.name,
            spec.universe,
            spec.asset_class,
            status="SKIP",
            note=spec.skip_reason,
        )
    if spec.build is None or not spec.grid:
        return PsaResult(
            spec.id,
            spec.name,
            spec.universe,
            spec.asset_class,
            status="SKIP",
            note="no PSA grid defined",
        )

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
                returns,
                symbol=spec.symbol,
                asset_class=spec.asset_class,
                interval=spec.interval,
            )
        else:
            if isinstance(out, pd.Series):
                raise ValueError("signals mode expects tuple output")
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

    if not rows:
        return PsaResult(
            spec.id,
            spec.name,
            spec.universe,
            spec.asset_class,
            status="ERROR",
            note="empty grid",
        )

    baseline_params = _merge_params(spec.baseline, {})
    baseline_row = None
    for r in rows:
        if all(r.get(k) == v for k, v in spec.baseline.items() if k in spec.grid):
            baseline_row = r
            break
    if baseline_row is None:
        try:
            out = spec.build(baseline_params)
            if spec.mode == "returns":
                returns = out if isinstance(out, pd.Series) else out[0]
                baseline_row = _is_metrics_from_returns(
                    returns,
                    symbol=spec.symbol,
                    asset_class=spec.asset_class,
                    interval=spec.interval,
                )
            else:
                close, entries, exits = out[0], out[1], out[2]
                short_entries = out[3] if len(out) > 3 else None
                short_exits = out[4] if len(out) > 4 else None
                baseline_row = _is_metrics_from_signals(
                    close,
                    entries,
                    exits,
                    symbol=spec.symbol,
                    asset_class=spec.asset_class,
                    interval=spec.interval,
                    short_entries=short_entries,
                    short_exits=short_exits,
                )
        except Exception as e:
            return PsaResult(
                spec.id,
                spec.name,
                spec.universe,
                spec.asset_class,
                status="ERROR",
                note=str(e)[:100],
            )

    baseline_sharpe = float(baseline_row["Sharpe"])
    center, stable_n = _find_stable_center(
        rows,
        baseline_sharpe,
        sharpe_tolerance=spec.sharpe_tolerance,
        min_pf=spec.min_pf,
        min_trades=float(spec.min_trades),
        min_stable_cells=spec.min_stable_cells,
    )

    if center is None:
        return PsaResult(
            spec.id,
            spec.name,
            spec.universe,
            spec.asset_class,
            status="NO_STABLE",
            baseline_sharpe=baseline_sharpe,
            stable_cells=stable_n,
            grid_cells=len(rows),
            note=f"stable<{spec.min_stable_cells} (Sharpe≥{baseline_sharpe - spec.sharpe_tolerance:.2f}, PF≥{spec.min_pf}, trades≥{spec.min_trades})",
        )

    rep_params = {k: center[k] for k in spec.grid}
    return PsaResult(
        spec.id,
        spec.name,
        spec.universe,
        spec.asset_class,
        status="STABLE",
        rep_sharpe=float(center["Sharpe"]),
        rep_pf=float(center["profit_factor"]),
        rep_trades=float(center["num_trades"]),
        rep_params=rep_params,
        baseline_sharpe=baseline_sharpe,
        stable_cells=stable_n,
        grid_cells=len(rows),
    )
