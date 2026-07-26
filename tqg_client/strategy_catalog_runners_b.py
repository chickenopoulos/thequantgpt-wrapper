"""Strategy catalog runners — on-chain, intermarket, Quantocracy."""

from __future__ import annotations

import numpy as np
import pandas as pd
import vectorbt as vbt

from tqg_client.market_data import load_market_data
from tqg_client.strategy_sweep_core import (
    LAG,
    align_to_close,
    load_btc_talos_metrics,
    load_close,
    load_coinglass_daily,
    load_equity_close,
    load_ohlcv,
    result_from_returns,
    run_signal_backtest,
    SkipStrategy,
    SweepResult,
)
from tqg_client.strategy_catalog_runners_a import _btc, _m


def _talos_series(col: str) -> pd.Series:
    df = load_btc_talos_metrics()
    if col not in df.columns:
        raise SkipStrategy(f"Talos column {col} missing")
    return df[col].astype(float)


def run_ON_01() -> SweepResult:
    z = _talos_series("CapMVRVZ")
    _, close = _btc()
    z = align_to_close(z, close.index)
    entries = (z < -1).fillna(False)
    exits = (z > 2).fillna(False)
    return _m("ON-01", "MVRV Z-score", "BTC", "crypto", close, entries, exits)


def run_ON_02() -> SweepResult:
    nupl = _talos_series("NUPL")
    _, close = _btc()
    n = align_to_close(nupl, close.index)
    entries = (n < 0.25).fillna(False)
    exits = (n > 0.75).fillna(False)
    return _m("ON-02", "NUPL regime", "BTC", "crypto", close, entries, exits)


def run_ON_03() -> SweepResult:
    real = _talos_series("CapRealUSD")
    _, close = _btc()
    r = align_to_close(real, close.index)
    entries = (close.shift(LAG) < r * 1.05).fillna(False)
    exits = (close.shift(LAG) > r * 1.1).fillna(False)
    return _m("ON-03", "Realized price support", "BTC", "crypto", close, entries, exits)


def run_ON_04() -> SweepResult:
    mv = _talos_series("CapMVRVCur")
    _, close = _btc()
    m = align_to_close(mv, close.index)
    entries = (m < 1).fillna(False)
    exits = (m > 3).fillna(False)
    return _m("ON-04", "MVRV < 1 value", "BTC", "crypto", close, entries, exits)


def run_ON_05() -> SweepResult:
    raise SkipStrategy("NVTAdj not in btc metrics file")


def run_ON_06() -> SweepResult:
    sopr = _talos_series("SOPR")
    _, close = _btc()
    s = align_to_close(sopr, close.index)
    below = (s < 1).rolling(7).sum() >= 5
    entries = below.shift(LAG).fillna(False)
    exits = (s > 1).fillna(False)
    return _m("ON-06", "SOPR capitulation", "BTC", "crypto", close, entries, exits)


def run_ON_07() -> SweepResult:
    real = _talos_series("CapRealUSD")
    _, close = _btc()
    r = align_to_close(real, close.index)
    cross = (close.shift(LAG) > r) & (close.shift(LAG + 1) <= r.shift(1))
    entries = cross.fillna(False)
    exits = (close.shift(LAG) < r).fillna(False)
    return _m("ON-07", "STH cost reclaim", "BTC", "crypto", close, entries, exits)


def run_ON_08() -> SweepResult:
    raise SkipStrategy("SplyLTH not in btc metrics")


def run_ON_09() -> SweepResult:
    adr = _talos_series("AdrActCnt")
    _, close = _btc()
    a = align_to_close(adr.diff(30), close.index)
    entries = (a > 0).fillna(False)
    exits = (a < 0).fillna(False)
    return _m("ON-09", "Accumulation proxy", "BTC", "crypto", close, entries, exits)


def run_ON_10() -> SweepResult:
    raise SkipStrategy("realized loss metric not mapped")


