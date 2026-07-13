"""Minimal crypto OHLCV loaders for the Cursor Lab wrapper (no full TheQuantGPT app)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "time" in out.columns:
        out["time"] = pd.to_datetime(out["time"], utc=True)
        out = out.set_index("time")
    if out.index.tz is None:
        out.index = out.index.tz_localize("UTC")
    else:
        out.index = out.index.tz_convert("UTC")
    missing = [c for c in OHLCV_COLUMNS if c not in out.columns]
    if missing:
        raise ValueError(f"OHLCV frame missing columns: {missing}")
    return out.sort_index()


def load_symbol_from_parquet(
    path: Path | str,
    symbol: str,
    *,
    interval: str | None = None,
) -> pd.DataFrame:
    """Load one symbol from a long-format Binance futures parquet file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    df = pd.read_parquet(p)
    if "asset" in df.columns:
        mask = df["asset"].astype(str).str.upper() == symbol.upper()
        df = df.loc[mask]
    elif "symbol" in df.columns:
        mask = df["symbol"].astype(str).str.upper() == symbol.upper()
        df = df.loc[mask]
    else:
        raise ValueError(f"{p} has no asset/symbol column for filtering")
    if interval and "interval" in df.columns:
        df = df.loc[df["interval"].astype(str) == interval]
    if df.empty:
        raise ValueError(f"No rows for {symbol} in {p}")
    return _normalize_ohlcv(df)


def load_symbol_close(
    path: Path | str,
    symbol: str,
    *,
    interval: str | None = "1d",
) -> pd.Series:
    frame = load_symbol_from_parquet(path, symbol, interval=interval)
    return frame["close"].astype(float)
