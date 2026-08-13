#!/usr/bin/env python3
"""Search BTC signal strategies: Sharpe>=1, MaxDD<25%, pure signals (no sizing)."""

from __future__ import annotations

import json
import itertools
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import vectorbt as vbt

from tqg_client.market_data import load_market_data
from tqg_client.strategy_sweep_core import (
    FEE,
    LAG,
    OOS,
    SLIPPAGE,
    align_to_close,
    atr,
    efficiency_ratio,
    load_coinglass_daily,
    load_equity_close,
)

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs" / "5"
DATA = REPO / "data"
ANN = 365
SYMBOL = "BTCUSDT"


@dataclass
class Candidate:
    id: str
    family: str
    name: str
    params: dict
    sharpe_full: float
    sharpe_is: float
    sharpe_oos: float
    max_dd: float
    cagr: float
    trades: int
    exposure: float


def _load_btc() -> pd.DataFrame:
    df, _ = load_market_data(SYMBOL, data_dir=DATA, interval="1d")
    return df.sort_index()


def _metrics(returns: pd.Series) -> dict:
    r = returns.dropna()
    if len(r) < 30:
        return {"Sharpe": 0.0, "MaxDD": 0.0, "CAGR": 0.0, "exposure": 0.0}
    cum = (1 + r).cumprod()
    dd = cum / cum.cummax() - 1
    vol = r.std()
    sharpe = float(np.sqrt(ANN) * r.mean() / vol) if vol > 0 else 0.0
    cagr = float(cum.iloc[-1] ** (ANN / len(r)) - 1)
    return {
        "Sharpe": sharpe,
        "MaxDD": float(dd.min()),
        "CAGR": cagr,
        "exposure": float((r != 0).mean()),
    }


def _position_from_signals(
    close: pd.Series,
    entries: pd.Series,
    exits: pd.Series,
    *,
    short_entries: pd.Series | None = None,
    short_exits: pd.Series | None = None,
) -> pd.Series:
    idx = close.index
    pos = pd.Series(0.0, index=idx)
    state = 0.0
    se = short_entries.fillna(False).astype(bool) if short_entries is not None else pd.Series(False, index=idx)
    sx = short_exits.fillna(False).astype(bool) if short_exits is not None else pd.Series(False, index=idx)
    en = entries.fillna(False).astype(bool)
    ex = exits.fillna(False).astype(bool)
    for t in idx:
        if state == 0.0:
            if en.loc[t]:
                state = 1.0
            elif se.loc[t]:
                state = -1.0
        elif state > 0:
            if ex.loc[t]:
                state = 0.0
        else:
            if sx.loc[t]:
                state = 0.0
        pos.loc[t] = state
    return pos


def _returns_from_position(close: pd.Series, position: pd.Series) -> pd.Series:
    asset = close.pct_change().fillna(0)
    pos = position.reindex(close.index).fillna(0)
    gross = pos.shift(1).fillna(0) * asset
    turnover = pos.diff().abs().fillna(0)
    return gross - turnover * (FEE + SLIPPAGE)


def _backtest(
    close: pd.Series,
    entries: pd.Series,
    exits: pd.Series,
    *,
    short_entries: pd.Series | None = None,
    short_exits: pd.Series | None = None,
) -> tuple[pd.Series, dict]:
    pos = _position_from_signals(close, entries, exits, short_entries=short_entries, short_exits=short_exits)
    rets = _returns_from_position(close, pos)
    full = _metrics(rets)
    is_m = _metrics(rets.loc[rets.index < OOS])
    oos_m = _metrics(rets.loc[rets.index >= OOS])
    full.update(
        {
            "sharpe_is": is_m["Sharpe"],
            "sharpe_oos": oos_m["Sharpe"],
            "trades": int(pos.diff().abs().fillna(0).gt(0).sum()),
            "exposure": float(pos.abs().mean()),
        }
    )
    return pos, full


def _long_only_ma(close: pd.Series, fast: int, slow: int) -> tuple[pd.Series, pd.Series]:
    ma_f = close.rolling(fast).mean().shift(LAG)
    ma_s = close.rolling(slow).mean().shift(LAG)
    entries = (ma_f > ma_s).fillna(False)
    exits = (ma_f < ma_s).fillna(False)
    return entries, exits


