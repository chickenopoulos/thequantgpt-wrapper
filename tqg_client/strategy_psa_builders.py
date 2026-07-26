"""Parameterized signal builders for catalog PSA."""

from __future__ import annotations

import numpy as np
import pandas as pd
import vectorbt as vbt

from tqg_client.market_data import load_symbol_from_parquet
from tqg_client.strategy_sweep_core import (
    DATA,
    LAG,
    align_to_close,
    atr,
    efficiency_ratio,
    load_btc_talos_metrics,
    load_close,
    load_coinglass_daily,
    load_equity_close,
    load_ohlcv,
    SkipStrategy,
)

_CACHE: dict[str, object] = {}


def _btc(interval: str = "1d") -> tuple[pd.DataFrame, pd.Series]:
    key = f"btc_{interval}"
    if key not in _CACHE:
        df, _ = load_ohlcv("BTCUSDT", interval)
        _CACHE[key] = (df, df["close"].astype(float))
    return _CACHE[key]


def _talos(col: str) -> pd.Series:
    key = f"talos_{col}"
    if key not in _CACHE:
        df = load_btc_talos_metrics()
        if col not in df.columns:
            raise SkipStrategy(f"Talos column {col} missing")
        _CACHE[key] = df[col].astype(float)
    return _CACHE[key]


def _cg(path: str, value_col: str = "close") -> pd.Series:
    key = f"cg_{path}_{value_col}"
    if key not in _CACHE:
        _CACHE[key] = load_coinglass_daily(path, value_col)
    return _CACHE[key]


def _sig(
    close: pd.Series,
    entries: pd.Series,
    exits: pd.Series,
    short_entries: pd.Series | None = None,
    short_exits: pd.Series | None = None,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series | None, pd.Series | None]:
    return close, entries, exits, short_entries, short_exits


def t01(p: dict) -> tuple:
    _, close = _btc()
    fast, slow = int(p["fast_ma"]), int(p["slow_ma"])
    ma_f = close.rolling(fast).mean().shift(LAG)
    ma_s = close.rolling(slow).mean().shift(LAG)
    return _sig(close, (ma_f > ma_s).fillna(False), (ma_f < ma_s).fillna(False))


def t02(p: dict) -> tuple:
    df, close = _btc()
    k = int(p["lookback"])
    log_p = np.log(close)
    ma = log_p.rolling(k).mean()
    a = atr(df["high"], df["low"], close)
    cmma = ((log_p - ma) / a).shift(LAG)
    return _sig(close, (cmma > 0).fillna(False), (cmma < 0).fillna(False))