def run_NA_01() -> SweepResult:
    adr = _talos_series("AdrActCnt")
    _, close = _btc()
    roc = align_to_close(adr.pct_change(30), close.index)
    entries = (roc > 0).fillna(False)
    exits = (roc < 0).fillna(False)
    return _m("NA-01", "Active address momentum", "BTC", "crypto", close, entries, exits)


def run_NA_02() -> SweepResult:
    tx = _talos_series("TxCnt")
    _, close = _btc()
    t = align_to_close(tx, close.index)
    ma = t.rolling(90).mean()
    entries = (t > ma).shift(LAG).fillna(False)
    exits = (t < ma).shift(LAG).fillna(False)
    return _m("NA-02", "Tx count breakout", "BTC", "crypto", close, entries, exits)


def run_NA_03() -> SweepResult:
    raise SkipStrategy("TxTfrValAdjUSD not verified")


def run_NA_04() -> SweepResult:
    raise SkipStrategy("FeeMeanUSD not in btc metrics")


def run_NA_05() -> SweepResult:
    new_a = _talos_series("AdrNewCnt")
    _, close = _btc()
    div = align_to_close(new_a.pct_change(30) - close.pct_change(30), close.index)
    entries = (div > 0).fillna(False)
    exits = (div < 0).fillna(False)
    return _m("NA-05", "New address divergence", "BTC", "crypto", close, entries, exits)


def run_EF_01() -> SweepResult:
    bal = load_coinglass_daily("exchange_balance_btc.parquet")
    _, close = _btc()
    flow = align_to_close(bal.diff(7), close.index)
    entries = (flow < 0).fillna(False)
    exits = (flow > 0).fillna(False)
    return _m("EF-01", "Exchange net outflow", "BTC", "crypto", close, entries, exits)


def run_EF_02() -> SweepResult:
    raise SkipStrategy("miner flows not mapped")


def run_EF_03() -> SweepResult:
    etf = load_coinglass_daily("etf_flows_btc.parquet", "flow_usd").rolling(5).sum()
    bal = load_coinglass_daily("exchange_balance_btc.parquet").diff(7)
    _, close = _btc()
    e = align_to_close(etf, close.index)
    b = align_to_close(bal, close.index)
    entries = (e > 0) & (b < 0).fillna(False)
    exits = (e < 0).fillna(False)
    return _m("EF-03", "ETF + exchange combo", "BTC", "crypto", close, entries, exits)


def run_EF_04() -> SweepResult:
    raise SkipStrategy("stablecoin flow upload required")


def run_DV_01() -> SweepResult:
    fund = align_to_close(load_coinglass_daily("futures_funding_rate_binance_1d.parquet"), _btc()[1].index)
    cum = fund.rolling(30).sum()
    _, close = _btc()
    entries = (cum.shift(LAG) > 0).fillna(False)
    exits = (cum.shift(LAG) < 0).fillna(False)
    return _m("DV-01", "Funding trend", "BTC", "crypto", close, entries, exits)


def run_DV_02() -> SweepResult:
    raise SkipStrategy("OI/MCAP talos join")


def run_DV_03() -> SweepResult:
    raise SkipStrategy("options OI put/call talos")


def run_DV_04() -> SweepResult:
    raise SkipStrategy("vol term structure talos columns")


def run_DV_05() -> SweepResult:
    raise SkipStrategy("perp/spot volume ratio")


def run_GF_01() -> SweepResult:
    mv = align_to_close(_talos_series("CapMVRVCur"), _btc()[1].index)
    bal = align_to_close(load_coinglass_daily("exchange_balance_btc.parquet").diff(14), _btc()[1].index)
    etf = align_to_close(load_coinglass_daily("etf_flows_btc.parquet", "flow_usd").rolling(5).sum(), _btc()[1].index)
    _, close = _btc()
    entries = (mv < 1) & (bal < 0) & (etf >= 0).fillna(False)
    exits = (mv > 2).fillna(False)
    return _m("GF-01", "Deep value accumulator", "BTC multi-layer", "crypto", close, entries, exits)


