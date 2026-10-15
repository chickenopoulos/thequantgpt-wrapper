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
    # Backward-compatible alias: pass-set size (eligibility filter).
    stable_cells: int = 0
    pass_set_cells: int = 0
    island_cells: int = 0
    island_radius: int = 1
    R_strict: int = -1
    plateau_quality: str = "none"  # tight_island | diffuse_pass_set | none
    median_params: dict[str, float | int] | None = None
    sharpe_floor: float | None = None
    grid_cells: int = 0
    note: str = ""


@dataclass
class PlateauAnalysis:
    """Pass-set eligibility vs local tight island around median-nearest."""

    pass_set: list[dict[str, Any]]
    representative: dict[str, Any] | None
    median_perm: dict[str, float] | None
    median_nearest: dict[str, Any] | None
    tight_island: list[dict[str, Any]]
    island_radius: int
    R_strict: int
    sharpe_floor: float
    plateau_quality: str
    param_keys: list[str]


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


def _param_axes(rows: list[dict[str, Any]], param_keys: list[str]) -> dict[str, list[float]]:
    return {k: sorted({float(r[k]) for r in rows if k in r and r[k] is not None}) for k in param_keys}


def _param_index(params: dict[str, Any], axes: dict[str, list[float]], param_keys: list[str]) -> tuple[int, ...]:
    out: list[int] = []
    for k in param_keys:
        vals = axes[k]
        v = float(params[k])
        # Exact match preferred; else nearest axis value.
        if v in vals:
            out.append(vals.index(v))
        else:
            nearest = min(vals, key=lambda x: (abs(x - v), x))
            out.append(vals.index(nearest))
    return tuple(out)


