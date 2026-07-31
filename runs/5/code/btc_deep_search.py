#!/usr/bin/env python3
"""Exhaustive BTC pure-signal search: Sharpe>=1, MaxDD<25%, min trades."""

from __future__ import annotations

import itertools
import json
from dataclasses import asdict, dataclass
from pathlib import Path

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
)

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs" / "5"
DATA = REPO / "data"
ANN = 365
MIN_TRADES = 8


@dataclass
class Hit:
    family: str
    name: str
    params: dict
    sharpe: float
    max_dd: float
    sharpe_is: float
    sharpe_oos: float
    trades: int
    exposure: float


def load_data() -> tuple[pd.DataFrame, pd.Series]:
    df, _ = load_market_data("BTCUSDT", data_dir=DATA, interval="1d")
    df = df.sort_index()
    return df, df["close"].astype(float)


def pos_from_signals(
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


def eval_pos(close: pd.Series, pos: pd.Series) -> dict:
    asset = close.pct_change().fillna(0)
    r = pos.shift(1).fillna(0) * asset - pos.diff().abs().fillna(0) * (FEE + SLIPPAGE)
    rr = r.dropna()
    if len(rr) < 30 or rr.std() == 0:
        return {"sharpe": 0.0, "max_dd": 0.0, "sharpe_is": 0.0, "sharpe_oos": 0.0, "trades": 0, "exposure": 0.0, "pos": pos, "r": r}
    cum = (1 + rr).cumprod()
    dd = cum / cum.cummax() - 1
    sh = float(np.sqrt(ANN) * rr.mean() / rr.std())
    is_r = rr.loc[rr.index < OOS]
    oos_r = rr.loc[rr.index >= OOS]

    def _sh(s: pd.Series) -> float:
        return float(np.sqrt(ANN) * s.mean() / s.std()) if len(s) > 10 and s.std() > 0 else 0.0

    return {
        "sharpe": sh,
        "max_dd": float(dd.min()),
        "sharpe_is": _sh(is_r),
        "sharpe_oos": _sh(oos_r),
        "trades": int(pos.diff().abs().fillna(0).gt(0).sum()),
        "exposure": float(pos.abs().mean()),
        "pos": pos,
        "r": r,
    }


def trail_pos(close: pd.Series, entry_sig: pd.Series, trail_pct: float) -> pd.Series:
    pos = pd.Series(0.0, index=close.index)
    state = 0.0
    peak = 0.0
    for t in close.index:
        sig = bool(entry_sig.loc[t])
        p = float(close.loc[t])
        if state == 0.0 and sig:
            state = 1.0
            peak = p
        elif state > 0:
            peak = max(peak, p)
            if (p / peak - 1) < -trail_pct or not sig:
                state = 0.0
        pos.loc[t] = state
    return pos


def consider(hits: list[Hit], family: str, name: str, params: dict, m: dict) -> None:
    if m["sharpe"] >= 1.0 and m["max_dd"] > -0.25 and m["trades"] >= MIN_TRADES:
        hits.append(
            Hit(
                family=family,
                name=name,
                params=params,
                sharpe=m["sharpe"],
                max_dd=m["max_dd"],
                sharpe_is=m["sharpe_is"],
                sharpe_oos=m["sharpe_oos"],
                trades=m["trades"],
                exposure=m["exposure"],
            )
        )


def run_search() -> list[Hit]:
    df, close = load_data()
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    vol = df["volume"].astype(float)

    puell = align_to_close(load_coinglass_daily("puell_multiple.csv", "puell_multiple"), close.index)
    fund = align_to_close(load_coinglass_daily("futures_funding_rate_binance_1d.parquet"), close.index)
    liq = align_to_close(load_coinglass_daily("futures_liquidations_binance_1d.parquet", "long_liquidation_usd"), close.index)
    flow = align_to_close(load_coinglass_daily("etf_flows_btc.parquet", "flow_usd").rolling(5).sum(), close.index)

    ob = pd.read_parquet(DATA / "coinglass" / "futures_orderbook_pair_binance_1d.parquet")
    ob = ob[ob["symbol"].astype(str).str.upper() == "BTCUSDT"]
    ob.index = pd.to_datetime(ob["date"], utc=True)
    imb = align_to_close((ob["bids_usd"] - ob["asks_usd"]) / (ob["bids_usd"] + ob["asks_usd"]), close.index)

    hits: list[Hit] = []

    # --- Trend long-flat + trailing stop ---
    for ma_w in range(30, 201, 10):
        ma = close.rolling(ma_w).mean().shift(LAG)
        entry = (close.shift(LAG) > ma).fillna(False)
        for trail in np.arange(0.06, 0.26, 0.02):
            pos = trail_pos(close, entry, trail)
            consider(hits, "trend_trail", f"SMA{ma_w}+trail{trail:.0%}", {"ma": ma_w, "trail": float(trail)}, eval_pos(close, pos))

    # --- Dual MA + trail ---
    for fast, slow in itertools.product([20, 30, 50], [100, 150, 200]):
        maf = close.rolling(fast).mean().shift(LAG)
        mas = close.rolling(slow).mean().shift(LAG)
        entry = (maf > mas).fillna(False)
        for trail in [0.08, 0.10, 0.12, 0.15, 0.18]:
            pos = trail_pos(close, entry, trail)
            consider(hits, "dual_ma_trail", f"MA{fast}/{slow}+trail{trail:.0%}", {"fast": fast, "slow": slow, "trail": trail}, eval_pos(close, pos))

    # --- CMMA + macro filter + trail ---
    log_p = np.log(close)
    a = atr(high, low, close)
    for k in [20, 30, 40, 50, 60]:
        cmma = ((log_p - log_p.rolling(k).mean()) / a).shift(LAG)
        for tma in [100, 150, 200]:
            macro = close.rolling(tma).mean().shift(LAG)
            entry = (cmma > 0) & (close.shift(LAG) > macro).fillna(False)
            for trail in [0.08, 0.10, 0.12, 0.15]:
                pos = trail_pos(close, entry, trail)
                consider(hits, "cmma_trail", f"CMMA{k}+MA{tma}+trail{trail:.0%}", {"k": k, "tma": tma, "trail": trail}, eval_pos(close, pos))

    # --- TSMOM + SMA gate + trail ---
    for lb in [63, 126, 189, 252]:
        mom = close.pct_change(lb - 21).shift(LAG) > 0
        for tma in [100, 150, 200]:
            ma = close.rolling(tma).mean().shift(LAG)
            entry = mom & (close.shift(LAG) > ma).fillna(False)
            for trail in [0.08, 0.10, 0.12, 0.15, 0.18]:
                pos = trail_pos(close, entry, trail)
                consider(hits, "tsmom_trail", f"TSMOM{lb}+MA{tma}", {"lb": lb, "tma": tma, "trail": trail}, eval_pos(close, pos))

    # --- Puell variants ---
    for ent in np.arange(0.45, 0.85, 0.05):
        for ex in np.arange(1.0, 2.0, 0.1):
            for tma in [100, 150, 200]:
                e = (close.shift(LAG) > close.rolling(tma).mean().shift(LAG)) & (puell < ent).fillna(False)
                x = (puell > ex).fillna(False)
                consider(hits, "puell", f"Puell {ent}/{ex}/MA{tma}", {"ent": float(ent), "ex": float(ex), "tma": tma}, eval_pos(close, pos_from_signals(close, e, x)))

    # --- Puell OR liq spike ---
    for q in [0.90, 0.93, 0.95]:
        spike = (liq > liq.rolling(90).quantile(q)).shift(LAG).fillna(False)
        for ent, ex in itertools.product([0.5, 0.6, 0.7], [1.2, 1.5, 1.8]):
            e = ((puell < ent) | spike).fillna(False)
            x = (puell > ex).fillna(False)
            consider(hits, "puell_liq", f"Puell|Liq q={q}", {"q": q, "ent": ent, "ex": ex}, eval_pos(close, pos_from_signals(close, e, x)))

    # --- IBS pullback extended ---
    for tma in range(75, 201, 25):
        ma = close.rolling(tma).mean().shift(LAG)
        ibs = ((close - low) / (high - low).replace(0, np.nan)).shift(LAG)
        rsi = vbt.RSI.run(close, 14).rsi.shift(LAG)
        for ibs_thr in np.arange(0.10, 0.40, 0.05):
            for rsi_thr in range(25, 46, 5):
                for exit_ibs in [0.4, 0.5, 0.6, 0.7]:
                    e = (close.shift(LAG) > ma) & (ibs < ibs_thr) & (rsi < rsi_thr).fillna(False)
                    x = (ibs > exit_ibs).fillna(False) | (close.shift(LAG) < ma).fillna(False)
                    consider(hits, "ibs", f"IBS tma={tma}", {"tma": tma, "ibs": float(ibs_thr), "rsi": rsi_thr, "exit": exit_ibs}, eval_pos(close, pos_from_signals(close, e, x)))

    # --- RSI long-short with ER gate ---
    for rw in [7, 14, 21]:
        rsi = vbt.RSI.run(close, window=rw).rsi.shift(LAG)
        er = efficiency_ratio(close, 20).shift(LAG)
        for er_thr in [0.3, 0.4, 0.5, 0.6]:
            for lo, hi in [(25, 75), (30, 70), (35, 65)]:
                e = (er > er_thr) & (rsi < lo).fillna(False)
                x = (rsi > 50).fillna(False)
                se = (er > er_thr) & (rsi > hi).fillna(False)
                sx = (rsi < 50).fillna(False)
                consider(
                    hits, "rsi_ls", f"RSI LS {rw}", {"rw": rw, "er": er_thr, "lo": lo, "hi": hi},
                    eval_pos(close, pos_from_signals(close, e, x, short_entries=se, short_exits=sx)),
                )

    # --- Funding long-short ---
    for qlo, qhi in itertools.product([0.05, 0.10, 0.15], [0.85, 0.90, 0.95]):
        e = (fund < fund.rolling(90).quantile(qlo)).fillna(False)
        x = (fund > fund.rolling(90).quantile(0.5)).fillna(False)
        se = (fund > fund.rolling(90).quantile(qhi)).fillna(False)
        sx = (fund < fund.rolling(90).quantile(0.5)).fillna(False)
        consider(
            hits, "fund_ls", f"Funding LS {qlo}/{qhi}", {"qlo": qlo, "qhi": qhi},
            eval_pos(close, pos_from_signals(close, e, x, short_entries=se, short_exits=sx)),
        )

    # --- Orderbook + trend ---
    for ent in np.arange(0.04, 0.14, 0.02):
        for tma in [50, 100, 150, 200]:
            ma = close.rolling(tma).mean().shift(LAG)
            e = (close.shift(LAG) > ma) & (imb > ent).fillna(False)
            x = (imb < 0).fillna(False)
            consider(hits, "ob", f"OB {ent}/MA{tma}", {"ent": float(ent), "tma": tma}, eval_pos(close, pos_from_signals(close, e, x)))

    # --- Liquidation spike holds ---
    for q in [0.88, 0.90, 0.93, 0.95, 0.97]:
        for hold in [3, 5, 7, 10, 14]:
            spike = (liq > liq.rolling(90).quantile(q)).shift(LAG).fillna(False)
            e = spike
            x = spike.shift(hold).fillna(False)
            consider(hits, "liq", f"Liq q={q} hold={hold}", {"q": q, "hold": hold}, eval_pos(close, pos_from_signals(close, e, x)))

    # --- ETF flow + MA ---
    for sm in [3, 5, 7, 10]:
        f = align_to_close(load_coinglass_daily("etf_flows_btc.parquet", "flow_usd").rolling(sm).sum(), close.index)
        for tma in [0, 100, 150, 200]:
            trend = (close.shift(LAG) > close.rolling(tma).mean().shift(LAG)) if tma else pd.Series(True, index=close.index)
            e = trend & (f > 0).fillna(False)
            x = (f < 0).fillna(False)
            consider(hits, "etf", f"ETF {sm}d MA{tma}", {"sm": sm, "tma": tma}, eval_pos(close, pos_from_signals(close, e, x)))

    # --- Low vol fade ---
    for vw in [20, 30, 60]:
        vq = vol.rolling(vw).quantile(0.15).shift(LAG)
        for drop in [0.015, 0.02, 0.025, 0.03]:
            ret1 = close.pct_change().shift(LAG)
            e = (vol.shift(LAG) < vq) & (ret1 < -drop).fillna(False)
            x = (ret1 > 0).fillna(False)
            consider(hits, "lowvol", f"LowVol vw={vw}", {"vw": vw, "drop": drop}, eval_pos(close, pos_from_signals(close, e, x)))

    # --- Triple vote conservative ---
    for w1, w2, w3, minv in itertools.product([20, 50], [50, 100], [100, 200], [2, 3]):
        vote = (
            (close.shift(LAG) > close.rolling(w1).mean().shift(LAG)).astype(int)
            + (close.pct_change(w2).shift(LAG) > 0).astype(int)
            + (close.shift(LAG) > close.rolling(w3).mean().shift(LAG)).astype(int)
        )
        entry = (vote >= minv).fillna(False)
        for trail in [0.10, 0.12, 0.15]:
            pos = trail_pos(close, entry, trail)
            consider(hits, "vote_trail", f"Vote {minv}/3+trail", {"w1": w1, "w2": w2, "w3": w3, "minv": minv, "trail": trail}, eval_pos(close, pos))

    # --- Regime: long TSMOM bull, short RSI bear ---
    rsi14 = vbt.RSI.run(close, 14).rsi.shift(LAG)
    for bull_ma in [100, 150, 200]:
        bull = (close.shift(LAG) > close.rolling(bull_ma).mean().shift(LAG)).fillna(False)
        mom = close.pct_change(126).shift(LAG) > 0
        pos = pd.Series(0.0, index=close.index)
        for t in close.index:
            if bull.loc[t] and mom.loc[t]:
                pos.loc[t] = 1.0
            elif not bull.loc[t]:
                if rsi14.loc[t] < 30:
                    pos.loc[t] = 1.0
                elif rsi14.loc[t] > 70:
                    pos.loc[t] = -1.0
        consider(hits, "regime", f"Regime MA{bull_ma}", {"bull_ma": bull_ma}, eval_pos(close, pos))

    # --- Weekly SMA mapped to daily ---
    w = close.resample("W").last().dropna()
    for win in [8, 10, 12, 16, 20, 26]:
        wma = w.rolling(win).mean().shift(LAG)
        wpos = (w.shift(LAG) > wma).astype(float)
        daily_pos = wpos.reindex(close.index, method="ffill").fillna(0)
        consider(hits, "weekly_sma", f"Weekly SMA{win}", {"win": win}, eval_pos(close, daily_pos))

    return hits


def select_diverse(hits: list[Hit], k: int = 5) -> list[Hit]:
    hits = sorted(hits, key=lambda h: (h.sharpe, h.max_dd), reverse=True)
    chosen: list[Hit] = []
    families: set[str] = set()
    for h in hits:
        if h.family in families:
            continue
        chosen.append(h)
        families.add(h.family)
        if len(chosen) >= k:
            break
    if len(chosen) < k:
        for h in hits:
            if h not in chosen:
                chosen.append(h)
            if len(chosen) >= k:
                break
    return chosen[:k]


def main() -> None:
    hits = run_search()
    hits.sort(key=lambda h: -h.sharpe)
    print(f"Total qualifying hits (Sharpe>=1, DD<25%, trades>={MIN_TRADES}): {len(hits)}")
    for h in hits[:30]:
        print(
            f"  {h.family:14} {h.name[:40]:40} sh={h.sharpe:.2f} dd={h.max_dd:.1%} "
            f"is={h.sharpe_is:.2f} oos={h.sharpe_oos:.2f} tr={h.trades}"
        )

    diverse = select_diverse(hits, 5)
    out = {
        "min_trades": MIN_TRADES,
        "total_hits": len(hits),
        "top_30": [asdict(h) for h in hits[:30]],
        "diverse_5": [asdict(h) for h in diverse],
    }
    (RUN / "artifacts").mkdir(parents=True, exist_ok=True)
    (RUN / "artifacts" / "deep_search_hits.json").write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nDiverse 5 families: {len(diverse)}")
    for h in diverse:
        print(f"  {h.family}: {h.name} sh={h.sharpe:.2f} dd={h.max_dd:.1%}")


if __name__ == "__main__":
    main()