def run_GF_02() -> SweepResult:
    etf = align_to_close(load_coinglass_daily("etf_flows_btc.parquet", "flow_usd"), _btc()[1].index)
    _, close = _btc()
    improving = etf.rolling(30).mean().diff().shift(LAG) > 0
    entries = improving.fillna(False)
    exits = ~improving.fillna(False)
    return _m("GF-02", "Bear late-stage ETF", "BTC", "crypto", close, entries, exits)


def run_GF_03() -> SweepResult:
    real = align_to_close(_talos_series("CapRealUSD"), _btc()[1].index)
    fund = align_to_close(load_coinglass_daily("futures_funding_rate_binance_1d.parquet"), _btc()[1].index)
    _, close = _btc()
    entries = (close.shift(LAG) > real) & (fund.abs() < 0.0001).fillna(False)
    exits = (close.shift(LAG) < real).fillna(False)
    return _m("GF-03", "Recovery confirmation", "BTC", "crypto", close, entries, exits)


def run_GF_04() -> SweepResult:
    etf = align_to_close(load_coinglass_daily("etf_flows_btc.parquet", "flow_usd"), _btc()[1].index)
    bal = align_to_close(load_coinglass_daily("exchange_balance_btc.parquet").diff(7), _btc()[1].index)
    _, close = _btc()
    vol_up = close.pct_change().rolling(20).std().diff().shift(LAG) > 0
    entries = vol_up & (etf < 0) & (bal > 0).fillna(False)
    exits = ~entries
    return _m("GF-04", "Risk-off de-risk", "BTC", "crypto", close, entries, exits, short_entries=entries, short_exits=~entries)


def run_GF_05() -> SweepResult:
    dxy = load_equity_close("DX-Y.NYB")
    _, close = _btc()
    idx = close.index.intersection(dxy.index)
    close, dxy = close.reindex(idx), dxy.reindex(idx)
    entries = ((dxy < dxy.rolling(200).mean()) & (close > close.rolling(200).mean())).shift(LAG).fillna(False)
    exits = ~entries
    return _m("GF-05", "Macro liquidity BTC", "BTC+DXY", "multi-asset", close, entries, exits)


def run_GF_06() -> SweepResult:
    dxy = load_equity_close("DX-Y.NYB")
    _, close = _btc()
    idx = close.index.intersection(dxy.index)
    corr = close.reindex(idx).pct_change().rolling(60).corr(dxy.reindex(idx).pct_change())
    scale = (-corr.shift(LAG)).clip(0, 1).fillna(0)
    rets = close.reindex(idx).pct_change().fillna(0) * scale
    return result_from_returns("GF-06", "Dollar inverse sleeve", "BTC+DXY", "multi-asset", rets)


def run_GF_07() -> SweepResult:
    raise SkipStrategy("options max pain strikes required")


def run_GF_08() -> SweepResult:
    df, close = _btc()
    from tqg_client.strategy_sweep_core import atr
    a = atr(df["high"], df["low"], close)
    low_vol = (a < a.rolling(252).quantile(0.1)).shift(LAG).fillna(False)
    brk = (close > close.rolling(20).max().shift(1)).shift(LAG).fillna(False)
    entries = low_vol & brk
    exits = (close < close.rolling(10).min().shift(1)).shift(LAG).fillna(False)
    return _m("GF-08", "Vol compression breakout", "BTC", "crypto", close, entries, exits)


def run_GF_09() -> SweepResult:
    real = align_to_close(_talos_series("CapRealUSD"), _btc()[1].index)
    _, close = _btc()
    near = (close.shift(LAG) / real - 1).abs() < 0.02
    entries = near.fillna(False)
    exits = (close.shift(LAG) > real * 1.05).fillna(False)
    return _m("GF-09", "STH resistance fade", "BTC", "crypto", close, entries, exits)


