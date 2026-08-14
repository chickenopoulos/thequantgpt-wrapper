"""Enhanced backtest with regime gating, diversification, vol scaling, funding."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import BacktestResult, compute_metrics
from .config import ANN_FACTOR, COST_PER_LEG, LAG_BARS
from .data import log_prices
from .funding import funding_tilt, load_daily_funding
from .regime import corr_quintile, low_corr_gate, portfolio_vol_scale, rolling_mean_pairwise_corr
from .signals import zscore_positions
from .triangles import Triangle, rolling_triangle_residual


def select_diverse_triangles(
    ranked: pd.DataFrame,
    n: int,
    *,
    max_per_target: int = 1,
) -> list[Triangle]:
    """Pick top triangles with at most `max_per_target` per target asset."""
    chosen: list[Triangle] = []
    target_counts: dict[str, int] = {}
    for row in ranked.itertuples():
        if len(chosen) >= n:
            break
        if target_counts.get(row.target, 0) >= max_per_target:
            continue
        chosen.append(Triangle(target=row.target, leg1=row.leg1, leg2=row.leg2))
        target_counts[row.target] = target_counts.get(row.target, 0) + 1
    return chosen


def backtest_enhanced(
    close: pd.DataFrame,
    triangles: list[Triangle],
    *,
    window: int = 120,
    min_periods: int = 90,
    entry_z: float = 2.5,
    exit_z: float = 0.5,
    weight_cap: float = 0.20,
    use_corr_gate: bool = True,
    use_vol_scale: bool = True,
    target_vol: float = 0.12,
    use_funding: bool = True,
    funding_strength: float = 0.10,
) -> BacktestResult:
    log_close = log_prices(close)
    asset_returns = close.pct_change()

    # Regime indicators on liquid cross-section.
    liq = close.notna().sum(axis=1)
    liquid_cols = close.columns[close.notna().sum() >= 400]
    rets_liq = close[liquid_cols].pct_change()
    mcorr = rolling_mean_pairwise_corr(rets_liq, window=30)
    quintile = corr_quintile(mcorr)
    gate = low_corr_gate(quintile) if use_corr_gate else pd.Series(1.0, index=close.index)

    triangle_frames: dict[str, pd.DataFrame] = {}
    pos_frames: dict[str, pd.Series] = {}

    for tri in triangles:
        stats = rolling_triangle_residual(log_close, tri, window=window, min_periods=min_periods)
        pos = zscore_positions(stats["zscore"].shift(LAG_BARS), entry=entry_z, exit_=exit_z)
        triangle_frames[tri.key] = stats
        pos_frames[tri.key] = pos

    weights = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    for tri in triangles:
        stats = triangle_frames[tri.key]
        pos = pos_frames[tri.key] * gate
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

    weights_lag = weights.shift(LAG_BARS).fillna(0.0)

    if use_funding:
        funding = load_daily_funding()
        funding.index = pd.to_datetime(funding.index, utc=True)
        weights_lag = funding_tilt(weights_lag, funding, strength=funding_strength)

    gross = weights_lag.abs().sum(axis=1).replace(0, np.nan)
    lev_scale = (1.0 / gross).clip(upper=1.0).fillna(1.0)
    weights_lag = weights_lag.mul(lev_scale, axis=0)

    raw_ret = (weights_lag * asset_returns).sum(axis=1).fillna(0.0)
    if use_vol_scale:
        vol_scale = portfolio_vol_scale(raw_ret, target_vol=target_vol)
        weights_lag = weights_lag.mul(vol_scale, axis=0)
        gross = weights_lag.abs().sum(axis=1).replace(0, np.nan)
        lev_scale = (1.0 / gross).clip(upper=1.0).fillna(1.0)
        weights_lag = weights_lag.mul(lev_scale, axis=0)

    turnover = weights_lag.diff().abs().sum(axis=1).fillna(0.0)
    costs = turnover * COST_PER_LEG
    port_ret = (weights_lag * asset_returns).sum(axis=1) - costs
    port_ret = port_ret.fillna(0.0)
    equity = (1 + port_ret).cumprod()

    return BacktestResult(
        daily_returns=port_ret,
        equity=equity,
        positions=weights_lag,
        metrics={},
    )
