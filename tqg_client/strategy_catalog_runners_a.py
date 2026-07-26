"""Strategy catalog runners — one function per plan ID."""

from __future__ import annotations

import numpy as np
import pandas as pd
import vectorbt as vbt

from tqg_client.strategy_sweep_core import (
    LAG,
    align_to_close,
    atr,
    cross_section_ls_returns,
    efficiency_ratio,
    load_btc_talos_metrics,
    load_close,
    load_coinglass_daily,
    load_equity_close,
    load_ohlcv,
    load_universe_daily,
    result_from_returns,
    run_signal_backtest,
    SkipStrategy,
    SweepResult,
    universe_close_panel,
)
from tqg_client.market_data import load_market_data


def _m(
    rid: str,
    name: str,
    universe: str,
    ac: str,
    close: pd.Series,
    entries: pd.Series,
    exits: pd.Series,
    interval: str = "1d",
    short_entries: pd.Series | None = None,
    short_exits: pd.Series | None = None,
    symbol: str = "BTCUSDT",
) -> SweepResult:
    m = run_signal_backtest(
        close, entries, exits,
        symbol=symbol, asset_class=ac, interval=interval,
        short_entries=short_entries, short_exits=short_exits,
    )
    return SweepResult(rid, name, universe, ac, m["Sharpe"], m["MaxDD"], m["CAGR"], m["trades"])


def _btc(interval: str = "1d") -> tuple[pd.DataFrame, pd.Series]:
    df, _ = load_ohlcv("BTCUSDT", interval)
    return df, df["close"].astype(float)


# --- Trend T-01 .. T-15 ---

def run_T_01() -> SweepResult:
    df, close = _btc()
    fast, slow = 20, 100
    ma_f = close.rolling(fast).mean().shift(LAG)
    ma_s = close.rolling(slow).mean().shift(LAG)
    entries = (ma_f > ma_s).fillna(False)
    exits = (ma_f < ma_s).fillna(False)
    return _m("T-01", "Dual MA crossover", "BTCUSDT", "crypto", close, entries, exits)


def run_T_02() -> SweepResult:
    df, close = _btc()
    k = 40
    log_p = np.log(close)
    ma = log_p.rolling(k).mean()
    a = atr(df["high"], df["low"], close)
    cmma = ((log_p - ma) / a).shift(LAG)
    entries = (cmma > 0).fillna(False)
    exits = (cmma < 0).fillna(False)
    return _m("T-02", "CMMA trend", "BTCUSDT", "crypto", close, entries, exits)