def run_GF_10() -> SweepResult:
    score = pd.Series(0, index=_btc()[1].index)
    try:
        mv = align_to_close(_talos_series("CapMVRVCur"), score.index)
        score += (mv < 1.5).astype(int)
    except SkipStrategy:
        pass
    try:
        etf = align_to_close(load_coinglass_daily("etf_flows_btc.parquet", "flow_usd").rolling(5).sum(), score.index)
        score += (etf > 0).astype(int)
    except SkipStrategy:
        pass
    try:
        fund = align_to_close(load_coinglass_daily("futures_funding_rate_binance_1d.parquet"), score.index)
        score += (fund.abs() < 0.0001).astype(int)
    except SkipStrategy:
        pass
    _, close = _btc()
    entries = (score >= 2).shift(LAG).fillna(False)
    exits = (score < 1).shift(LAG).fillna(False)
    return _m("GF-10", "Week 28 scorecard", "BTC multi-layer", "crypto", close, entries, exits)


def run_IA_01() -> SweepResult:
    b = load_close("BTCUSDT")
    e = load_close("ETHUSDT")
    idx = b.index.intersection(e.index)
    sig = (b.reindex(idx).pct_change().shift(LAG) > 0).reindex(e.index).fillna(False)
    entries = sig
    exits = ~sig
    return _m("IA-01", "BTC leads ETH", "ETHUSDT", "crypto", e, entries, exits, symbol="ETHUSDT")


def run_IA_02() -> SweepResult:
    spy = load_equity_close("SPY")
    btc = load_close("BTCUSDT")
    idx = spy.index.intersection(btc.index)
    risk = spy.reindex(idx).pct_change(5).shift(LAG) > 0
    entries = risk.reindex(btc.index).fillna(False)
    exits = ~entries
    return _m("IA-02", "SPY leads BTC", "BTCUSDT", "crypto", btc, entries, exits)


def run_IA_03() -> SweepResult:
    pax = load_close("PAXGUSDT")
    btc = load_close("BTCUSDT")
    idx = pax.index.intersection(btc.index)
    ratio = (pax.reindex(idx) / btc.reindex(idx))
    z = ((ratio - ratio.rolling(60).mean()) / ratio.rolling(60).std()).shift(LAG)
    entries = (z > 2).fillna(False)
    exits = (z < 0).fillna(False)
    return _m("IA-03", "Gold/BTC ratio MR", "PAXG/BTC", "crypto", btc.reindex(idx), entries, exits)


def run_IA_04() -> SweepResult:
    h = load_equity_close("HG=F")
    g = load_equity_close("GLD")
    idx = h.index.intersection(g.index)
    ratio = (h.reindex(idx) / g.reindex(idx)).pct_change(20).shift(LAG)
    btc = load_close("BTCUSDT")
    entries = (ratio > 0).reindex(btc.index).fillna(False)
    exits = ~entries
    return _m("IA-04", "Copper/gold risk-on", "BTC", "crypto", btc, entries, exits)


def run_IA_05() -> SweepResult:
    uso = load_equity_close("USO")
    shock = (uso.pct_change(5).shift(LAG) > 0.08).fillna(False)
    btc = load_close("BTCUSDT")
    entries = ~shock.reindex(btc.index).fillna(True)
    exits = shock.reindex(btc.index).fillna(False)
    return _m("IA-05", "Oil shock risk-off", "BTCUSDT", "crypto", btc, entries, exits)


def run_IA_06() -> SweepResult:
    tlt = load_equity_close("TLT")
    nvda = load_close("NVDAUSDT")
    gate = (tlt.pct_change(60).shift(LAG) > 0).reindex(nvda.index).fillna(False)
    mom = (nvda.pct_change(20).shift(LAG) > 0).fillna(False)
    entries = gate & mom
    exits = ~gate | ~mom
    return _m("IA-06", "Rates gate NVDA", "NVDAUSDT", "crypto", nvda, entries, exits, symbol="NVDAUSDT")


