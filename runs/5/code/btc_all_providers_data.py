"""Load and align all BTC research features from every data provider."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from tqg_client.market_data import load_market_data, load_symbol_from_parquet
from tqg_client.strategy_sweep_core import LAG, align_to_close, load_btc_talos_metrics, load_coinglass_daily

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "data"


def _read_cg_parquet(name: str, value_col: str | None = None, symbol: str = "BTCUSDT") -> pd.Series:
    path = DATA / "coinglass" / name
    if not path.exists():
        return pd.Series(dtype=float)
    df = pd.read_parquet(path)
    if "date" in df.columns:
        df.index = pd.to_datetime(df["date"], utc=True)
    elif "time" in df.columns:
        df.index = pd.to_datetime(df["time"], utc=True)
    if "symbol" in df.columns:
        sym = df["symbol"].astype(str).str.upper()
        if symbol.upper() in sym.values:
            df = df[sym == symbol.upper()]
        elif "BTC" in symbol.upper():
            df = df[sym.str.contains("BTC", na=False)]
    if value_col and value_col in df.columns:
        s = df[value_col].astype(float)
    elif name.startswith("exchange_balance"):
        s = df.select_dtypes(include="number").sum(axis=1).astype(float)
    else:
        for c in ("close", "close_basis", "whale_index_value", "flow_usd", "value"):
            if c in df.columns:
                s = df[c].astype(float)
                break
        else:
            num = df.select_dtypes(include="number")
            s = num.iloc[:, 0].astype(float) if not num.empty else pd.Series(dtype=float)
    return s.groupby(s.index).last().sort_index()


def load_all_features() -> tuple[pd.DataFrame, dict, str]:
    """Return (ohlcv_df, features dict, primary_source_label)."""
    ohlcv, source = load_market_data("BTCUSDT", data_dir=DATA, interval="1d")
    ohlcv = ohlcv.sort_index()
    idx = ohlcv.index
    close = ohlcv["close"].astype(float)
    high = ohlcv["high"].astype(float)
    low = ohlcv["low"].astype(float)
    vol = ohlcv["volume"].astype(float)

    f: dict[str, pd.Series] = {}
    f["close"] = close
    f["high"] = high
    f["low"] = low
    f["volume"] = vol

    # --- Talos on-chain metrics (149 cols) ---
    talos = load_btc_talos_metrics()
    for col in talos.select_dtypes(include="number").columns:
        s = talos[col].astype(float)
        if s.notna().mean() >= 0.5:
            f[f"talos_{col}"] = align_to_close(s, idx)

    # --- Coinglass daily (all BTC-relevant) ---
    cg_files = [
        ("puell_multiple.csv", "puell_multiple", None),
        ("futures_funding_rate_binance_1d.parquet", None, "close"),
        ("futures_funding_rate_oi_weight_binance_1d.parquet", None, "close"),
        ("futures_funding_rate_vol_weight_binance_1d.parquet", None, "close"),
        ("futures_open_interest_history_ohlc_binance_1d.parquet", None, "close"),
        ("futures_liquidations_binance_1d.parquet", None, "long_liquidation_usd"),
        ("futures_basis_binance_1d.parquet", None, "close_basis"),
        ("futures_taker_buy_sell_history_binance_1d.parquet", None, None),
        ("futures_orderbook_pair_binance_1d.parquet", None, None),
        ("futures_net_position_v2_binance_1d.parquet", None, "net_long_change"),
        ("futures_global_account_long_short_ratio_binance_1d.parquet", None, "long_short_ratio"),
        ("indic_whale_index_binance_1d.parquet", None, "whale_index_value"),
        ("etf_flows_btc.parquet", None, "flow_usd"),
        ("etf_premium_discount_btc.parquet", None, "premium_discount"),
        ("etf_net_assets_btc.parquet", None, "net_assets_usd"),
        ("exchange_balance_btc.parquet", None, None),
        ("spot_orderbook_binance_1d.parquet", None, None),
        ("spot_taker_buy_sell_history_binance_1d.parquet", None, None),
    ]
    for fname, csv_col, pcol in cg_files:
        try:
            if fname.endswith(".csv"):
                s = load_coinglass_daily(fname, csv_col or "puell_multiple")
            else:
                s = _read_cg_parquet(fname, pcol)
            if s is not None and not s.empty:
                key = "cg_" + fname.replace(".parquet", "").replace(".csv", "")
                f[key] = align_to_close(s, idx)
        except Exception:
            pass

    # Derived Coinglass
    if "cg_futures_taker_buy_sell_history_binance_1d" in f:
        # reload for ratio
        taker = _read_cg_parquet("futures_taker_buy_sell_history_binance_1d.parquet")
        tb = align_to_close(taker, idx) if False else None
    taker_df = pd.read_parquet(DATA / "coinglass" / "futures_taker_buy_sell_history_binance_1d.parquet")
    taker_df.index = pd.to_datetime(taker_df["date"], utc=True)
    sym = taker_df["symbol"].astype(str).str.upper()
    taker_df = taker_df[sym.str.contains("BTC", na=False)]
    buy = align_to_close(taker_df["taker_buy_volume_usd"].astype(float), idx)
    sell = align_to_close(taker_df["taker_sell_volume_usd"].astype(float), idx)
    f["cg_taker_buy_ratio"] = buy / (buy + sell)

    ob = pd.read_parquet(DATA / "coinglass" / "futures_orderbook_pair_binance_1d.parquet")
    ob.index = pd.to_datetime(ob["date"], utc=True)
    ob = ob[ob["symbol"].astype(str).str.upper() == "BTCUSDT"]
    imb = (ob["bids_usd"] - ob["asks_usd"]) / (ob["bids_usd"] + ob["asks_usd"])
    f["cg_ob_imbalance"] = align_to_close(imb.astype(float), idx)

    spot_ob = pd.read_parquet(DATA / "coinglass" / "spot_orderbook_binance_1d.parquet")
    spot_ob.index = pd.to_datetime(spot_ob["date"], utc=True)
    spot_ob = spot_ob[spot_ob["symbol"].astype(str).str.upper() == "BTCUSDT"]
    if "bids_usd" in spot_ob.columns:
        spot_imb = (spot_ob["bids_usd"] - spot_ob["asks_usd"]) / (spot_ob["bids_usd"] + spot_ob["asks_usd"])
        f["cg_spot_ob_imbalance"] = align_to_close(spot_imb.astype(float), idx)

    # Short liq
    liq_df = pd.read_parquet(DATA / "coinglass" / "futures_liquidations_binance_1d.parquet")
    liq_df.index = pd.to_datetime(liq_df["date"], utc=True)
    liq_df = liq_df[liq_df["symbol"].astype(str).str.upper().str.contains("BTC")]
    if "short_liquidation_usd" in liq_df.columns:
        f["cg_short_liq"] = align_to_close(liq_df["short_liquidation_usd"].astype(float), idx)
    if "long_liquidation_usd" in liq_df.columns:
        f["cg_long_liq"] = align_to_close(liq_df["long_liquidation_usd"].astype(float), idx)

    # --- Binance futures OHLCV (alternate venue) ---
    try:
        bn = load_symbol_from_parquet(DATA / "binance" / "binance_futures_ohlcv_1d.parquet", "BTCUSDT")
        bn = bn.sort_index()
        bn_close = bn["close"].astype(float)
        f["binance_close"] = align_to_close(bn_close, idx)
        f["binance_talos_basis"] = align_to_close(bn_close / bn_close * close / bn_close.reindex(idx, method="ffill") - 1, idx)
        # proper basis: talos vs binance
        bn_al = bn_close.reindex(idx, method="ffill")
        f["venue_spread_bn_talos"] = align_to_close((close - bn_al) / bn_al, idx)
    except Exception:
        pass

    # --- Hyperliquid OHLCV ---
    try:
        hl = pd.read_parquet(DATA / "hyperliquid" / "hyperliquid_futures_ohlcv_1d.parquet")
        hl = hl[hl["symbol"].astype(str).str.upper() == "BTC"].sort_values("open_time")
        hl.index = pd.to_datetime(hl["open_time"], utc=True)
        hl_close = hl["close"].astype(float)
        hl_al = hl_close.reindex(idx, method="ffill")
        f["hyperliquid_close"] = align_to_close(hl_close, idx)
        f["venue_spread_hl_talos"] = align_to_close((close - hl_al) / hl_al, idx)
        if "binance_close" in f:
            bn_al = f["binance_close"]
            f["venue_spread_hl_bn"] = align_to_close((hl_al - bn_al) / bn_al, idx)
    except Exception:
        pass

    # --- Price-derived ---
    log_p = np.log(close)
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean()
    f["ma50"] = close.rolling(50).mean().shift(LAG)
    f["ma100"] = close.rolling(100).mean().shift(LAG)
    f["ma150"] = close.rolling(150).mean().shift(LAG)
    f["ma200"] = close.rolling(200).mean().shift(LAG)
    f["cmma40"] = ((log_p - log_p.rolling(40).mean()) / atr14).shift(LAG)
    f["mom126"] = close.pct_change(126).shift(LAG)
    f["mom21"] = close.pct_change(21).shift(LAG)

    meta = {
        "source": source,
        "n_features": len(f),
        "providers": ["talos", "coinglass", "binance", "hyperliquid"],
        "date_range": [str(idx.min()), str(idx.max())],
    }
    return ohlcv, f, meta