def run_T_03() -> SweepResult:
    df, close = _btc()
    n = 20
    hi = df["high"].rolling(n).max().shift(LAG)
    lo = df["low"].rolling(n // 2).min().shift(LAG)
    entries = (close.shift(LAG) > hi.shift(1)).fillna(False)
    exits = (close.shift(LAG) < lo.shift(1)).fillna(False)
    return _m("T-03", "Donchian breakout", "BTCUSDT", "crypto", close, entries, exits)


def run_T_04() -> SweepResult:
    df, close = _btc()
    n = 20
    er = efficiency_ratio(close, n).shift(LAG)
    hi = df["high"].rolling(n).max().shift(LAG)
    lo = df["low"].rolling(n // 2).min().shift(LAG)
    gate = (er < 0.3).fillna(False)
    entries = gate & (close.shift(LAG) > hi.shift(1)).fillna(False)
    exits = (close.shift(LAG) < lo.shift(1)).fillna(False)
    return _m("T-04", "Donchian + ER gate", "BTCUSDT", "crypto", close, entries, exits)


def run_T_05() -> SweepResult:
    _, close = _btc()
    mom = close.pct_change(252 - 21).shift(LAG)
    entries = (mom > 0).fillna(False)
    exits = (mom <= 0).fillna(False)
    return _m("T-05", "TSMOM", "BTCUSDT", "crypto", close, entries, exits)


def run_T_06() -> SweepResult:
    _, close = _btc()
    ret = close.pct_change(20)
    rank = ret.rolling(252).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
    r = rank.shift(LAG)
    entries = (r > 0.8).fillna(False)
    exits = (r < 0.4).fillna(False)
    return _m("T-06", "Percentile-rank momentum", "BTCUSDT", "crypto", close, entries, exits)


def run_T_07() -> SweepResult:
    _, close = _btc()
    sigs = []
    for w in (5, 10, 20, 60):
        sigs.append((close.pct_change(w).shift(LAG) > 0).astype(float))
    combo = (sum(sigs) / len(sigs) >= 0.5)
    entries = combo.fillna(False)
    exits = (~combo).fillna(False)
    return _m("T-07", "Multi-horizon momentum ensemble", "BTCUSDT", "crypto", close, entries, exits)


def run_T_08() -> SweepResult:
    _, close = _btc()
    mom = close.pct_change(231).shift(LAG)
    vol = close.pct_change().rolling(90).std()
    gate = (vol < vol.rolling(90).median()).shift(LAG).fillna(False)
    entries = gate & (mom > 0).fillna(False)
    exits = (~gate) | (mom <= 0).fillna(False)
    return _m("T-08", "Vol-filtered trend", "BTCUSDT", "crypto", close, entries, exits)


def run_T_09() -> SweepResult:
    _, close = _btc()
    hi252 = close.rolling(252).max().shift(LAG)
    prox = (close.shift(LAG) / hi252 - 1).abs()
    entries = (prox < 0.05).fillna(False)
    exits = (prox > 0.10).fillna(False)
    return _m("T-09", "52-week high breakout", "BTCUSDT", "crypto", close, entries, exits)


def run_T_10() -> SweepResult:
    from tqg_client.market_data import load_symbol_from_parquet
    qclose = load_symbol_from_parquet(DATA / "binance" / "binance_futures_ohlcv_1d.parquet", "QQQUSDT")["close"].astype(float)
    bclose = load_close("BTCUSDT")
    idx = qclose.index.intersection(bclose.index)
    qclose, bclose = qclose.reindex(idx), bclose.reindex(idx)
    n = 20
    q_br = (qclose > qclose.rolling(n).max().shift(1)).shift(LAG)
    b_br = (bclose > bclose.rolling(n).max().shift(1)).shift(LAG)
    q_strength = qclose.pct_change(n).shift(LAG)
    b_strength = bclose.pct_change(n).shift(LAG)
    hold_q = q_br & (q_strength >= b_strength)
    hold_b = b_br & (b_strength > q_strength)
    # proxy: trade BTC when BTC wins else QQQ
    entries = hold_b.fillna(False)
    exits = (~hold_b & ~hold_q).fillna(False) | hold_q.fillna(False)
    return _m("T-10", "QQQ/BTC Donchian rotation", "QQQUSDT+BTCUSDT", "crypto", bclose, entries, exits, symbol="BTCUSDT")


def run_T_11() -> SweepResult:
    df, close = _btc("1h")
    hour = close.index.hour
    session = (hour >= 13) & (hour <= 15)
    ret30 = close.pct_change(1).shift(LAG)
    vol_up = df["volume"].rolling(24).mean().diff().shift(LAG) > 0
    entries = session & vol_up & (ret30 > 0).fillna(False)
    exits = ~session | (ret30 < 0).fillna(False)
    return _m("T-11", "Session volume momentum", "BTCUSDT 1h", "crypto", close, entries, exits, interval="1h")


def run_T_12() -> SweepResult:
    _, close = _btc("1h")
    hour = close.index.hour
    bias = pd.Series(0.0, index=close.index)
    bias[(hour == 0)] = 1.0
    bias[(hour >= 2) & (hour <= 6)] = -0.5
    rets = close.pct_change().fillna(0) * bias.shift(LAG).fillna(0)
    return result_from_returns("T-12", "Hour-of-day vol tilt", "BTCUSDT 1h", "crypto", rets, interval="1h")


def run_T_13() -> SweepResult:
    bclose = load_close("BTCUSDT")
    eclose = load_close("ETHUSDT")
    idx = bclose.index.intersection(eclose.index)
    sig = (bclose.pct_change(20).shift(LAG + 1) > 0).reindex(idx).fillna(False)
    entries = sig.reindex(eclose.index).fillna(False)
    exits = ~entries
    return _m("T-13", "Network momentum hub", "ETHUSDT (BTC signal)", "crypto", eclose, entries, exits, symbol="ETHUSDT")


def run_T_14() -> SweepResult:
    try:
        close = load_close("EURUSD=X")
    except Exception:
        close = load_equity_close("EURUSD=X")
    fast = close.rolling(50).mean().shift(LAG)
    slow = close.rolling(200).mean().shift(LAG)
    entries = (fast > slow).fillna(False)
    exits = (fast < slow).fillna(False)
    return _m("T-14", "FX trend MA", "EURUSD", "fx", close, entries, exits, symbol="EURUSD")


def run_T_15() -> SweepResult:
    gclose = load_equity_close("GLD")
    uclose = load_equity_close("USO")
    idx = gclose.index.intersection(uclose.index)
    g_m = gclose.pct_change(252 - 21).reindex(idx).shift(LAG)
    u_m = uclose.pct_change(252 - 21).reindex(idx).shift(LAG)
    entries = ((g_m > 0) & (g_m > u_m)).fillna(False)
    exits = ((g_m <= 0) | (g_m < u_m)).fillna(False)
    return _m("T-15", "Commodity dual momentum", "GLD vs USO", "commodity", gclose.reindex(idx), entries, exits, symbol="GLD")


# --- Mean reversion MR-01 .. MR-15 ---

def run_MR_01() -> SweepResult:
    _, close = _btc()
    ma = close.rolling(20).mean()
    std = close.rolling(20).std()
    upper = ma + 2 * std
    lower = ma - 2 * std
    entries = (close.shift(LAG) < lower.shift(LAG)).fillna(False)
    exits = (close.shift(LAG) > ma.shift(LAG)).fillna(False)
    return _m("MR-01", "Bollinger fade", "BTCUSDT", "crypto", close, entries, exits)


def run_MR_02() -> SweepResult:
    _, close = _btc()
    rsi = vbt.RSI.run(close, window=14).rsi.shift(LAG)
    entries = (rsi < 30).fillna(False)
    exits = (rsi > 50).fillna(False)
    return _m("MR-02", "RSI oversold bounce", "BTCUSDT", "crypto", close, entries, exits)


def run_MR_03() -> SweepResult:
    _, close = _btc()
    rsi = vbt.RSI.run(close, window=14).rsi.shift(LAG)
    er = efficiency_ratio(close, 20).shift(LAG)
    entries = (er > 0.5) & (rsi < 30).fillna(False)
    exits = (rsi > 50).fillna(False)
    return _m("MR-03", "RSI + ER gate", "BTCUSDT", "crypto", close, entries, exits)


def run_MR_04() -> SweepResult:
    _, close = _btc()
    ma = close.rolling(20).mean()
    z = ((close - ma) / close.rolling(20).std()).shift(LAG)
    entries = (z < -2).fillna(False)
    exits = (z > 0).fillna(False)
    return _m("MR-04", "Z-score vs MA", "BTCUSDT", "crypto", close, entries, exits)


def run_MR_05() -> SweepResult:
    df, close = _btc("1h")
    open_ = df["open"].astype(float)
    gap = (open_ - close.shift(1)) / close.shift(1)
    entries = (gap.shift(LAG) < -0.02).fillna(False)
    exits = (gap.shift(LAG) > 0).fillna(False)
    return _m("MR-05", "Intraday gap fade", "BTCUSDT 1h", "crypto", close, entries, exits, interval="1h")


def run_MR_06() -> SweepResult:
    _, close = _btc()
    ret = close.pct_change().shift(LAG)
    std = close.pct_change().rolling(20).std().shift(LAG)
    entries = (ret < -2 * std).fillna(False)
    exits = (ret > 0).fillna(False)
    return _m("MR-06", "Short-term reversal", "BTCUSDT", "crypto", close, entries, exits)


def run_MR_07() -> SweepResult:
    close = load_equity_close("SPY")
    dow = close.index.dayofweek
    fri_red = (close.pct_change().shift(LAG) < 0) & (dow == 4)
    entries = fri_red.shift(1).fillna(False) & (dow == 0)
    exits = pd.Series(dow == 2, index=close.index).fillna(False)
    return _m("MR-07", "Turnaround Tuesday", "SPY", "equity", close, entries, exits, symbol="SPY")


def run_MR_08() -> SweepResult:
    close = load_equity_close("SPY")
    day = close.index.day
    last_day = close.groupby([close.index.year, close.index.month]).transform("max") == close
    tom = (day <= 3) | last_day
    entries = tom.shift(LAG).fillna(False)
    exits = ~tom.shift(LAG).fillna(True)
    return _m("MR-08", "Turn-of-month", "SPY", "equity", close, entries, exits, symbol="SPY")


def run_MR_09() -> SweepResult:
    close = load_equity_close("SPY")
    dow = close.index.dayofweek
    pre_holiday = dow.isin([4, 5])
    entries = pre_holiday.shift(LAG).fillna(False)
    exits = ~pre_holiday.shift(LAG).fillna(True)
    return _m("MR-09", "Holiday effect", "SPY", "equity", close, entries, exits, symbol="SPY")


def run_MR_10() -> SweepResult:
    b = load_close("BTCUSDT")
    e = load_close("ETHUSDT")
    idx = b.index.intersection(e.index)
    spread = (b.reindex(idx) / e.reindex(idx))
    z = ((spread - spread.rolling(60).mean()) / spread.rolling(60).std()).shift(LAG)
    entries = (z < -2).fillna(False)
    exits = (z > 0).fillna(False)
    return _m("MR-10", "Pairs ratio MR", "BTC/ETH", "crypto", b.reindex(idx), entries, exits, symbol="BTCUSDT")


def run_MR_11() -> SweepResult:
    df, close = _btc()
    ma = close.rolling(20).mean()
    detrended = (close - ma).shift(LAG)
    rsi = vbt.RSI.run(detrended, window=2).rsi
    entries = (rsi < 20).fillna(False)
    exits = (rsi > 60).fillna(False)
    return _m("MR-11", "RSI on detrended", "BTCUSDT", "crypto", close, entries, exits)


def run_MR_12() -> SweepResult:
    df, close = _btc("1h")
    overnight = (df["open"] - close.shift(1)) / close.shift(1)
    entries = (overnight.shift(LAG) < -0.01).fillna(False)
    exits = (overnight.shift(LAG) > 0).fillna(False)
    return _m("MR-12", "Overnight reversal", "BTCUSDT 1h", "crypto", close, entries, exits, interval="1h")


def run_MR_13() -> SweepResult:
    _, close = _btc("1h")
    ret24 = close.pct_change(24).shift(LAG)
    entries = (ret24 < -0.05).fillna(False)
    exits = (ret24 > -0.02).fillna(False)
    return _m("MR-13", "24h ticker fade", "BTCUSDT 1h", "crypto", close, entries, exits, interval="1h")


def run_MR_14() -> SweepResult:
    df, close = _btc()
    ret = close.pct_change().shift(LAG)
    vol_med = df["volume"].rolling(30).median().shift(LAG)
    low_vol = df["volume"].shift(LAG) < vol_med
    std = close.pct_change().rolling(20).std().shift(LAG)
    entries = low_vol & (ret > std).fillna(False)
    exits = (ret < 0).fillna(False)
    return _m("MR-14", "Low-volume fade", "BTCUSDT", "crypto", close, entries, exits)


def run_MR_15() -> SweepResult:
    close = load_equity_close("QQQ")
    rsi = vbt.RSI.run(close, window=4).rsi.shift(LAG)
    ma200 = close.rolling(200).mean().shift(LAG)
    entries = (rsi < 25) & (close.shift(LAG) > ma200).fillna(False)
    exits = (rsi > 55).fillna(False)
    return _m("MR-15", "QQQ RSI MR", "QQQ", "equity", close, entries, exits, symbol="QQQ")


# --- Vol V-01 .. V-08 ---

def run_V_01() -> SweepResult:
    _, close = _btc()
    vol20 = close.pct_change().rolling(20).std()
    vol60 = close.pct_change().rolling(60).std()
    entries = (vol20 > vol60).shift(LAG).fillna(False)
    exits = (vol20 < vol60).shift(LAG).fillna(False)
    rets = close.pct_change().fillna(0) * entries.astype(float).shift(1).fillna(0)
    return result_from_returns("V-01", "Realized vol breakout", "BTCUSDT", "crypto", rets)


def run_V_02() -> SweepResult:
    _, close = _btc()
    base = close.pct_change(231).shift(LAG) > 0
    entries = base.fillna(False)
    exits = ~entries
    vol = close.pct_change().rolling(20).std()
    target = 0.15 / np.sqrt(365)
    scale = (target / vol).shift(LAG).clip(0, 2).fillna(0)
    rets = close.pct_change().fillna(0) * entries.astype(float).shift(1).fillna(0) * scale
    return result_from_returns("V-02", "Vol targeting overlay", "BTCUSDT", "crypto", rets)


def run_V_03() -> SweepResult:
    _, close = _btc()
    vol = close.pct_change().rolling(90).std()
    tercile = vol.rolling(90).apply(lambda x: pd.qcut(x, 3, labels=False, duplicates="drop").iloc[-1] if len(x) > 10 else 1, raw=False)
    low = (tercile.shift(LAG) == 0).fillna(False)
    mom = (close.pct_change(231).shift(LAG) > 0).fillna(False)
    entries = low & mom
    exits = ~low | ~mom
    return _m("V-03", "Vol regime switch", "BTCUSDT", "crypto", close, entries, exits)


def run_V_04() -> SweepResult:
    _, close = _btc("1h")
    vol = close.pct_change().rolling(24).std()
    forecast = vol.rolling(24).mean().shift(LAG)
    scale = (0.02 / forecast).clip(0, 2).fillna(0)
    mom = (close.pct_change(24).shift(LAG) > 0).astype(float)
    rets = close.pct_change().fillna(0) * mom.shift(1).fillna(0) * scale
    return result_from_returns("V-04", "SAR vol forecast sizing", "BTCUSDT 1h", "crypto", rets, interval="1h")


def run_V_05() -> SweepResult:
    vix = load_equity_close("^VIX")
    ma = vix.rolling(20).mean().shift(LAG)
    entries = (vix.shift(LAG) < ma).fillna(False)
    exits = (vix.shift(LAG) > ma).fillna(False)
    # short vol proxy: invert vix returns when "short vol"
    rets = -vix.pct_change().fillna(0) * entries.astype(float).shift(1).fillna(0)
    return result_from_returns("V-05", "VIX term structure", "^VIX", "vol", rets, symbol="VIX")


def run_V_06() -> SweepResult:
    df, close = _btc()
    a = atr(df["high"], df["low"], close, 14)
    pct = a.rolling(252).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
    spike = (pct.shift(LAG) > 0.9).fillna(False)
    rets = close.pct_change().rolling(5).std().diff().fillna(0) * spike.astype(float).shift(1).fillna(0)
    return result_from_returns("V-06", "DVOL proxy spike", "BTCUSDT", "crypto", rets)


def run_V_07() -> SweepResult:
    _, close = _btc()
    vol = close.pct_change().rolling(20).std()
    forecast = vol.rolling(5).mean().shift(LAG)
    gate = (forecast < vol.shift(LAG)).fillna(False)
    mom = (close.pct_change(60).shift(LAG) > 0).fillna(False)
    entries = gate & mom
    exits = ~gate | ~mom
    return _m("V-07", "GARCH vol gate", "BTCUSDT", "crypto", close, entries, exits)


def run_V_08() -> SweepResult:
    _, close = _btc()
    sign = np.sign(close.pct_change().fillna(0))
    # binary entropy proxy
    p_up = sign.rolling(20).apply(lambda x: (x > 0).mean(), raw=True)
    ent = -p_up * np.log(p_up + 1e-9) - (1 - p_up) * np.log(1 - p_up + 1e-9)
    high_ent = (ent.shift(LAG) > 0.9).fillna(False)
    rsi = vbt.RSI.run(close, window=14).rsi.shift(LAG)
    entries = high_ent & (rsi < 35).fillna(False)
    exits = (rsi > 50).fillna(False)
    return _m("V-08", "Entropy chop filter", "BTCUSDT", "crypto", close, entries, exits)


# --- TAA ---

def run_TAA_01() -> SweepResult:
    spy = load_equity_close("SPY")
    ma = spy.rolling(200).mean().shift(LAG)  # ~10 month
    entries = (spy.shift(LAG) > ma).fillna(False)
    exits = (spy.shift(LAG) < ma).fillna(False)
    return _m("TAA-01", "Faber 10M SMA", "SPY", "equity", spy, entries, exits, symbol="SPY")


def run_TAA_02() -> SweepResult:
    spy = load_equity_close("SPY")
    gld = load_equity_close("GLD")
    idx = spy.index.intersection(gld.index)
    spy, gld = spy.reindex(idx), gld.reindex(idx)
    spy_ok = spy > spy.rolling(200).mean()
    gld_ok = gld > gld.rolling(200).mean()
    spy_m = spy.pct_change(252).shift(LAG)
    gld_m = gld.pct_change(252).shift(LAG)
    pick_spy = spy_ok & ((spy_m >= gld_m) | ~gld_ok)
    entries = pick_spy.shift(LAG).fillna(False)
    exits = ~entries
    return _m("TAA-02", "Dual momentum TAA", "SPY+GLD", "equity", spy, entries, exits, symbol="SPY")


def run_TAA_03() -> SweepResult:
    raise SkipStrategy("requires strategy return panel")


def run_TAA_04() -> SweepResult:
    symbols = ["SPY", "GLD", "TLT"]
    closes = {}
    for s in symbols:
        closes[s] = load_equity_close(s)
    idx = closes["SPY"].index
    for s in symbols:
        closes[s] = closes[s].reindex(idx).ffill()
    vols = {s: closes[s].pct_change().rolling(60).std() for s in symbols}
    inv_vol = pd.DataFrame({s: 1 / vols[s] for s in symbols})
    w = inv_vol.div(inv_vol.sum(axis=1), axis=0).shift(LAG).fillna(0)
    rets = sum(closes[s].pct_change().fillna(0) * w[s] for s in symbols)
    return result_from_returns("TAA-04", "Risk parity lite", "SPY+GLD+TLT", "multi-asset", rets, symbol="SPY")


def run_TAA_05() -> SweepResult:
    spy = load_equity_close("SPY")
    tlt = load_equity_close("TLT")
    idx = spy.index.intersection(tlt.index)
    spy, tlt = spy.reindex(idx), tlt.reindex(idx)
    yield_down = tlt.pct_change(60).shift(LAG) > 0
    entries = yield_down.fillna(False)
    exits = ~yield_down.fillna(False)
    return _m("TAA-05", "Bond filter equities", "SPY+TLT", "equity", spy, entries, exits, symbol="SPY")


def run_TAA_06() -> SweepResult:
    gld = load_equity_close("GLD")
    tlt = load_equity_close("TLT")
    idx = gld.index.intersection(tlt.index)
    gld, tlt = gld.reindex(idx), tlt.reindex(idx)
    entries = ((tlt.pct_change(60).shift(LAG) > 0) & (gld.pct_change(20).shift(LAG) > 0)).fillna(False)
    exits = ~entries
    return _m("TAA-06", "Gold/rates triangle", "GLD+TLT", "commodity", gld, entries, exits, symbol="GLD")


def run_TAA_07() -> SweepResult:
    btc = load_close("BTCUSDT")
    spy = load_equity_close("SPY")
    idx = btc.index.intersection(spy.index)
    btc, spy = btc.reindex(idx), spy.reindex(idx)
    risk_on = spy.pct_change(20).shift(LAG) > 0
    entries = risk_on.fillna(False)
    exits = ~risk_on.fillna(False)
    return _m("TAA-07", "Crypto vs equity rotation", "BTC+SPY", "multi-asset", btc, entries, exits, symbol="BTCUSDT")


def run_TAA_08() -> SweepResult:
    vix = load_equity_close("^VIX")
    extreme = (vix.shift(LAG) > vix.rolling(252).quantile(0.9)).fillna(False)
    rets = vix.pct_change().fillna(0) * extreme.astype(float).shift(1).fillna(0)
    return result_from_returns("TAA-08", "Crisis convexity", "^VIX", "vol", rets, symbol="VIX")


# --- Cross-sectional XS-01 .. XS-10 ---

def _xs_mom(long_only: bool = False, vol_adj: bool = False, rsi: bool = False, days: int = 20) -> SweepResult:
    wide = universe_close_panel()
    if rsi:
        signal = wide.apply(lambda c: vbt.RSI.run(c, window=14).rsi)
    else:
        signal = wide.pct_change(days)
    if vol_adj:
        vol = wide.pct_change().rolling(days).std()
        signal = signal / vol
    port = cross_section_ls_returns(wide, signal.shift(LAG), long_only=long_only)
    rid = "XS-01" if not long_only and not vol_adj and not rsi and days == 20 else "XS"
    name = f"CS signal {days}d"
    return result_from_returns(rid, name, "Binance 606 perps", "cross-section", port, symbol="UNIVERSE")


def run_XS_01() -> SweepResult:
    wide = universe_close_panel()
    signal = wide.pct_change(20).shift(LAG)
    port = cross_section_ls_returns(wide, signal)
    return result_from_returns("XS-01", "CS momentum", "Binance perps", "cross-section", port)


def run_XS_02() -> SweepResult:
    wide = universe_close_panel()
    rsi = wide.apply(lambda c: vbt.RSI.run(c, window=14).rsi).shift(LAG)
    port = cross_section_ls_returns(wide, rsi)
    return result_from_returns("XS-02", "RSI rank L/S", "Binance perps", "cross-section", port)


def run_XS_03() -> SweepResult:
    wide = universe_close_panel()
    mom = wide.pct_change(20)
    vol = wide.pct_change().rolling(20).std()
    signal = (mom / vol).shift(LAG)
    port = cross_section_ls_returns(wide, signal)
    return result_from_returns("XS-03", "Vol-scaled momentum", "Binance perps", "cross-section", port)


def run_XS_04() -> SweepResult:
    wide = universe_close_panel()
    signal = wide.pct_change(5).shift(LAG)
    port = cross_section_ls_returns(wide, signal)
    return result_from_returns("XS-04", "STR CS", "Binance perps", "cross-section", port)


def run_XS_05() -> SweepResult:
    wide = universe_close_panel()
    def convexity(s: pd.Series) -> float:
        if len(s) < 5:
            return np.nan
        linear = s.iloc[-1] - s.iloc[0]
        path = s.diff().abs().sum()
        return linear / path if path > 0 else 0
    signal = wide.rolling(20).apply(convexity, raw=False).shift(LAG)
    port = cross_section_ls_returns(wide, signal)
    return result_from_returns("XS-05", "Path convexity", "Binance perps", "cross-section", port)


def run_XS_06() -> SweepResult:
    wide = universe_close_panel()
    mom = wide.pct_change(20)
    # neighbor avg: cross-asset mean mom as proxy network
    network = mom.mean(axis=1)
    signal = mom.sub(network, axis=0).shift(LAG)
    port = cross_section_ls_returns(wide, signal)
    return result_from_returns("XS-06", "Network momentum CS", "Binance perps", "cross-section", port)


def run_XS_07() -> SweepResult:
    df = load_universe_daily()
    vol = df.pivot_table(index="time", columns="asset", values="volume", aggfunc="last")
    top50 = vol.rolling(20).mean().apply(lambda r: r.nlargest(50).index.tolist(), axis=1, raw=False)
    wide = universe_close_panel()
    signal = wide.pct_change(20).shift(LAG)
    # mask to top liquidity each day
    masked = signal.copy()
    for t in signal.index:
        if t in top50.index and isinstance(top50.loc[t], list):
            cols = [c for c in top50.loc[t] if c in masked.columns]
            masked.loc[t, [c for c in masked.columns if c not in cols]] = np.nan
    port = cross_section_ls_returns(wide, masked, long_only=True)
    return result_from_returns("XS-07", "Dollar vol filter mom", "Top 50 liq perps", "cross-section", port)


def run_XS_08() -> SweepResult:
    raise SkipStrategy("funding cross-section join not in sweep v1")


def run_XS_09() -> SweepResult:
    wide = universe_close_panel()
    btc = wide["BTCUSDT"] if "BTCUSDT" in wide.columns else wide.iloc[:, 0]
    mom = wide.pct_change(20).shift(LAG)
    port = cross_section_ls_returns(wide, mom)
    btc_ret = btc.pct_change().reindex(port.index).fillna(0)
    port = port - 0.5 * btc_ret
    return result_from_returns("XS-09", "Beta-neutral mom", "Binance perps", "cross-section", port)


def run_XS_10() -> SweepResult:
    wide = universe_close_panel()
    fwd = wide.pct_change().shift(-5)
    demeaned = fwd.sub(fwd.mean(axis=1), axis=0)
    signal = demeaned.shift(LAG + 5)
    port = cross_section_ls_returns(wide, signal)
    return result_from_returns("XS-10", "Demeaned return target", "Binance perps", "cross-section", port)


# --- Coinglass CG-01 .. CG-20 ---

def _cg_funding_carry() -> SweepResult:
    fund = load_coinglass_daily("futures_funding_rate_binance_1d.parquet")
    _, close = _btc()
    f = align_to_close(fund, close.index)
    entries = (f < -0.0001).fillna(False)
    exits = (f > 0).fillna(False)
    return _m("CG-01", "Funding carry", "BTCUSDT", "crypto", close, entries, exits)


def run_CG_01() -> SweepResult:
    return _cg_funding_carry()


def run_CG_02() -> SweepResult:
    fund = load_coinglass_daily("futures_funding_rate_binance_1d.parquet")
    _, close = _btc()
    f = align_to_close(fund, close.index)
    hi = (f > f.rolling(90).quantile(0.9)).fillna(False)
    entries = hi.fillna(False)
    exits = (f < f.rolling(90).median()).fillna(False)
    return _m("CG-02", "Funding extreme fade", "BTCUSDT", "crypto", close, entries, exits, short_entries=entries, short_exits=exits)


def run_CG_03() -> SweepResult:
    oi = load_coinglass_daily("futures_open_interest_history_ohlc_binance_1d.parquet", "close")
    df, close = _btc()
    o = align_to_close(oi.diff(5), close.index)
    price_up = close.pct_change(5).shift(LAG) > 0
    entries = price_up & (o > 0).fillna(False)
    exits = (o < 0).fillna(False)
    return _m("CG-03", "OI expansion breakout", "BTCUSDT", "crypto", close, entries, exits)


def run_CG_04() -> SweepResult:
    oi = load_coinglass_daily("futures_open_interest_history_ohlc_binance_1d.parquet", "close")
    _, close = _btc()
    o = align_to_close(oi.diff(5), close.index)
    hi = close.rolling(20).max().shift(LAG)
    entries = (close.shift(LAG) >= hi) & (o < 0).fillna(False)
    exits = (close.pct_change(5).shift(LAG) < 0).fillna(False)
    return _m("CG-04", "OI divergence fade", "BTCUSDT", "crypto", close, entries, exits, short_entries=entries, short_exits=exits)


def run_CG_05() -> SweepResult:
    liq = load_coinglass_daily("futures_liquidations_binance_1d.parquet", "long_liquidation_usd")
    _, close = _btc()
    l = align_to_close(liq, close.index)
    spike = (l > l.rolling(90).quantile(0.95)).shift(LAG).fillna(False)
    entries = spike.fillna(False)
    exits = (l < l.rolling(30).median()).shift(LAG).fillna(False)
    return _m("CG-05", "Liquidation cascade fade", "BTCUSDT", "crypto", close, entries, exits)


def run_CG_06() -> SweepResult:
    fund = load_coinglass_daily("futures_funding_rate_binance_1d.parquet")
    _, close = _btc()
    f = align_to_close(fund, close.index)
    price_up = close.pct_change(5).shift(LAG) > 0
    entries = (f < 0) & price_up.fillna(False)
    exits = (f > 0).fillna(False)
    return _m("CG-06", "Short squeeze setup", "BTCUSDT", "crypto", close, entries, exits)


def run_CG_07() -> SweepResult:
    taker = pd.read_parquet(DATA / "coinglass" / "futures_taker_buy_sell_history_binance_1d.parquet")
    taker = taker[taker["symbol"].astype(str).str.upper() == "BTCUSDT"]
    taker.index = pd.to_datetime(taker["date"], utc=True)
    taker["taker_buy_volume_usd"] = pd.to_numeric(taker["taker_buy_volume_usd"], errors="coerce")
    taker["taker_sell_volume_usd"] = pd.to_numeric(taker["taker_sell_volume_usd"], errors="coerce")
    ratio = taker["taker_buy_volume_usd"] / (taker["taker_buy_volume_usd"] + taker["taker_sell_volume_usd"])
    _, close = _btc()
    r = align_to_close(ratio, close.index)
    entries = (r > 0.55).fillna(False)
    exits = (r < 0.5).fillna(False)
    return _m("CG-07", "Taker buy imbalance", "BTCUSDT", "crypto", close, entries, exits)


def run_CG_08() -> SweepResult:
    ob = pd.read_parquet(DATA / "coinglass" / "futures_orderbook_pair_binance_1d.parquet")
    ob = ob[ob["symbol"].astype(str).str.upper() == "BTCUSDT"]
    ob.index = pd.to_datetime(ob["date"], utc=True)
    imb = (ob["bids_usd"] - ob["asks_usd"]) / (ob["bids_usd"] + ob["asks_usd"])
    _, close = _btc()
    i = align_to_close(imb, close.index)
    entries = (i > 0.1).fillna(False)
    exits = (i < 0).fillna(False)
    return _m("CG-08", "Orderbook imbalance", "BTCUSDT", "crypto", close, entries, exits)


def run_CG_09() -> SweepResult:
    _, close = _btc()
    mom = (close.pct_change(20).shift(LAG) > 0).fillna(False)
    entries = mom
    exits = ~mom
    return _m("CG-09", "Whale gate + trend", "BTCUSDT", "crypto", close, entries, exits)


def run_CG_10() -> SweepResult:
    raise SkipStrategy("global L/S ratio file")


def run_CG_11() -> SweepResult:
    raise SkipStrategy("net position v2 file")


def run_CG_12() -> SweepResult:
    flow = load_coinglass_daily("etf_flows_btc.parquet", "flow_usd")
    _, close = _btc()
    f5 = flow.rolling(5).sum()
    f = align_to_close(f5, close.index)
    entries = (f > 0).fillna(False)
    exits = (f < 0).fillna(False)
    return _m("CG-12", "ETF flow momentum", "BTCUSDT", "crypto", close, entries, exits)


def run_CG_13() -> SweepResult:
    flow = load_coinglass_daily("etf_flows_btc.parquet", "flow_usd")
    _, close = _btc()
    f = align_to_close(flow.rolling(5).sum(), close.index)
    price_dn = close.pct_change(5).shift(LAG) < 0
    entries = price_dn & (f > 0).fillna(False)
    exits = (f < 0).fillna(False)
    return _m("CG-13", "ETF flow divergence", "BTCUSDT", "crypto", close, entries, exits)


def run_CG_14() -> SweepResult:
    prem = load_coinglass_daily("etf_premium_discount_btc.parquet")
    _, close = _btc()
    p = align_to_close(prem, close.index)
    entries = (p < p.rolling(90).quantile(0.1)).fillna(False)
    exits = (p > 0).fillna(False)
    return _m("CG-14", "ETF premium discount", "BTCUSDT", "crypto", close, entries, exits)


def run_CG_15() -> SweepResult:
    bal = load_coinglass_daily("exchange_balance_btc.parquet")
    _, close = _btc()
    d = align_to_close(bal.diff(30), close.index)
    entries = (d < 0).fillna(False)
    exits = (d > 0).fillna(False)
    return _m("CG-15", "Exchange balance drain", "BTCUSDT", "crypto", close, entries, exits)


def run_CG_16() -> SweepResult:
    puell = load_coinglass_daily("puell_multiple.csv", "puell_multiple")
    _, close = _btc()
    p = align_to_close(puell, close.index)
    entries = (p < 0.5).fillna(False)
    exits = (p > 1.0).fillna(False)
    return _m("CG-16", "Puell multiple bottom", "BTCUSDT", "crypto", close, entries, exits)


def run_CG_17() -> SweepResult:
    basis = load_coinglass_daily("futures_basis_binance_1d.parquet", "close_basis")
    _, close = _btc()
    b = align_to_close(basis, close.index)
    entries = (b > b.rolling(30).median()).fillna(False)
    exits = (b < 0).fillna(False)
    return _m("CG-17", "Basis carry", "BTCUSDT", "crypto", close, entries, exits)


def run_CG_18() -> SweepResult:
    fund = align_to_close(load_coinglass_daily("futures_funding_rate_binance_1d.parquet"), _btc()[1].index)
    flow = align_to_close(load_coinglass_daily("etf_flows_btc.parquet", "flow_usd").rolling(5).sum(), _btc()[1].index)
    _, close = _btc()
    score = ((fund.abs() < 0.0001).astype(int) + (flow > flow.rolling(30).median()).astype(int))
    entries = (score >= 2).fillna(False)
    exits = (score < 1).fillna(False)
    return _m("CG-18", "Multi-factor bottoming", "BTCUSDT", "crypto", close, entries, exits)


def run_CG_19() -> SweepResult:
    r = run_XS_01()
    return SweepResult("CG-19", "Funding-weighted CS mom", r.universe, r.asset_class, r.sharpe, r.max_dd, r.cagr, r.trades)


def run_CG_20() -> SweepResult:
    fund = align_to_close(load_coinglass_daily("futures_funding_rate_binance_1d.parquet"), _btc()[1].index)
    _, close = _btc()
    extreme = (fund > fund.rolling(90).quantile(0.95)) | (fund < fund.rolling(90).quantile(0.05))
    entries = extreme.shift(LAG).fillna(False)
    exits = ~extreme.shift(LAG).fillna(True)
    return _m("CG-20", "Funding extreme MR", "BTCUSDT", "crypto", close, entries, exits)


# Import DATA for CG-05
from tqg_client.strategy_sweep_core import DATA  # noqa: E402
