"""Funding rate overlay for triangular pairs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import DATA_DIR

FUNDING_PATH = DATA_DIR / "coinglass" / "futures_funding_rate_binance_1d.parquet"
FUNDING_PCT_TO_DECIMAL = 1.0 / 100.0


def load_daily_funding() -> pd.DataFrame:
    path = FUNDING_PATH
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    panel = (
        df.pivot_table(index="date", columns="symbol", values="close", aggfunc="last")
        .sort_index()
        .apply(pd.to_numeric, errors="coerce")
        * FUNDING_PCT_TO_DECIMAL
    )
    return panel


def funding_tilt(
    weights: pd.DataFrame,
    funding: pd.DataFrame,
    *,
    strength: float = 0.15,
) -> pd.DataFrame:
    """Tilt weights toward collecting positive funding (short high-funding names)."""
    if funding.empty:
        return weights
    common_idx = weights.index.intersection(funding.index)
    common_cols = weights.columns.intersection(funding.columns)
    if common_idx.empty or common_cols.empty:
        return weights

    out = weights.copy()
    f = funding.reindex(common_idx)[common_cols].shift(1)
    w = weights.reindex(common_idx)[common_cols]
    # Reduce long exposure on high positive funding; increase short tilt.
    tilt = -strength * f.clip(-0.001, 0.001) / 0.001
    out.loc[common_idx, common_cols] = w * (1.0 + tilt * np.sign(w))
    return out
