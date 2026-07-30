"""Load BTCUSDT intraday OHLCV and build lag-safe feature panels."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from tqg_client.strategy_sweep_core import LAG, align_to_close, atr, efficiency_ratio

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "data"


def load_btc_ohlcv(interval: str = "1h") -> pd.DataFrame:
    path = DATA / "binance" / "BTCUSDT_1h.parquet"
    df = pd.read_parquet(path)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.sort_values("time").drop_duplicates("time")
    df = df.set_index("time")
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = df[c].astype(float)

    if interval == "1h":
        return df

    rule = {"4h": "4h", "8h": "8h", "12h": "12h", "1d": "1D"}[interval]
    ohlc = df.resample(rule).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    return ohlc


def _lag(s: pd.Series) -> pd.Series:
    return s.shift(LAG)


def build_price_features(df: pd.DataFrame) -> dict[str, pd.Series]:
    close = df["close"]
    high = df["high"]
    low = df["low"]
    vol = df["volume"]
    log_p = np.log(close)
    ret1 = close.pct_change()

    f: dict[str, pd.Series] = {}
    f["close"] = close
    f["high"] = high
    f["low"] = low
    f["volume"] = vol

    a14 = atr(high, low, close, 14)
    f["atr14"] = _lag(a14)

    for w in (20, 50, 100, 200):
        f[f"ma{w}"] = _lag(close.rolling(w).mean())
    for w in (12, 20, 24, 48, 50, 96, 100, 200):
        f[f"ema{w}"] = _lag(close.ewm(span=w, adjust=False).mean())

    for w in (10, 14, 20, 30):
        delta = close.diff()
        up = delta.clip(lower=0).rolling(w).mean()
        down = (-delta.clip(upper=0)).rolling(w).mean()
        rsi = 100 - 100 / (1 + up / down.replace(0, np.nan))
        f[f"rsi{w}"] = _lag(rsi)

    for w in (20, 40, 55):
        std = close.rolling(w).std()
        ma = close.rolling(w).mean()
        f[f"bb_upper_{w}"] = _lag(ma + 2 * std)
        f[f"bb_lower_{w}"] = _lag(ma - 2 * std)
        f[f"bb_mid_{w}"] = _lag(ma)
        f[f"bb_width_{w}"] = _lag((4 * std) / ma.replace(0, np.nan))

    for w in (20, 55, 100):
        f[f"don_high_{w}"] = _lag(high.rolling(w).max())
        f[f"don_low_{w}"] = _lag(low.rolling(w).min())

    for w in (12, 20, 40):
        f[f"er{w}"] = _lag(efficiency_ratio(close, w))

    for w in (5, 10, 20, 24, 40, 48, 96):
        f[f"mom{w}"] = _lag(close.pct_change(w))
        f[f"vol{w}"] = _lag(ret1.rolling(w).std())

    # Intraday seasonality (hour-of-day) — only meaningful on 1h bars
    if len(df) > 5000 and (df.index[1] - df.index[0]).total_seconds() <= 3700:
        hod = pd.Series(df.index.hour, index=df.index)
        f["hour"] = hod.shift(LAG)

    # Z-score of returns (lag-safe: stats exclude current bar)
    for w in (48, 96, 168):
        mu = ret1.rolling(w).mean().shift(LAG)
        sig = ret1.rolling(w).std().shift(LAG)
        f[f"ret_z{w}"] = _lag((ret1 - mu) / sig.replace(0, np.nan))

    # Volume spike
    for w in (24, 48, 96):
        f[f"vol_ratio{w}"] = _lag(vol / vol.rolling(w).mean().replace(0, np.nan))

    return f


def load_coinglass_1h_feature(name: str, value_col: str, idx: pd.DatetimeIndex) -> pd.Series | None:
    path = DATA / "coinglass" / name
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    if df.empty:
        return None
    if "date" in df.columns:
        df.index = pd.to_datetime(df["date"], utc=True)
    elif "time" in df.columns:
        df.index = pd.to_datetime(df["time"], utc=True)
    if "symbol" in df.columns:
        sym = df["symbol"].astype(str).str.upper()
        if (sym == "BTCUSDT").any():
            df = df[sym == "BTCUSDT"]
        else:
            df = df[sym.str.contains("BTC", na=False)]
    if value_col not in df.columns:
        return None
    s = df[value_col].astype(float).groupby(df.index).last().sort_index()
    return align_to_close(s, idx)


def build_all_features(interval: str = "4h") -> tuple[pd.DataFrame, dict[str, pd.Series], dict]:
    df = load_btc_ohlcv(interval)
    f = build_price_features(df)
    idx = df.index

    # Coinglass 1h alt-data (short history — tagged separately)
    cg_specs = [
        ("futures_funding_rate_binance_1h.parquet", "close", "cg_funding"),
        ("futures_liquidations_binance_1h.parquet", "short_liquidation_usd", "cg_short_liq"),
        ("futures_taker_buy_sell_history_binance_1h.parquet", "taker_buy_volume_usd", "cg_taker_buy"),
        ("futures_global_account_long_short_ratio_binance_1h.parquet", "global_account_long_short_ratio", "cg_ls_ratio"),
        ("futures_orderbook_pair_binance_1h.parquet", "bids_usd", "cg_bids"),
    ]
    cg_loaded = []
    for fname, col, key in cg_specs:
        s = load_coinglass_1h_feature(fname, col, idx)
        if s is not None and s.notna().sum() > 100:
            f[key] = s
            if key == "cg_taker_buy" and "cg_taker_sell" not in f:
                sell = load_coinglass_1h_feature(fname, "taker_sell_volume_usd", idx)
                if sell is not None:
                    f["cg_taker_sell"] = sell
                    f["cg_taker_ratio"] = _lag(
                        f["cg_taker_buy"] / (f["cg_taker_buy"] + f["cg_taker_sell"]).replace(0, np.nan)
                    )
            if key == "cg_bids":
                asks = load_coinglass_1h_feature(fname, "asks_usd", idx)
                if asks is not None:
                    f["cg_ob_imb"] = _lag(
                        (f["cg_bids"] - asks) / (f["cg_bids"] + asks).replace(0, np.nan)
                    )
            cg_loaded.append(key)

    meta = {
        "interval": interval,
        "bars": len(df),
        "date_range": [str(idx.min()), str(idx.max())],
        "coinglass_features": cg_loaded,
    }
    return df, f, meta
