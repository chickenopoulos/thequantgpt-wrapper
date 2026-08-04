"""Load Binance USDT-M perpetual OHLCV panels."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import ANCHORS, FUTURES_DAILY, FUTURES_HOURLY, profile


def _read_parquet_closes(path: Path) -> pd.DataFrame:
    try:
        df = pd.read_parquet(path, columns=["time", "asset", "close"])
        time_col = "time"
    except Exception:
        df = pd.read_parquet(path, columns=["open_time", "asset", "close"])
        time_col = "open_time"
    df["time"] = pd.to_datetime(df[time_col], utc=True)
    return df


def load_close_panel(
    path: Path | None = None,
    *,
    interval: str = "1d",
    min_history: int | None = None,
    assets: list[str] | None = None,
    start: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Return wide close-price panel indexed by UTC time."""
    if path is None:
        path = FUTURES_DAILY if interval == "1d" else FUTURES_HOURLY
    if min_history is None:
        min_history = profile(interval)["min_history"]

    df = _read_parquet_closes(path)
    if assets is not None:
        keep = set(assets) | set(ANCHORS)
        df = df[df["asset"].isin(keep)]
    if start is not None:
        df = df[df["time"] >= start]

    close = (
        df.pivot_table(index="time", columns="asset", values="close", aggfunc="last")
        .sort_index()
        .astype(float)
    )
    counts = close.notna().sum()
    valid = counts[counts >= min_history].index
    return close[valid]


def liquid_universe(close: pd.DataFrame, top_n: int) -> list[str]:
    counts = close.notna().sum().sort_values(ascending=False)
    liquid = counts.head(top_n).index.tolist()
    for a in ANCHORS:
        if a in close.columns and a not in liquid:
            liquid.append(a)
    return liquid


def log_prices(close: pd.DataFrame) -> pd.DataFrame:
    out = close.replace(0, np.nan).astype(float)
    return np.log(out)


def resample_to_daily(hourly_returns: pd.Series) -> pd.Series:
    """Compound hourly returns into daily bars (for cross-interval comparison)."""
    return hourly_returns.resample("1D").apply(lambda x: (1 + x).prod() - 1).dropna()
