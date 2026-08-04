"""Portfolio backtest engine for triangular pairs."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import ANN_FACTOR, COST_PER_LEG, LAG_BARS
from .data import log_prices
from .signals import triangle_weights, zscore_positions
from .triangles import Triangle, rolling_triangle_residual


@dataclass
class BacktestResult:
    daily_returns: pd.Series
    equity: pd.Series
    positions: pd.DataFrame
    metrics: dict


def compute_metrics(
    returns: pd.Series,
    oos_start: pd.Timestamp,
    *,
    ann_factor: int | None = None,
) -> dict:
    if ann_factor is None:
        ann_factor = ANN_FACTOR
    r = returns.dropna()
    if r.empty:
        return {"Sharpe": np.nan, "CAGR": np.nan, "MaxDD": np.nan, "n_days": 0}

    vol = r.std()
    sharpe = (r.mean() / vol * np.sqrt(ann_factor)) if vol > 0 else np.nan
    equity = (1 + r).cumprod()
    cagr = equity.iloc[-1] ** (ann_factor / len(r)) - 1
    dd = (equity / equity.cummax() - 1).min()

    out = {
        "Sharpe": float(sharpe),
        "CAGR": float(cagr),
        "MaxDD": float(dd),
        "n_days": int(len(r)),
        "vol_ann": float(vol * np.sqrt(ann_factor)),
    }

    for label, subset in [("full", r), ("in_sample", r[r.index < oos_start]), ("out_of_sample", r[r.index >= oos_start])]:
        if subset.empty:
            out[label] = {"Sharpe": np.nan, "CAGR": np.nan, "MaxDD": np.nan, "n_days": 0}
            continue
        vol_s = subset.std()
        sh = (subset.mean() / vol_s * np.sqrt(ann_factor)) if vol_s > 0 else np.nan
        eq = (1 + subset).cumprod()
        cg = eq.iloc[-1] ** (ann_factor / len(subset)) - 1
        mdd = (eq / eq.cummax() - 1).min()
        out[label] = {"Sharpe": float(sh), "CAGR": float(cg), "MaxDD": float(mdd), "n_days": int(len(subset))}
    return out


def backtest_triangles(
    close: pd.DataFrame,
    triangles: list[Triangle],
    *,
    window: int = 120,
    min_periods: int = 90,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
    max_triangles: int | None = None,
    weight_cap: float = 0.25,
    max_gross_exposure: float = 1.0,
) -> BacktestResult:
    """Run multi-triangle mean-reversion backtest with lagged execution."""
    log_close = log_prices(close)
    asset_returns = close.pct_change()

    active = triangles[:max_triangles] if max_triangles else triangles
    triangle_frames: dict[str, pd.DataFrame] = {}
    pos_frames: dict[str, pd.Series] = {}

    for tri in active:
        stats = rolling_triangle_residual(log_close, tri, window=window, min_periods=min_periods)
        pos = zscore_positions(stats["zscore"].shift(LAG_BARS), entry=entry_z, exit_=exit_z)
        triangle_frames[tri.key] = stats
        pos_frames[tri.key] = pos

    # Aggregate portfolio weights per asset.
    weights = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    turnover = pd.Series(0.0, index=close.index)

    for tri in active:
        stats = triangle_frames[tri.key]
        pos = pos_frames[tri.key]
        b1 = stats["beta1"]
        b2 = stats["beta2"]
        gross = 1.0 + b1.abs() + b2.abs()
        w_target = pos * (1.0 / gross)
        w_leg1 = pos * (-b1 / gross)
        w_leg2 = pos * (-b2 / gross)
        scale = weight_cap
        weights[tri.target] = weights[tri.target] + w_target * scale
        weights[tri.leg1] = weights[tri.leg1] + w_leg1 * scale
        weights[tri.leg2] = weights[tri.leg2] + w_leg2 * scale

    # Lag weights for no lookahead.
    weights_lag = weights.shift(LAG_BARS).fillna(0.0)
    gross = weights_lag.abs().sum(axis=1).replace(0, np.nan)
    # Normalize when gross > 1 to keep leverage bounded.
    scale = (1.0 / gross).clip(upper=1.0).fillna(1.0)
    weights_lag = weights_lag.mul(scale, axis=0)

    # Turnover = sum abs weight changes.
    turnover = weights_lag.diff().abs().sum(axis=1).fillna(0.0)
    # Three legs per triangle trade; approximate cost as turnover * cost_per_leg.
    costs = turnover * COST_PER_LEG

    port_ret = (weights_lag * asset_returns).sum(axis=1) - costs
    port_ret = port_ret.fillna(0.0)

    if max_gross_exposure < 1.0:
        gross_now = weights_lag.abs().sum(axis=1).replace(0, np.nan)
        scale = (max_gross_exposure / gross_now).clip(upper=1.0).fillna(1.0)
        port_ret = port_ret * scale

    equity = (1 + port_ret).cumprod()

    return BacktestResult(
        daily_returns=port_ret,
        equity=equity,
        positions=weights_lag,
        metrics={},
    )