def run_IA_07() -> SweepResult:
    syms = ["SPYUSDT", "QQQUSDT", "NVDAUSDT"]
    closes = {s: load_close(s) for s in syms}
    idx = closes["SPYUSDT"].index
    mom = pd.DataFrame({s: closes[s].reindex(idx).pct_change(20) for s in syms})
    best = mom.idxmax(axis=1)
    rets = pd.Series(0.0, index=idx)
    for t in idx:
        if t in mom.index and best.loc[t] in syms:
            rets.loc[t] = closes[best.loc[t]].pct_change().reindex(idx).loc[t]
    return result_from_returns("IA-07", "Equity perp basket", "SPY/QQQ/NVDA perps", "crypto", rets.dropna())


def run_IA_08() -> SweepResult:
    eth = load_close("ETHUSDT")
    btc = load_close("BTCUSDT")
    idx = eth.index.intersection(btc.index)
    e_m = eth.reindex(idx).pct_change(20) / eth.reindex(idx).pct_change().rolling(20).std()
    b_m = btc.reindex(idx).pct_change(20) / btc.reindex(idx).pct_change().rolling(20).std()
    hold_eth = (e_m.shift(LAG) > b_m.shift(LAG)).fillna(False)
    entries = hold_eth.reindex(eth.index).fillna(False)
    exits = ~entries
    return _m("IA-08", "ETH/BTC rotation", "ETHUSDT", "crypto", eth, entries, exits, symbol="ETHUSDT")


def run_IA_09() -> SweepResult:
    dxy = load_equity_close("DX-Y.NYB")
    btc = load_close("BTCUSDT")
    scale = (dxy.pct_change(60).shift(LAG) < 0).reindex(btc.index).astype(float).fillna(0)
    rets = btc.pct_change().fillna(0) * scale
    return result_from_returns("IA-09", "DXY risk filter", "BTCUSDT", "crypto", rets)


def run_IA_10() -> SweepResult:
    eth = load_close("ETHUSDT")
    btc = load_close("BTCUSDT")
    idx = eth.index.intersection(btc.index)
    lead = btc.reindex(idx).pct_change().shift(LAG)
    lag_ret = eth.reindex(idx).pct_change().shift(LAG)
    entries = (lead > 0.02) & (lag_ret < 0).fillna(False)
    exits = (lag_ret > 0).fillna(False)
    return _m("IA-10", "Intermarket divergence", "ETH lag BTC", "crypto", eth.reindex(idx), entries, exits, symbol="ETHUSDT")


def run_Q_01() -> SweepResult:
    raise SkipStrategy("fundamentals required")


def run_Q_02() -> SweepResult:
    raise SkipStrategy("earnings data required")


def run_Q_03() -> SweepResult:
    raise SkipStrategy("fundamentals required")


def run_Q_04() -> SweepResult:
    raise SkipStrategy("short interest/options required")


def run_Q_05() -> SweepResult:
    raise SkipStrategy("crack spread data required")


def run_Q_06() -> SweepResult:
    from tqg_client.strategy_catalog_runners_a import run_V_05
    r = run_V_05()
    return SweepResult("Q-06", "VIX risk premium", "^VIX", "vol", r.sharpe, r.max_dd, r.cagr, r.trades)


def run_Q_07() -> SweepResult:
    raise SkipStrategy("intraday SPY upload required")


def run_Q_08() -> SweepResult:
    _, close = _btc()
    x = close.pct_change().fillna(0)
    pred = x.rolling(20).mean().shift(LAG)
    signal = (pred > 0).fillna(False)
    entries = signal
    exits = ~signal
    return _m("Q-08", "Recursive LS proxy", "BTCUSDT", "crypto", close, entries, exits)


def run_Q_09() -> SweepResult:
    _, close = _btc()
    vol = close.pct_change().rolling(20).std()
    high = (vol > vol.rolling(252).median()).shift(LAG).fillna(False)
    mom = (close.pct_change(60).shift(LAG) > 0).fillna(False)
    entries = ~high & mom
    exits = high | ~mom
    return _m("Q-09", "Regime overlay proxy", "BTCUSDT", "crypto", close, entries, exits)


def run_Q_10() -> SweepResult:
    raise SkipStrategy("margin debt/GDP macro upload required")