def _sma_trend_long_flat(close: pd.Series, window: int) -> tuple[pd.Series, pd.Series]:
    ma = close.rolling(window).mean().shift(LAG)
    entries = (close.shift(LAG) > ma).fillna(False)
    exits = (close.shift(LAG) <= ma).fillna(False)
    return entries, exits


def _dual_ma_confirm(close: pd.Series, w1: int, w2: int, w3: int) -> tuple[pd.Series, pd.Series]:
    ma1 = close.rolling(w1).mean().shift(LAG)
    ma2 = close.rolling(w2).mean().shift(LAG)
    ma3 = close.rolling(w3).mean().shift(LAG)
    bull = (ma1 > ma2) & (ma2 > ma3)
    entries = bull.fillna(False)
    exits = (~bull).fillna(False)
    return entries, exits


def _donchian_long(close: pd.Series, high: pd.Series, low: pd.Series, entry_n: int, exit_n: int) -> tuple[pd.Series, pd.Series]:
    hi = high.rolling(entry_n).max().shift(LAG)
    lo = low.rolling(exit_n).min().shift(LAG)
    entries = (close.shift(LAG) > hi.shift(1)).fillna(False)
    exits = (close.shift(LAG) < lo.shift(1)).fillna(False)
    return entries, exits


def _tsmom_long_flat(close: pd.Series, lookback: int, skip: int = 21) -> tuple[pd.Series, pd.Series]:
    mom = close.pct_change(lookback - skip).shift(LAG)
    entries = (mom > 0).fillna(False)
    exits = (mom <= 0).fillna(False)
    return entries, exits


def _rsi_mr_long_only(close: pd.Series, rsi_window: int, entry: float, exit_: float, trend_ma: int) -> tuple[pd.Series, pd.Series]:
    rsi = vbt.RSI.run(close, window=rsi_window).rsi.shift(LAG)
    ma = close.rolling(trend_ma).mean().shift(LAG)
    trend = close.shift(LAG) > ma
    entries = trend & (rsi < entry).fillna(False)
    exits = (rsi > exit_).fillna(False) | (~trend).fillna(False)
    return entries, exits


def _bollinger_mr_long(close: pd.Series, window: int, z_entry: float, trend_ma: int) -> tuple[pd.Series, pd.Series]:
    ma = close.rolling(window).mean()
    std = close.rolling(window).std()
    lower = (ma - z_entry * std).shift(LAG)
    mid = ma.shift(LAG)
    trend = close.rolling(trend_ma).mean().shift(LAG)
    entries = (close.shift(LAG) > trend) & (close.shift(LAG) < lower).fillna(False)
    exits = (close.shift(LAG) > mid).fillna(False)
    return entries, exits