def _chebyshev(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    return int(max(abs(x - y) for x, y in zip(a, b))) if a and b else 0


def _infer_param_keys(rows: list[dict[str, Any]], param_keys: list[str] | None = None) -> list[str]:
    metric_keys = {
        "Sharpe",
        "CAGR",
        "MaxDD",
        "num_trades",
        "win_rate",
        "profit_factor",
        "exposure",
        "skipped",
        "error",
        "total_return",
        "Vol",
    }
    if param_keys:
        return [k for k in param_keys if any(k in r for r in rows)]
    keys: list[str] = []
    for r in rows:
        for k, v in r.items():
            if k in metric_keys or k in keys:
                continue
            if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
                keys.append(k)
        if keys:
            break
    return keys


def filter_pass_set(
    rows: list[dict[str, Any]],
    *,
    sharpe_floor: float,
    min_pf: float,
    min_trades: float,
) -> list[dict[str, Any]]:
    """Eligibility filter: IS Sharpe / PF / trades thresholds (not a local island)."""
    return [
        r
        for r in rows
        if float(r.get("Sharpe", 0.0)) >= sharpe_floor
        and float(r.get("profit_factor", 0.0)) >= min_pf
        and float(r.get("num_trades", 0.0)) >= min_trades
        and not bool(r.get("skipped", False))
    ]


def median_permutation(pass_set: list[dict[str, Any]], param_keys: list[str]) -> dict[str, float] | None:
    if not pass_set or not param_keys:
        return None
    return {k: float(np.median([float(r[k]) for r in pass_set])) for k in param_keys}


def nearest_pass_cell(
    pass_set: list[dict[str, Any]],
    target: dict[str, float],
    *,
    param_keys: list[str],
    axes: dict[str, list[float]],
) -> dict[str, Any] | None:
    if not pass_set:
        return None
    target_ix = _param_index(target, axes, param_keys)

    def _key(r: dict[str, Any]) -> tuple:
        ix = _param_index(r, axes, param_keys)
        cheb = _chebyshev(ix, target_ix)
        l1 = sum(abs(a - b) for a, b in zip(ix, target_ix))
        # Prefer closer cells; tie-break on higher Sharpe then lower param tuple.
        return (cheb, l1, -float(r.get("Sharpe", 0.0)), ix)

    return min(pass_set, key=_key)


def chebyshev_ball(
    rows: list[dict[str, Any]],
    center: dict[str, Any],
    *,
    param_keys: list[str],
    axes: dict[str, list[float]],
    radius: int,
) -> list[dict[str, Any]]:
    cix = _param_index(center, axes, param_keys)
    return [r for r in rows if _chebyshev(_param_index(r, axes, param_keys), cix) <= radius]


def strict_robustness_radius(
    rows: list[dict[str, Any]],
    pass_set: list[dict[str, Any]],
    center: dict[str, Any],
    *,
    param_keys: list[str],
    axes: dict[str, list[float]],
) -> int:
    """Largest R where every existing grid cell in the ball is in the pass set."""
    if not pass_set or center is None:
        return -1
    pass_ids = {id(r) for r in pass_set}
    # Identity may fail across copies — also key by param tuple.
    pass_keys = {tuple(float(r[k]) for k in param_keys) for r in pass_set}
    cix = _param_index(center, axes, param_keys)
    max_r = max((_chebyshev(_param_index(r, axes, param_keys), cix) for r in rows), default=0)
    best = -1
    for r in range(0, max_r + 1):
        ball = [row for row in rows if _chebyshev(_param_index(row, axes, param_keys), cix) <= r]
        if not ball:
            break
        if all(tuple(float(row[k]) for k in param_keys) in pass_keys for row in ball):
            best = r
        else:
            break
    return best


def analyze_plateau(
    rows: list[dict[str, Any]],
    baseline_sharpe: float,
    *,
    param_keys: list[str] | None = None,
    sharpe_tolerance: float = 0.05,
    min_pf: float = 1.2,
    min_trades: float = 30,
    min_stable_cells: int = 3,
    island_radius: int = 1,
    floor_at_least_zero: bool = True,
) -> PlateauAnalysis:
    """Split PSA 'stable' into pass_set (eligibility) and tight_island (local R-ball).

    - pass_set: Sharpe ≥ floor, PF ≥ min_pf, trades ≥ min_trades
    - median_nearest: nearest pass_set cell to per-parameter medians
    - tight_island: pass_set cells within Chebyshev ``island_radius`` of median_nearest
    - plateau_quality: tight_island if R_strict ≥ island_radius and island non-empty;
      diffuse_pass_set if pass_set is large enough but not locally solid; else none
    """
    keys = _infer_param_keys(rows, param_keys)
    raw_floor = float(baseline_sharpe) - float(sharpe_tolerance)
    sharpe_floor = max(0.0, raw_floor) if floor_at_least_zero else raw_floor
    pass_set = filter_pass_set(rows, sharpe_floor=sharpe_floor, min_pf=min_pf, min_trades=min_trades)

    empty = PlateauAnalysis(
        pass_set=pass_set,
        representative=None,
        median_perm=None,
        median_nearest=None,
        tight_island=[],
        island_radius=int(island_radius),
        R_strict=-1,
        sharpe_floor=sharpe_floor,
        plateau_quality="none",
        param_keys=keys,
    )
    if len(pass_set) < min_stable_cells or not keys:
        return empty

    axes = _param_axes(rows, keys)
    med = median_permutation(pass_set, keys)
    assert med is not None
    median_nearest = nearest_pass_cell(pass_set, med, param_keys=keys, axes=axes)
    representative = max(pass_set, key=lambda r: float(r["Sharpe"]))
    R_strict = strict_robustness_radius(
        rows, pass_set, median_nearest, param_keys=keys, axes=axes
    ) if median_nearest is not None else -1

    if median_nearest is None:
        return PlateauAnalysis(
            pass_set=pass_set,
            representative=representative,
            median_perm=med,
            median_nearest=None,
            tight_island=[],
            island_radius=int(island_radius),
            R_strict=-1,
            sharpe_floor=sharpe_floor,
            plateau_quality="diffuse_pass_set",
            param_keys=keys,
        )

    island = [
        r
        for r in chebyshev_ball(
            pass_set, median_nearest, param_keys=keys, axes=axes, radius=int(island_radius)
        )
    ]
    # Prefer listing island members sorted for determinism.
    island = sorted(
        island,
        key=lambda r: tuple(float(r[k]) for k in keys) + (-float(r.get("Sharpe", 0.0)),),
    )

    if R_strict >= int(island_radius) and len(island) >= min_stable_cells:
        quality = "tight_island"
    else:
        quality = "diffuse_pass_set"

    return PlateauAnalysis(
        pass_set=pass_set,
        representative=representative,
        median_perm=med,
        median_nearest=median_nearest,
        tight_island=island,
        island_radius=int(island_radius),
        R_strict=int(R_strict),
        sharpe_floor=sharpe_floor,
        plateau_quality=quality,
        param_keys=keys,
    )


def _find_stable_center(
    rows: list[dict[str, Any]],
    baseline_sharpe: float,
    *,
    sharpe_tolerance: float,
    min_pf: float,
    min_trades: float,
    min_stable_cells: int,
    param_keys: list[str] | None = None,
    island_radius: int = 1,
) -> tuple[dict[str, Any] | None, int, PlateauAnalysis]:
    """Backward-compatible wrapper: representative center + pass_set size + full plateau."""
    plateau = analyze_plateau(
        rows,
        baseline_sharpe,
        param_keys=param_keys,
        sharpe_tolerance=sharpe_tolerance,
        min_pf=min_pf,
        min_trades=min_trades,
        min_stable_cells=min_stable_cells,
        island_radius=island_radius,
    )
    if len(plateau.pass_set) < min_stable_cells or plateau.representative is None:
        return None, len(plateau.pass_set), plateau
    return plateau.representative, len(plateau.pass_set), plateau


def _result_from_plateau(
    *,
    spec: PsaSpec,
    status: str,
    baseline_sharpe: float,
    plateau: PlateauAnalysis,
    grid_cells: int,
    note: str = "",
) -> PsaResult:
    center = plateau.representative
    med = plateau.median_nearest or plateau.median_perm
    return PsaResult(
        spec.id,
        spec.name,
        spec.universe,
        spec.asset_class,
        status=status,
        rep_sharpe=float(center["Sharpe"]) if center else None,
        rep_pf=float(center["profit_factor"]) if center else None,
        rep_trades=float(center["num_trades"]) if center else None,
        rep_params={k: center[k] for k in plateau.param_keys if center and k in center} if center else None,
        baseline_sharpe=baseline_sharpe,
        stable_cells=len(plateau.pass_set),
        pass_set_cells=len(plateau.pass_set),
        island_cells=len(plateau.tight_island),
        island_radius=plateau.island_radius,
        R_strict=plateau.R_strict,
        plateau_quality=plateau.plateau_quality,
        median_params={k: med[k] for k in plateau.param_keys if med and k in med} if med else None,
        sharpe_floor=plateau.sharpe_floor,
        grid_cells=grid_cells,
        note=note,
    )


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
    center, _stable_n, plateau = _find_stable_center(
        rows,
        baseline_sharpe,
        sharpe_tolerance=spec.sharpe_tolerance,
        min_pf=spec.min_pf,
        min_trades=float(spec.min_trades),
        min_stable_cells=spec.min_stable_cells,
        param_keys=list(spec.grid.keys()),
    )

    if center is None:
        return _result_from_plateau(
            spec=spec,
            status="NO_STABLE",
            baseline_sharpe=baseline_sharpe,
            plateau=plateau,
            grid_cells=len(rows),
            note=(
                f"pass_set<{spec.min_stable_cells} "
                f"(Sharpe≥{plateau.sharpe_floor:.2f}, PF≥{spec.min_pf}, trades≥{spec.min_trades}); "
                f"plateau_quality={plateau.plateau_quality}"
            ),
        )

    note = (
        f"pass_set={len(plateau.pass_set)}, tight_island(R={plateau.island_radius})="
        f"{len(plateau.tight_island)}, R_strict={plateau.R_strict}, "
        f"quality={plateau.plateau_quality}"
    )
    return _result_from_plateau(
        spec=spec,
        status="STABLE",
        baseline_sharpe=baseline_sharpe,
        plateau=plateau,
        grid_cells=len(rows),
        note=note,
    )
