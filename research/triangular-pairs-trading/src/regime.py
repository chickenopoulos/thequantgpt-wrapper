"""Market regime indicators for triangular pairs gating."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_mean_pairwise_corr(returns: pd.DataFrame, window: int = 30) -> pd.Series:
    """Average pairwise correlation across universe."""
    values = returns.to_numpy(dtype=float)
    index = returns.index
    out = np.full(len(index), np.nan)
    for i in range(window, len(index)):
        block = values[i - window : i]
        valid_cols = np.sum(~np.isnan(block), axis=0) >= window
        if valid_cols.sum() < 5:
            continue
        block = block[:, valid_cols]
        corr = np.corrcoef(block, rowvar=False)
        upper = corr[np.triu_indices(corr.shape[0], k=1)]
        if upper.size:
            out[i] = upper.mean()
    return pd.Series(out, index=index, name="market_corr")


def corr_quintile(corr: pd.Series, min_periods: int = 120) -> pd.Series:
    lagged = corr.shift(1)
    ranks = lagged.expanding(min_periods=min_periods).rank(pct=True)
    return np.ceil(ranks * 5).clip(1, 5).rename("corr_quintile")


def low_corr_gate(quintile: pd.Series, allowed: tuple[int, ...] = (1, 2)) -> pd.Series:
    """1 when allowed to trade, 0 otherwise."""
    return quintile.isin(allowed).astype(float).rename("trade_gate")


def portfolio_vol_scale(returns: pd.Series, target_vol: float = 0.10, window: int = 60) -> pd.Series:
    """Scale factor to target annualized vol using trailing realized vol."""
    ann = 365
    roll = returns.rolling(window, min_periods=window // 2).std() * np.sqrt(ann)
    scale = (target_vol / roll).clip(upper=1.5).fillna(1.0)
    return scale.shift(1).fillna(1.0).rename("vol_scale")