def t03(p: dict) -> tuple:
    df, close = _btc()
    n = int(p["lookback"])
    hi = df["high"].rolling(n).max().shift(LAG)
    lo = df["low"].rolling(n // 2).min().shift(LAG)
    return _sig(close, (close.shift(LAG) > hi.shift(1)).fillna(False), (close.shift(LAG) < lo.shift(1)).fillna(False))


def t04(p: dict) -> tuple:
    df, close = _btc()
    n = int(p["lookback"])
    er = efficiency_ratio(close, n).shift(LAG)
    hi = df["high"].rolling(n).max().shift(LAG)
    lo = df["low"].rolling(n // 2).min().shift(LAG)
    gate = (er < float(p["er_max"])).fillna(False)
    return _sig(close, gate & (close.shift(LAG) > hi.shift(1)).fillna(False), (close.shift(LAG) < lo.shift(1)).fillna(False))


def t05(p: dict) -> tuple:
    _, close = _btc()
    skip = int(p["skip_days"])
    mom = close.pct_change(252 - skip).shift(LAG)
    return _sig(close, (mom > 0).fillna(False), (mom <= 0).fillna(False))


def t06(p: dict) -> tuple:
    _, close = _btc()
    w = int(p["rank_window"])
    ret = close.pct_change(20)
    rank = ret.rolling(w).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
    r = rank.shift(LAG)
    return _sig(close, (r > float(p["entry_rank"])).fillna(False), (r < float(p["exit_rank"])).fillna(False))


def t08(p: dict) -> tuple:
    _, close = _btc()
    mom = close.pct_change(231).shift(LAG)
    vol = close.pct_change().rolling(90).std()
    gate = (vol < vol.rolling(int(p["vol_window"])).median()).shift(LAG).fillna(False)
    return _sig(close, gate & (mom > 0).fillna(False), (~gate) | (mom <= 0).fillna(False))


def t09(p: dict) -> tuple:
    _, close = _btc()
    hi252 = close.rolling(252).max().shift(LAG)
    prox = (close.shift(LAG) / hi252 - 1).abs()
    return _sig(close, (prox < float(p["entry_prox"])).fillna(False), (prox > float(p["exit_prox"])).fillna(False))


def t10(p: dict) -> tuple:
    qclose = load_symbol_from_parquet(
        DATA / "binance" / "binance_futures_ohlcv_1d.parquet", "QQQUSDT"
    )["close"].astype(float)
    bclose = load_close("BTCUSDT")
    idx = qclose.index.intersection(bclose.index)
    qclose, bclose = qclose.reindex(idx), bclose.reindex(idx)
    n = int(p["lookback"])
    q_br = (qclose > qclose.rolling(n).max().shift(1)).shift(LAG)
    b_br = (bclose > bclose.rolling(n).max().shift(1)).shift(LAG)
    q_strength = qclose.pct_change(n).shift(LAG)
    b_strength = bclose.pct_change(n).shift(LAG)
    hold_q = q_br & (q_strength >= b_strength)
    hold_b = b_br & (b_strength > q_strength)
    entries = hold_b.fillna(False)
    exits = (~hold_b & ~hold_q).fillna(False) | hold_q.fillna(False)
    return _sig(bclose, entries, exits)


def t13(p: dict) -> tuple:
    bclose = load_close("BTCUSDT")
    eclose = load_close("ETHUSDT")
    idx = bclose.index.intersection(eclose.index)
    w = int(p["lookback"])
    sig = (bclose.pct_change(w).shift(LAG + 1) > 0).reindex(idx).fillna(False)
    entries = sig.reindex(eclose.index).fillna(False)
    return _sig(eclose, entries, ~entries)


def t14(p: dict) -> tuple:
    try:
        close = load_close("EURUSD=X")
    except Exception:
        close = load_equity_close("EURUSD=X")
    fast = close.rolling(int(p["fast_ma"])).mean().shift(LAG)
    slow = close.rolling(int(p["slow_ma"])).mean().shift(LAG)
    return _sig(close, (fast > slow).fillna(False), (fast < slow).fillna(False))


def mr01(p: dict) -> tuple:
    _, close = _btc()
    w = int(p["window"])
    mult = float(p["std_mult"])
    ma = close.rolling(w).mean()
    std = close.rolling(w).std()
    lower = ma - mult * std
    return _sig(close, (close.shift(LAG) < lower.shift(LAG)).fillna(False), (close.shift(LAG) > ma.shift(LAG)).fillna(False))


def mr02(p: dict) -> tuple:
    _, close = _btc()
    rsi = vbt.RSI.run(close, window=int(p["rsi_window"])).rsi.shift(LAG)
    return _sig(close, (rsi < float(p["oversold"])).fillna(False), (rsi > float(p["exit_rsi"])).fillna(False))


def mr03(p: dict) -> tuple:
    _, close = _btc()
    rsi = vbt.RSI.run(close, window=int(p["rsi_window"])).rsi.shift(LAG)
    er = efficiency_ratio(close, int(p["er_window"])).shift(LAG)
    entries = (er > float(p["er_min"])) & (rsi < float(p["oversold"])).fillna(False)
    return _sig(close, entries, (rsi > float(p["exit_rsi"])).fillna(False))


def mr04(p: dict) -> tuple:
    _, close = _btc()
    w = int(p["window"])
    ma = close.rolling(w).mean()
    z = ((close - ma) / close.rolling(w).std()).shift(LAG)
    return _sig(close, (z < -float(p["z_entry"])).fillna(False), (z > 0).fillna(False))


def mr05(p: dict) -> tuple:
    df, close = _btc("1h")
    open_ = df["open"].astype(float)
    gap = (open_ - close.shift(1)) / close.shift(1)
    thr = float(p["gap_thr"])
    return _sig(close, (gap.shift(LAG) < thr).fillna(False), (gap.shift(LAG) > 0).fillna(False))


def mr06(p: dict) -> tuple:
    _, close = _btc()
    ret = close.pct_change().shift(LAG)
    std = close.pct_change().rolling(int(p["window"])).std().shift(LAG)
    return _sig(close, (ret < -float(p["std_mult"]) * std).fillna(False), (ret > 0).fillna(False))


def mr10(p: dict) -> tuple:
    b = load_close("BTCUSDT")
    e = load_close("ETHUSDT")
    idx = b.index.intersection(e.index)
    spread = b.reindex(idx) / e.reindex(idx)
    w = int(p["window"])
    z = ((spread - spread.rolling(w).mean()) / spread.rolling(w).std()).shift(LAG)
    return _sig(b.reindex(idx), (z < -float(p["z_entry"])).fillna(False), (z > 0).fillna(False))


def mr11(p: dict) -> tuple:
    _, close = _btc()
    w = int(p["detrend_window"])
    ma = close.rolling(w).mean()
    detrended = (close - ma).shift(LAG)
    rsi = vbt.RSI.run(detrended, window=int(p["rsi_window"])).rsi
    return _sig(close, (rsi < float(p["oversold"])).fillna(False), (rsi > float(p["exit_rsi"])).fillna(False))


def mr12(p: dict) -> tuple:
    df, close = _btc("1h")
    overnight = (df["open"] - close.shift(1)) / close.shift(1)
    thr = float(p["overnight_thr"])
    return _sig(close, (overnight.shift(LAG) < thr).fillna(False), (overnight.shift(LAG) > 0).fillna(False))


def mr13(p: dict) -> tuple:
    _, close = _btc("1h")
    ret24 = close.pct_change(24).shift(LAG)
    return _sig(close, (ret24 < float(p["fade_thr"])).fillna(False), (ret24 > float(p["exit_thr"])).fillna(False))


def mr14(p: dict) -> tuple:
    df, close = _btc()
    ret = close.pct_change().shift(LAG)
    vol_med = df["volume"].rolling(int(p["vol_window"])).median().shift(LAG)
    low_vol = df["volume"].shift(LAG) < vol_med
    std = close.pct_change().rolling(int(p["ret_window"])).std().shift(LAG)
    return _sig(close, low_vol & (ret > std).fillna(False), (ret < 0).fillna(False))


def mr15(p: dict) -> tuple:
    close = load_equity_close("QQQ")
    rsi = vbt.RSI.run(close, window=int(p["rsi_window"])).rsi.shift(LAG)
    ma = close.rolling(int(p["trend_ma"])).mean().shift(LAG)
    entries = (rsi < float(p["oversold"])) & (close.shift(LAG) > ma).fillna(False)
    return _sig(close, entries, (rsi > float(p["exit_rsi"])).fillna(False))


def v03(p: dict) -> tuple:
    _, close = _btc()
    vol = close.pct_change().rolling(int(p["vol_window"])).std()
    tercile = vol.rolling(int(p["vol_window"])).apply(
        lambda x: pd.qcut(x, 3, labels=False, duplicates="drop").iloc[-1] if len(x) > 10 else 1,
        raw=False,
    )
    low = (tercile.shift(LAG) == 0).fillna(False)
    mom = (close.pct_change(int(p["mom_window"])).shift(LAG) > 0).fillna(False)
    return _sig(close, low & mom, ~low | ~mom)


def v07(p: dict) -> tuple:
    _, close = _btc()
    vol = close.pct_change().rolling(20).std()
    forecast = vol.rolling(int(p["forecast_window"])).mean().shift(LAG)
    gate = (forecast < vol.shift(LAG)).fillna(False)
    mom = (close.pct_change(int(p["mom_window"])).shift(LAG) > 0).fillna(False)
    return _sig(close, gate & mom, ~gate | ~mom)


def v08(p: dict) -> tuple:
    _, close = _btc()
    sign = np.sign(close.pct_change().fillna(0))
    w = int(p["entropy_window"])
    p_up = sign.rolling(w).apply(lambda x: (x > 0).mean(), raw=True)
    ent = -p_up * np.log(p_up + 1e-9) - (1 - p_up) * np.log(1 - p_up + 1e-9)
    high_ent = (ent.shift(LAG) > float(p["entropy_thr"])).fillna(False)
    rsi = vbt.RSI.run(close, window=int(p["rsi_window"])).rsi.shift(LAG)
    return _sig(close, high_ent & (rsi < float(p["oversold"])).fillna(False), (rsi > float(p["exit_rsi"])).fillna(False))


def taa01(p: dict) -> tuple:
    spy = load_equity_close("SPY")
    ma = spy.rolling(int(p["ma_window"])).mean().shift(LAG)
    return _sig(spy, (spy.shift(LAG) > ma).fillna(False), (spy.shift(LAG) < ma).fillna(False))


def taa05(p: dict) -> tuple:
    spy = load_equity_close("SPY")
    tlt = load_equity_close("TLT")
    idx = spy.index.intersection(tlt.index)
    spy, tlt = spy.reindex(idx), tlt.reindex(idx)
    yield_down = tlt.pct_change(int(p["bond_window"])).shift(LAG) > 0
    return _sig(spy, yield_down.fillna(False), ~yield_down.fillna(False))


def taa06(p: dict) -> tuple:
    gld = load_equity_close("GLD")
    tlt = load_equity_close("TLT")
    idx = gld.index.intersection(tlt.index)
    gld, tlt = gld.reindex(idx), tlt.reindex(idx)
    w1, w2 = int(p["bond_window"]), int(p["gold_window"])
    entries = ((tlt.pct_change(w1).shift(LAG) > 0) & (gld.pct_change(w2).shift(LAG) > 0)).fillna(False)
    return _sig(gld, entries, ~entries)


def taa07(p: dict) -> tuple:
    btc = load_close("BTCUSDT")
    spy = load_equity_close("SPY")
    idx = btc.index.intersection(spy.index)
    btc, spy = btc.reindex(idx), spy.reindex(idx)
    risk_on = spy.pct_change(int(p["spy_window"])).shift(LAG) > 0
    return _sig(btc, risk_on.fillna(False), ~risk_on.fillna(False))


def cg01(p: dict) -> tuple:
    fund = _cg("futures_funding_rate_binance_1d.parquet")
    _, close = _btc()
    f = align_to_close(fund, close.index)
    thr = float(p["fund_thr"])
    return _sig(close, (f < thr).fillna(False), (f > 0).fillna(False))


def cg02(p: dict) -> tuple:
    fund = _cg("futures_funding_rate_binance_1d.parquet")
    _, close = _btc()
    f = align_to_close(fund, close.index)
    w = int(p["quantile_window"])
    hi = (f > f.rolling(w).quantile(float(p["hi_quantile"]))).fillna(False)
    exits = (f < f.rolling(w).median()).fillna(False)
    return _sig(close, hi.fillna(False), exits, hi.fillna(False), exits)


def cg03(p: dict) -> tuple:
    oi = _cg("futures_open_interest_history_ohlc_binance_1d.parquet", "close")
    df, close = _btc()
    o = align_to_close(oi.diff(int(p["oi_diff"])), close.index)
    price_up = close.pct_change(int(p["price_window"])).shift(LAG) > 0
    return _sig(close, price_up & (o > 0).fillna(False), (o < 0).fillna(False))


def cg04(p: dict) -> tuple:
    oi = _cg("futures_open_interest_history_ohlc_binance_1d.parquet", "close")
    _, close = _btc()
    o = align_to_close(oi.diff(int(p["oi_diff"])), close.index)
    hi = close.rolling(int(p["price_window"])).max().shift(LAG)
    entries = (close.shift(LAG) >= hi) & (o < 0).fillna(False)
    exits = (close.pct_change(int(p["price_window"])).shift(LAG) < 0).fillna(False)
    return _sig(close, entries, exits, entries, exits)


def cg05(p: dict) -> tuple:
    liq = _cg("futures_liquidations_binance_1d.parquet", "long_liquidation_usd")
    _, close = _btc()
    l = align_to_close(liq, close.index)
    spike = (l > l.rolling(int(p["spike_window"])).quantile(float(p["spike_q"]))).shift(LAG).fillna(False)
    exits = (l < l.rolling(int(p["exit_window"])).median()).shift(LAG).fillna(False)
    return _sig(close, spike.fillna(False), exits)


def cg06(p: dict) -> tuple:
    fund = _cg("futures_funding_rate_binance_1d.parquet")
    _, close = _btc()
    f = align_to_close(fund, close.index)
    w = int(p["price_window"])
    price_up = close.pct_change(w).shift(LAG) > 0
    entries = (f < float(p["fund_thr"])) & price_up.fillna(False)
    return _sig(close, entries, (f > 0).fillna(False))


def cg07(p: dict) -> tuple:
    taker = pd.read_parquet(DATA / "coinglass" / "futures_taker_buy_sell_history_binance_1d.parquet")
    taker = taker[taker["symbol"].astype(str).str.upper() == "BTCUSDT"]
    taker.index = pd.to_datetime(taker["date"], utc=True)
    taker["taker_buy_volume_usd"] = pd.to_numeric(taker["taker_buy_volume_usd"], errors="coerce")
    taker["taker_sell_volume_usd"] = pd.to_numeric(taker["taker_sell_volume_usd"], errors="coerce")
    ratio = taker["taker_buy_volume_usd"] / (taker["taker_buy_volume_usd"] + taker["taker_sell_volume_usd"])
    _, close = _btc()
    r = align_to_close(ratio, close.index)
    return _sig(close, (r > float(p["entry_ratio"])).fillna(False), (r < float(p["exit_ratio"])).fillna(False))


def cg08(p: dict) -> tuple:
    ob = pd.read_parquet(DATA / "coinglass" / "futures_orderbook_pair_binance_1d.parquet")
    ob = ob[ob["symbol"].astype(str).str.upper() == "BTCUSDT"]
    ob.index = pd.to_datetime(ob["date"], utc=True)
    imb = (ob["bids_usd"] - ob["asks_usd"]) / (ob["bids_usd"] + ob["asks_usd"])
    _, close = _btc()
    i = align_to_close(imb, close.index)
    return _sig(close, (i > float(p["entry_imb"])).fillna(False), (i < float(p["exit_imb"])).fillna(False))


def cg09(p: dict) -> tuple:
    _, close = _btc()
    mom = (close.pct_change(int(p["mom_window"])).shift(LAG) > 0).fillna(False)
    return _sig(close, mom, ~mom)


def cg12(p: dict) -> tuple:
    flow = _cg("etf_flows_btc.parquet", "flow_usd")
    _, close = _btc()
    f = align_to_close(flow.rolling(int(p["flow_window"])).sum(), close.index)
    return _sig(close, (f > 0).fillna(False), (f < 0).fillna(False))


def cg13(p: dict) -> tuple:
    flow = _cg("etf_flows_btc.parquet", "flow_usd")
    _, close = _btc()
    f = align_to_close(flow.rolling(int(p["flow_window"])).sum(), close.index)
    w = int(p["price_window"])
    price_dn = close.pct_change(w).shift(LAG) < 0
    return _sig(close, price_dn & (f > 0).fillna(False), (f < 0).fillna(False))


def cg15(p: dict) -> tuple:
    bal = _cg("exchange_balance_btc.parquet")
    _, close = _btc()
    d = align_to_close(bal.diff(int(p["diff_window"])), close.index)
    return _sig(close, (d < 0).fillna(False), (d > 0).fillna(False))


def cg16(p: dict) -> tuple:
    puell = _cg("puell_multiple.csv", "puell_multiple")
    _, close = _btc()
    pu = align_to_close(puell, close.index)
    return _sig(close, (pu < float(p["entry_thr"])).fillna(False), (pu > float(p["exit_thr"])).fillna(False))


def cg17(p: dict) -> tuple:
    basis = _cg("futures_basis_binance_1d.parquet", "close_basis")
    _, close = _btc()
    b = align_to_close(basis, close.index)
    w = int(p["median_window"])
    return _sig(close, (b > b.rolling(w).median()).fillna(False), (b < 0).fillna(False))


def cg20(p: dict) -> tuple:
    fund = align_to_close(_cg("futures_funding_rate_binance_1d.parquet"), _btc()[1].index)
    _, close = _btc()
    w = int(p["quantile_window"])
    extreme = (fund > fund.rolling(w).quantile(0.95)) | (fund < fund.rolling(w).quantile(0.05))
    entries = extreme.shift(LAG).fillna(False)
    return _sig(close, entries, ~extreme.shift(LAG).fillna(True))


def on02(p: dict) -> tuple:
    nupl = _talos("NUPL")
    _, close = _btc()
    n = align_to_close(nupl, close.index)
    return _sig(close, (n < float(p["entry_thr"])).fillna(False), (n > float(p["exit_thr"])).fillna(False))


def on04(p: dict) -> tuple:
    mv = _talos("CapMVRVCur")
    _, close = _btc()
    m = align_to_close(mv, close.index)
    return _sig(close, (m < float(p["entry_thr"])).fillna(False), (m > float(p["exit_thr"])).fillna(False))


def on06(p: dict) -> tuple:
    sopr = _talos("SOPR")
    _, close = _btc()
    s = align_to_close(sopr, close.index)
    n = int(p["streak_window"])
    below = (s < 1).rolling(n).sum() >= int(p["streak_min"])
    return _sig(close, below.shift(LAG).fillna(False), (s > 1).fillna(False))


def on09(p: dict) -> tuple:
    adr = _talos("AdrActCnt")
    _, close = _btc()
    w = int(p["diff_window"])
    a = align_to_close(adr.diff(w), close.index)
    return _sig(close, (a > 0).fillna(False), (a < 0).fillna(False))


def na01(p: dict) -> tuple:
    adr = _talos("AdrActCnt")
    _, close = _btc()
    w = int(p["roc_window"])
    roc = align_to_close(adr.pct_change(w), close.index)
    return _sig(close, (roc > 0).fillna(False), (roc < 0).fillna(False))


def na02(p: dict) -> tuple:
    tx = _talos("TxCnt")
    _, close = _btc()
    t = align_to_close(tx, close.index)
    ma = t.rolling(int(p["ma_window"])).mean()
    return _sig(close, (t > ma).shift(LAG).fillna(False), (t < ma).shift(LAG).fillna(False))


def ef01(p: dict) -> tuple:
    bal = _cg("exchange_balance_btc.parquet")
    _, close = _btc()
    w = int(p["diff_window"])
    flow = align_to_close(bal.diff(w), close.index)
    return _sig(close, (flow < 0).fillna(False), (flow > 0).fillna(False))


def ef03(p: dict) -> tuple:
    etf = _cg("etf_flows_btc.parquet", "flow_usd").rolling(int(p["etf_window"])).sum()
    bal = _cg("exchange_balance_btc.parquet").diff(int(p["bal_window"]))
    _, close = _btc()
    e = align_to_close(etf, close.index)
    b = align_to_close(bal, close.index)
    return _sig(close, (e > 0) & (b < 0).fillna(False), (e < 0).fillna(False))


def dv01(p: dict) -> tuple:
    fund = align_to_close(_cg("futures_funding_rate_binance_1d.parquet"), _btc()[1].index)
    w = int(p["cum_window"])
    cum = fund.rolling(w).sum()
    _, close = _btc()
    return _sig(close, (cum.shift(LAG) > 0).fillna(False), (cum.shift(LAG) < 0).fillna(False))


def gf02(p: dict) -> tuple:
    etf = align_to_close(_cg("etf_flows_btc.parquet", "flow_usd"), _btc()[1].index)
    _, close = _btc()
    w = int(p["smooth_window"])
    improving = etf.rolling(w).mean().diff().shift(LAG) > 0
    return _sig(close, improving.fillna(False), ~improving.fillna(False))


def gf08(p: dict) -> tuple:
    df, close = _btc()
    a = atr(df["high"], df["low"], close)
    q = float(p["vol_quantile"])
    low_vol = (a < a.rolling(252).quantile(q)).shift(LAG).fillna(False)
    brk_n = int(p["breakout_window"])
    brk = (close > close.rolling(brk_n).max().shift(1)).shift(LAG).fillna(False)
    entries = low_vol & brk
    exits = (close < close.rolling(int(p["exit_window"])).min().shift(1)).shift(LAG).fillna(False)
    return _sig(close, entries, exits)


def gf10(p: dict) -> tuple:
    score = pd.Series(0, index=_btc()[1].index)
    thr = int(p["score_thr"])
    try:
        mv = align_to_close(_talos("CapMVRVCur"), score.index)
        score += (mv < float(p["mv_thr"])).astype(int)
    except SkipStrategy:
        pass
    try:
        etf = align_to_close(_cg("etf_flows_btc.parquet", "flow_usd").rolling(5).sum(), score.index)
        score += (etf > 0).astype(int)
    except SkipStrategy:
        pass
    try:
        fund = align_to_close(_cg("futures_funding_rate_binance_1d.parquet"), score.index)
        score += (fund.abs() < float(p["fund_abs"])).astype(int)
    except SkipStrategy:
        pass
    _, close = _btc()
    entries = (score >= thr).shift(LAG).fillna(False)
    exits = (score < max(1, thr - 1)).shift(LAG).fillna(False)
    return _sig(close, entries, exits)


def ia01(p: dict) -> tuple:
    b = load_close("BTCUSDT")
    e = load_close("ETHUSDT")
    idx = b.index.intersection(e.index)
    lag = int(p["lag_days"])
    sig = (b.reindex(idx).pct_change(lag).shift(LAG) > 0).reindex(e.index).fillna(False)
    return _sig(e, sig, ~sig)


def ia02(p: dict) -> tuple:
    spy = load_equity_close("SPY")
    btc = load_close("BTCUSDT")
    idx = spy.index.intersection(btc.index)
    w = int(p["spy_window"])
    risk = spy.reindex(idx).pct_change(w).shift(LAG) > 0
    entries = risk.reindex(btc.index).fillna(False)
    return _sig(btc, entries, ~entries)


def ia03(p: dict) -> tuple:
    pax = load_close("PAXGUSDT")
    btc = load_close("BTCUSDT")
    idx = pax.index.intersection(btc.index)
    ratio = pax.reindex(idx) / btc.reindex(idx)
    w = int(p["window"])
    z = ((ratio - ratio.rolling(w).mean()) / ratio.rolling(w).std()).shift(LAG)
    return _sig(btc.reindex(idx), (z > float(p["z_entry"])).fillna(False), (z < 0).fillna(False))


def ia04(p: dict) -> tuple:
    h = load_equity_close("HG=F")
    g = load_equity_close("GLD")
    idx = h.index.intersection(g.index)
    w = int(p["ratio_window"])
    ratio = (h.reindex(idx) / g.reindex(idx)).pct_change(w).shift(LAG)
    btc = load_close("BTCUSDT")
    entries = (ratio > 0).reindex(btc.index).fillna(False)
    return _sig(btc, entries, ~entries)


def ia05(p: dict) -> tuple:
    uso = load_equity_close("USO")
    shock_thr = float(p["shock_thr"])
    shock = (uso.pct_change(int(p["shock_window"])).shift(LAG) > shock_thr).fillna(False)
    btc = load_close("BTCUSDT")
    entries = ~shock.reindex(btc.index).fillna(True)
    exits = shock.reindex(btc.index).fillna(False)
    return _sig(btc, entries, exits)


def ia08(p: dict) -> tuple:
    eth = load_close("ETHUSDT")
    btc = load_close("BTCUSDT")
    idx = eth.index.intersection(btc.index)
    w = int(p["mom_window"])
    e_m = eth.reindex(idx).pct_change(w) / eth.reindex(idx).pct_change().rolling(w).std()
    b_m = btc.reindex(idx).pct_change(w) / btc.reindex(idx).pct_change().rolling(w).std()
    hold_eth = (e_m.shift(LAG) > b_m.shift(LAG)).fillna(False)
    entries = hold_eth.reindex(eth.index).fillna(False)
    return _sig(eth, entries, ~entries)


def ia10(p: dict) -> tuple:
    eth = load_close("ETHUSDT")
    btc = load_close("BTCUSDT")
    idx = eth.index.intersection(btc.index)
    lead_thr = float(p["lead_thr"])
    lead = btc.reindex(idx).pct_change().shift(LAG)
    lag_ret = eth.reindex(idx).pct_change().shift(LAG)
    entries = (lead > lead_thr) & (lag_ret < 0).fillna(False)
    return _sig(eth.reindex(idx), entries, (lag_ret > 0).fillna(False))


def q08(p: dict) -> tuple:
    _, close = _btc()
    w = int(p["window"])
    x = close.pct_change().fillna(0)
    pred = x.rolling(w).mean().shift(LAG)
    signal = (pred > 0).fillna(False)
    return _sig(close, signal, ~signal)


def q09(p: dict) -> tuple:
    _, close = _btc()
    vol = close.pct_change().rolling(int(p["vol_window"])).std()
    high = (vol > vol.rolling(252).median()).shift(LAG).fillna(False)
    mom = (close.pct_change(int(p["mom_window"])).shift(LAG) > 0).fillna(False)
    return _sig(close, ~high & mom, high | ~mom)