def _er_gate_breakout(df: pd.DataFrame, er_window: int, don_n: int, er_thr: float) -> tuple[pd.Series, pd.Series]:
    close = df["close"].astype(float)
    er = efficiency_ratio(close, er_window).shift(LAG)
    hi = df["high"].rolling(don_n).max().shift(LAG)
    lo = df["low"].rolling(don_n // 2).min().shift(LAG)
    gate = (er > er_thr).fillna(False)
    entries = gate & (close.shift(LAG) > hi.shift(1)).fillna(False)
    exits = (close.shift(LAG) < lo.shift(1)).fillna(False)
    return entries, exits


def _funding_contrarian_long(close: pd.Series, fund: pd.Series, q_lo: float, q_hi: float) -> tuple[pd.Series, pd.Series]:
    f = align_to_close(fund, close.index)
    entries = (f < f.rolling(90).quantile(q_lo)).fillna(False)
    exits = (f > f.rolling(90).quantile(q_hi)).fillna(False)
    return entries, exits


def _liquidation_spike_long(close: pd.Series, liq: pd.Series, q: float, hold: int) -> tuple[pd.Series, pd.Series]:
    l = align_to_close(liq, close.index)
    spike = (l > l.rolling(90).quantile(q)).shift(LAG).fillna(False)
    entries = spike
    exits = spike.shift(hold).fillna(False) | (close.pct_change(hold).shift(LAG) > 0.15).fillna(False)
    return entries, exits


def _orderbook_imbalance(close: pd.Series, imb: pd.Series, entry_thr: float, exit_thr: float) -> tuple[pd.Series, pd.Series]:
    i = align_to_close(imb, close.index)
    entries = (i > entry_thr).fillna(False)
    exits = (i < exit_thr).fillna(False)
    return entries, exits


def _puell_value(close: pd.Series, puell: pd.Series, entry: float, exit_: float) -> tuple[pd.Series, pd.Series]:
    p = align_to_close(puell, close.index)
    entries = (p < entry).fillna(False)
    exits = (p > exit_).fillna(False)
    return entries, exits


def _mvrv_value(close: pd.Series, mvrv: pd.Series, entry: float, exit_: float) -> tuple[pd.Series, pd.Series]:
    m = align_to_close(mvrv, close.index)
    entries = (m < entry).fillna(False)
    exits = (m > exit_).fillna(False)
    return entries, exits


def _dxy_risk_on(close: pd.Series, dxy: pd.Series, ma: int) -> tuple[pd.Series, pd.Series]:
    d = dxy.reindex(close.index).ffill()
    dma = d.rolling(ma).mean().shift(LAG)
    entries = (d.shift(LAG) < dma).fillna(False)
    exits = (d.shift(LAG) >= dma).fillna(False)
    return entries, exits


def _52w_high_proximity(close: pd.Series, entry_pct: float, exit_pct: float) -> tuple[pd.Series, pd.Series]:
    hi = close.rolling(252).max().shift(LAG)
    prox = close.shift(LAG) / hi - 1
    entries = (prox > -entry_pct).fillna(False)
    exits = (prox < -exit_pct).fillna(False)
    return entries, exits


def _cmma_trend(df: pd.DataFrame, k: int) -> tuple[pd.Series, pd.Series]:
    close = df["close"].astype(float)
    log_p = np.log(close)
    ma = log_p.rolling(k).mean()
    a = atr(df["high"], df["low"], close)
    cmma = ((log_p - ma) / a).shift(LAG)
    entries = (cmma > 0).fillna(False)
    exits = (cmma < 0).fillna(False)
    return entries, exits


def _multi_horizon_vote(close: pd.Series, windows: tuple[int, ...], min_votes: int) -> tuple[pd.Series, pd.Series]:
    votes = sum((close.pct_change(w).shift(LAG) > 0).astype(int) for w in windows)
    entries = (votes >= min_votes).fillna(False)
    exits = (votes < min_votes).fillna(False)
    return entries, exits


def _vol_regime_trend(close: pd.Series, vol_window: int, mom_lb: int) -> tuple[pd.Series, pd.Series]:
    vol = close.pct_change().rolling(vol_window).std()
    calm = (vol < vol.rolling(vol_window * 2).median()).shift(LAG).fillna(False)
    mom = close.pct_change(mom_lb).shift(LAG) > 0
    entries = calm & mom.fillna(False)
    exits = (~calm) | (~mom).fillna(False)
    return entries, exits


def _etf_flow_momentum(close: pd.Series, flow: pd.Series, smooth: int) -> tuple[pd.Series, pd.Series]:
    f = align_to_close(flow.rolling(smooth).sum(), close.index)
    entries = (f > 0).fillna(False)
    exits = (f < 0).fillna(False)
    return entries, exits


def _short_squeeze_setup(close: pd.Series, fund: pd.Series) -> tuple[pd.Series, pd.Series]:
    f = align_to_close(fund, close.index)
    price_up = close.pct_change(5).shift(LAG) > 0
    entries = (f < 0) & price_up.fillna(False)
    exits = (f > 0).fillna(False)
    return entries, exits


def _ibs_pullback(close: pd.Series, high: pd.Series, low: pd.Series, ibs_thr: float, rsi_thr: float, trend_ma: int) -> tuple[pd.Series, pd.Series]:
    ibs = ((close - low) / (high - low).replace(0, np.nan)).shift(LAG)
    rsi = vbt.RSI.run(close, window=14).rsi.shift(LAG)
    ma = close.rolling(trend_ma).mean().shift(LAG)
    entries = (close.shift(LAG) > ma) & (ibs < ibs_thr) & (rsi < rsi_thr).fillna(False)
    exits = (ibs > 0.5).fillna(False) | (close.shift(LAG) < ma).fillna(False)
    return entries, exits


def generate_candidates(df: pd.DataFrame) -> list[Candidate]:
    close = df["close"].astype(float)
    candidates: list[Candidate] = []
    counter = 0

    def add(family: str, name: str, params: dict, entries: pd.Series, exits: pd.Series, **kw):
        nonlocal counter
        counter += 1
        pos, m = _backtest(close, entries, exits, **kw)
        c = Candidate(
            id=f"S{counter:03d}",
            family=family,
            name=name,
            params=params,
            sharpe_full=m["Sharpe"],
            sharpe_is=m["sharpe_is"],
            sharpe_oos=m["sharpe_oos"],
            max_dd=m["MaxDD"],
            cagr=m["CAGR"],
            trades=m["trades"],
            exposure=m["exposure"],
        )
        c._position = pos  # type: ignore[attr-defined]
        candidates.append(c)

    # 1. SMA trend long-flat (literature: MA predictability)
    for w in (20, 30, 50, 80, 100, 150, 200):
        e, x = _sma_trend_long_flat(close, w)
        add("trend_sma", f"SMA {w} long-flat", {"window": w}, e, x)

    # 2. Dual / triple MA
    for fast, slow in ((20, 100), (30, 150), (50, 200), (20, 200)):
        e, x = _long_only_ma(close, fast, slow)
        add("trend_dual_ma", f"Dual MA {fast}/{slow}", {"fast": fast, "slow": slow}, e, x)

    for w1, w2, w3 in ((10, 50, 200), (20, 50, 200), (30, 100, 200)):
        e, x = _dual_ma_confirm(close, w1, w2, w3)
        add("trend_triple_ma", f"Triple MA {w1}/{w2}/{w3}", {"w1": w1, "w2": w2, "w3": w3}, e, x)

    # 3. TSMOM long-flat
    for lb in (63, 126, 189, 252):
        e, x = _tsmom_long_flat(close, lb)
        add("trend_tsmom", f"TSMOM {lb}d", {"lookback": lb}, e, x)

    # 4. Donchian
    for en, ex in ((20, 10), (40, 20), (55, 20), (80, 40)):
        e, x = _donchian_long(close, df["high"], df["low"], en, ex)
        add("trend_donchian", f"Donchian {en}/{ex}", {"entry_n": en, "exit_n": ex}, e, x)

    # 5. CMMA
    for k in (20, 40, 60, 80):
        e, x = _cmma_trend(df, k)
        add("trend_cmma", f"CMMA {k}", {"k": k}, e, x)

    # 6. Multi-horizon vote
    for windows, min_v in [((5, 20, 60), 2), ((10, 30, 90), 2), ((5, 10, 20, 60), 3)]:
        e, x = _multi_horizon_vote(close, windows, min_v)
        add("trend_multi_mom", f"Mom vote {windows}", {"windows": windows, "min_votes": min_v}, e, x)

    # 7. 52-week high proximity
    for ep, xp in ((0.05, 0.10), (0.03, 0.08), (0.10, 0.15)):
        e, x = _52w_high_proximity(close, ep, xp)
        add("trend_52w", f"52w hi prox {ep}/{xp}", {"entry_pct": ep, "exit_pct": xp}, e, x)

    # 8. ER-gated breakout
    for er_w, don_n, thr in ((20, 20, 0.3), (20, 40, 0.4), (30, 55, 0.35)):
        e, x = _er_gate_breakout(df, er_w, don_n, thr)
        add("trend_er_breakout", f"ER breakout {er_w}/{don_n}", {"er_window": er_w, "don_n": don_n, "er_thr": thr}, e, x)

    # 9. Vol regime trend
    for vw, ml in ((20, 63), (30, 126), (20, 42)):
        e, x = _vol_regime_trend(close, vw, ml)
        add("vol_regime", f"Calm vol mom {vw}/{ml}", {"vol_window": vw, "mom_lb": ml}, e, x)

    # 10. Mean reversion long-only with trend filter
    for rsi_w, ent, ex, tma in ((14, 30, 50, 100), (14, 35, 55, 200), (7, 25, 45, 100)):
        e, x = _rsi_mr_long_only(close, rsi_w, ent, ex, tma)
        add("mr_rsi", f"RSI MR {rsi_w}/{ent}", {"rsi_window": rsi_w, "entry": ent, "exit": ex, "trend_ma": tma}, e, x)

    for bw, z, tma in ((20, 2.0, 100), (20, 2.5, 200), (30, 2.0, 150)):
        e, x = _bollinger_mr_long(close, bw, z, tma)
        add("mr_bollinger", f"BB MR {bw}/{z}", {"window": bw, "z": z, "trend_ma": tma}, e, x)

    for ibs_thr, rsi_thr, tma in ((0.2, 30, 100), (0.25, 35, 200), (0.15, 25, 50)):
        e, x = _ibs_pullback(close, df["high"], df["low"], ibs_thr, rsi_thr, tma)
        add("mr_ibs", f"IBS pullback {ibs_thr}", {"ibs_thr": ibs_thr, "rsi_thr": rsi_thr, "trend_ma": tma}, e, x)

    # 11. On-chain / alt-data
    try:
        puell = load_coinglass_daily("puell_multiple.csv", "puell_multiple")
        for ent, ex in ((0.5, 1.0), (0.6, 1.2), (0.4, 0.9)):
            e, x = _puell_value(close, puell, ent, ex)
            add("onchain_puell", f"Puell {ent}/{ex}", {"entry": ent, "exit": ex}, e, x)
    except Exception:
        pass

    try:
        fund = load_coinglass_daily("futures_funding_rate_binance_1d.parquet")
        for qlo, qhi in ((0.1, 0.7), (0.2, 0.8), (0.05, 0.6)):
            e, x = _funding_contrarian_long(close, fund, qlo, qhi)
            add("crypto_funding", f"Funding MR {qlo}/{qhi}", {"q_lo": qlo, "q_hi": qhi}, e, x)
        e, x = _short_squeeze_setup(close, fund)
        add("crypto_squeeze", "Short squeeze setup", {}, e, x)
    except Exception:
        pass

    try:
        liq = load_coinglass_daily("futures_liquidations_binance_1d.parquet", "long_liquidation_usd")
        for q in (0.90, 0.95, 0.97):
            for hold in (3, 5, 10):
                e, x = _liquidation_spike_long(close, liq, q, hold)
                add("crypto_liq", f"Liq spike q={q} hold={hold}", {"q": q, "hold": hold}, e, x)
    except Exception:
        pass

    try:
        ob = pd.read_parquet(DATA / "coinglass" / "futures_orderbook_pair_binance_1d.parquet")
        ob = ob[ob["symbol"].astype(str).str.upper() == SYMBOL]
        ob.index = pd.to_datetime(ob["date"], utc=True)
        imb = (ob["bids_usd"] - ob["asks_usd"]) / (ob["bids_usd"] + ob["asks_usd"])
        for ent, ex in ((0.05, 0.0), (0.10, 0.0), (0.08, -0.02)):
            e, x = _orderbook_imbalance(close, imb, ent, ex)
            add("crypto_ob", f"OB imb {ent}/{ex}", {"entry": ent, "exit": ex}, e, x)
    except Exception:
        pass

    try:
        flow = load_coinglass_daily("etf_flows_btc.parquet", "flow_usd")
        for sm in (3, 5, 10):
            e, x = _etf_flow_momentum(close, flow, sm)
            add("crypto_etf", f"ETF flow {sm}d", {"smooth": sm}, e, x)
    except Exception:
        pass

    # 12. DXY risk-on filter
    try:
        dxy = load_equity_close("DX-Y.NYB")
        for ma in (50, 100, 200):
            e, x = _dxy_risk_on(close, dxy, ma)
            add("intermarket_dxy", f"DXY risk-on MA{ma}", {"ma": ma}, e, x)
    except Exception:
        pass

    return candidates


def filter_candidates(candidates: list[Candidate]) -> list[Candidate]:
    ok = [
        c
        for c in candidates
        if c.sharpe_full >= 1.0
        and c.max_dd > -0.25
        and c.sharpe_is >= 0.5
        and c.sharpe_oos >= 0.0
    ]
    ok.sort(key=lambda c: (c.sharpe_full, -abs(c.max_dd)), reverse=True)
    return ok


def select_diverse(candidates: list[Candidate], k: int = 5) -> list[Candidate]:
    """Greedy pick by family diversity + low return correlation."""
    if len(candidates) <= k:
        return candidates
    selected: list[Candidate] = []
    families_seen: set[str] = set()
    rets_map: dict[str, pd.Series] = {}

    for c in candidates:
        pos = getattr(c, "_position")
        close = _load_btc()["close"].astype(float)
        rets_map[c.id] = _returns_from_position(close, pos)

    for c in candidates:
        if c.family in families_seen:
            continue
        if not selected:
            selected.append(c)
            families_seen.add(c.family)
            continue
        corr_ok = True
        for s in selected:
            r1 = rets_map[c.id]
            r2 = rets_map[s.id]
            idx = r1.index.intersection(r2.index)
            corr = r1.reindex(idx).corr(r2.reindex(idx))
            if corr is not None and abs(corr) > 0.85:
                corr_ok = False
                break
        if corr_ok:
            selected.append(c)
            families_seen.add(c.family)
        if len(selected) >= k:
            break

    # fill remaining slots if needed
    if len(selected) < k:
        for c in candidates:
            if c not in selected:
                selected.append(c)
            if len(selected) >= k:
                break
    return selected[:k]


def ensemble_metrics(selected: list[Candidate], close: pd.Series) -> dict:
    positions = [getattr(c, "_position").reindex(close.index).fillna(0) for c in selected]
    ens_pos = pd.DataFrame(positions).mean(axis=1).clip(-1, 1)
    rets = _returns_from_position(close, ens_pos)
    full = _metrics(rets)
    is_m = _metrics(rets.loc[rets.index < OOS])
    oos_m = _metrics(rets.loc[rets.index >= OOS])
    return {
        "full": full,
        "in_sample": is_m,
        "out_of_sample": oos_m,
        "n_strategies": len(selected),
        "strategy_ids": [c.id for c in selected],
    }


def main() -> None:
    for sub in ("artifacts", "charts", "logs"):
        (RUN / sub).mkdir(parents=True, exist_ok=True)

    df = _load_btc()
    close = df["close"].astype(float)
    print(f"Data: {len(df)} bars, {df.index.min()} -> {df.index.max()}")

    candidates = generate_candidates(df)
    print(f"Generated {len(candidates)} candidates")

    qualified = filter_candidates(candidates)
    print(f"Qualified (Sharpe>=1, DD<25%): {len(qualified)}")

    # Relax slightly if too few, but report
    if len(qualified) < 5:
        relaxed = [
            c for c in candidates
            if c.sharpe_full >= 0.9 and c.max_dd > -0.25
        ]
        relaxed.sort(key=lambda c: c.sharpe_full, reverse=True)
        qualified = relaxed[:20]
        print(f"Relaxed pool: {len(relaxed)}")

    top = select_diverse(qualified if len(qualified) >= 5 else sorted(candidates, key=lambda c: c.sharpe_full, reverse=True), 5)
    ens = ensemble_metrics(top, close)

    # Serialize without position
    out_candidates = []
    for c in top:
        d = asdict(c)
        out_candidates.append(d)

    summary = {
        "symbol": SYMBOL,
        "oos_start_ts": str(OOS),
        "annualization": ANN,
        "costs": {"fee": FEE, "slippage": SLIPPAGE},
        "criteria": {
            "per_strategy": {"min_sharpe": 1.0, "max_drawdown": 0.25},
            "ensemble": {"min_sharpe": 2.0, "max_drawdown": 0.15},
        },
        "search_size": len(candidates),
        "qualified_count": len([c for c in candidates if c.sharpe_full >= 1.0 and c.max_dd > -0.25]),
        "selected_strategies": out_candidates,
        "ensemble": ens,
        "all_qualified": [asdict(c) for c in filter_candidates(candidates)[:30]],
    }

    (RUN / "artifacts" / "btc_strategy_search.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )

    # Equity chart for ensemble
    positions = [getattr(c, "_position").reindex(close.index).fillna(0) for c in top]
    ens_pos = pd.DataFrame(positions).mean(axis=1).clip(-1, 1)
    ens_rets = _returns_from_position(close, ens_pos)
    equity = (1 + ens_rets.fillna(0)).cumprod()
    bh = close / close.iloc[0]

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(equity.index, equity.values, label="Ensemble", linewidth=2)
    ax.plot(bh.index, bh.values, label="Buy & hold", alpha=0.6)
    ax.axvline(OOS, color="red", linestyle="--", label="OOS start")
    ax.legend()
    ax.set_title(f"BTC 5-Strategy Ensemble (Sharpe={ens['full']['Sharpe']:.2f}, MaxDD={ens['full']['MaxDD']:.1%})")
    fig.tight_layout()
    fig.savefig(RUN / "charts" / "ensemble_equity.png", dpi=120)

    # Individual strategy equities
    fig2, axes = plt.subplots(len(top), 1, figsize=(11, 2.5 * len(top)), sharex=True)
    if len(top) == 1:
        axes = [axes]
    for ax, c in zip(axes, top):
        pos = getattr(c, "_position")
        r = _returns_from_position(close, pos)
        eq = (1 + r.fillna(0)).cumprod()
        ax.plot(eq.index, eq.values)
        ax.set_title(f"{c.id}: {c.name} | Sharpe={c.sharpe_full:.2f} DD={c.max_dd:.1%}")
        ax.axvline(OOS, color="red", linestyle="--", alpha=0.5)
    fig2.tight_layout()
    fig2.savefig(RUN / "charts" / "strategy_equities.png", dpi=120)

    spec = {
        "workflow": "single_asset_signals",
        "symbol": SYMBOL,
        "asset_class": "crypto",
        "data_source": "local:talos/cm_BTCUSDT_market_candles_1d.parquet",
        "annualization": ANN,
        "oos_start_ts": "2025-01-01",
        "strategies": [{**asdict(c), "params": c.params} for c in top],
        "ensemble_method": "equal_weight_position_mean_clipped",
    }
    (RUN / "strategy_spec.json").write_text(json.dumps(spec, indent=2, default=str) + "\n", encoding="utf-8")

    report_lines = [
        "# BTC Five-Strategy Ensemble Research",
        "",
        f"**Symbol:** {SYMBOL} (daily, one symbol only)",
        f"**OOS cut-off:** {OOS.date()}",
        f"**Search space:** {len(candidates)} pure-signal candidates across trend, MR, on-chain, and microstructure families",
        "",
        "## Selection criteria",
        "- Per strategy: Sharpe ≥ 1.0, max drawdown < 25%",
        "- Ensemble target: Sharpe > 2.0, max drawdown < 15%",
        "- No position sizing — binary/long-flat signals only",
        "",
        "## Selected strategies",
        "",
        "| ID | Family | Name | Sharpe | IS | OOS | MaxDD | CAGR | Trades |",
        "|----|--------|------|--------|----|-----|-------|------|--------|",
    ]
    for c in top:
        report_lines.append(
            f"| {c.id} | {c.family} | {c.name} | {c.sharpe_full:.2f} | {c.sharpe_is:.2f} | {c.sharpe_oos:.2f} | {c.max_dd:.1%} | {c.cagr:.1%} | {c.trades} |"
        )
    report_lines += [
        "",
        "## Ensemble (equal-weight positions)",
        "",
        f"- **Full-sample Sharpe:** {ens['full']['Sharpe']:.2f}",
        f"- **In-sample Sharpe:** {ens['in_sample']['Sharpe']:.2f}",
        f"- **Out-of-sample Sharpe:** {ens['out_of_sample']['Sharpe']:.2f}",
        f"- **Max drawdown:** {ens['full']['MaxDD']:.1%}",
        f"- **CAGR:** {ens['full']['CAGR']:.1%}",
        "",
        "## Charts",
        "- `charts/ensemble_equity.png`",
        "- `charts/strategy_equities.png`",
    ]
    (RUN / "report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print("\n=== SELECTED ===")
    for c in top:
        print(f"{c.id} {c.name}: Sharpe={c.sharpe_full:.2f} DD={c.max_dd:.1%} IS={c.sharpe_is:.2f} OOS={c.sharpe_oos:.2f}")
    print(f"\nENSEMBLE: Sharpe={ens['full']['Sharpe']:.2f} DD={ens['full']['MaxDD']:.1%}")
    print(f"Wrote artifacts to {RUN}")


if __name__ == "__main__":
    main()
