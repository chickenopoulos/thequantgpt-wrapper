#!/usr/bin/env python3
"""Final exhaustive search: SMA+Puell+trail grid + diverse families for 5 qualifying sleeves."""

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
MIN_TRADES = 5


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


def pos_from_signals(close: pd.Series, entries: pd.Series, exits: pd.Series) -> pd.Series:
    idx = close.index
    pos = pd.Series(0.0, index=idx)
    state = 0.0
    en = entries.fillna(False).astype(bool)
    ex = exits.fillna(False).astype(bool)
    for t in idx:
        if state == 0.0 and en.loc[t]:
            state = 1.0
        elif state > 0 and ex.loc[t]:
            state = 0.0
        pos.loc[t] = state
    return pos


def eval_pos(close: pd.Series, pos: pd.Series) -> dict:
    asset = close.pct_change().fillna(0)
    r = pos.shift(1).fillna(0) * asset - pos.diff().abs().fillna(0) * (FEE + SLIPPAGE)
    rr = r.dropna()
    if len(rr) < 30 or rr.std() == 0:
        return {"sharpe": 0.0, "max_dd": 0.0, "sharpe_is": 0.0, "sharpe_oos": 0.0, "trades": 0, "exposure": 0.0}
    cum = (1 + rr).cumprod()
    dd = cum / cum.cummax() - 1
    sh = float(np.sqrt(ANN) * rr.mean() / rr.std())

    def _sh(s: pd.Series) -> float:
        return float(np.sqrt(ANN) * s.mean() / s.std()) if len(s) > 10 and s.std() > 0 else 0.0

    is_r = rr.loc[rr.index < OOS]
    oos_r = rr.loc[rr.index >= OOS]
    return {
        "sharpe": sh,
        "max_dd": float(dd.min()),
        "sharpe_is": _sh(is_r),
        "sharpe_oos": _sh(oos_r),
        "trades": int(pos.diff().abs().fillna(0).gt(0).sum()),
        "exposure": float(pos.abs().mean()),
    }


def consider(hits: list[Hit], family: str, name: str, params: dict, m: dict) -> None:
    if m["sharpe"] >= 1.0 and m["max_dd"] > -0.25 and m["trades"] >= MIN_TRADES:
        hits.append(Hit(family, name, params, m["sharpe"], m["max_dd"], m["sharpe_is"], m["sharpe_oos"], m["trades"], m["exposure"]))


def run_search(close: pd.Series, high: pd.Series, low: pd.Series, vol: pd.Series, puell: pd.Series) -> list[Hit]:
    hits: list[Hit] = []

    # --- KEY MISSING: SMA + Puell + trail (fine grid) ---
    for ma in range(100, 201):
        ma_s = close.rolling(ma).mean().shift(LAG)
        for pthr in np.arange(0.85, 1.15, 0.01):
            entry_base = (close.shift(LAG) > ma_s) & (puell < pthr)
            for trail in np.arange(0.05, 0.21, 0.005):
                pos = trail_pos(close, entry_base.fillna(False), float(trail))
                m = eval_pos(close, pos)
                if m["sharpe"] >= 0.95 and m["max_dd"] > -0.25:
                    consider(hits, "sma_puell_trail", f"SMA{ma}+P<{pthr:.2f}+T{trail:.1%}", {"ma": ma, "puell": float(pthr), "trail": float(trail)}, m)

    # --- Puell entry/exit with MA gate (fine) ---
    for ent in np.arange(0.50, 0.85, 0.02):
        for ex in np.arange(1.20, 2.00, 0.05):
            for tma in range(100, 201, 5):
                e = (close.shift(LAG) > close.rolling(tma).mean().shift(LAG)) & (puell < ent)
                x = puell > ex
                consider(hits, "puell_ma", f"P{ent:.2f}/{ex:.2f}/MA{tma}", {"ent": float(ent), "ex": float(ex), "tma": tma}, eval_pos(close, pos_from_signals(close, e.fillna(False), x.fillna(False))))

    # --- CMMA + Puell + trail ---
    log_p = np.log(close)
    a = atr(high, low, close)
    for k in [20, 30, 40, 50, 60, 80]:
        cmma = ((log_p - log_p.rolling(k).mean()) / a).shift(LAG)
        for pthr in np.arange(0.90, 1.20, 0.05):
            for trail in np.arange(0.06, 0.20, 0.02):
                entry = (cmma > 0) & (puell < pthr)
                pos = trail_pos(close, entry.fillna(False), float(trail))
                consider(hits, "cmma_puell_trail", f"CMMA{k}+P{pthr}+T{trail:.0%}", {"k": k, "puell": float(pthr), "trail": float(trail)}, eval_pos(close, pos))

    # --- Dual MA + Puell + trail ---
    for fast in [20, 30, 40, 50]:
        for slow in [100, 120, 150, 180, 200]:
            if fast >= slow:
                continue
            maf = close.rolling(fast).mean().shift(LAG)
            mas = close.rolling(slow).mean().shift(LAG)
            for pthr in [0.95, 1.0, 1.05, 1.10]:
                entry = (maf > mas) & (puell < pthr)
                for trail in [0.08, 0.10, 0.12, 0.15]:
                    pos = trail_pos(close, entry.fillna(False), trail)
                    consider(hits, "dual_ma_puell", f"MA{fast}/{slow}+P{pthr}", {"fast": fast, "slow": slow, "puell": pthr, "trail": trail}, eval_pos(close, pos))

    # --- TSMOM + Puell + trail ---
    for lb in [63, 84, 126, 168, 189, 252]:
        mom = close.pct_change(lb).shift(LAG) > 0
        for pthr in [0.95, 1.0, 1.05]:
            for trail in [0.08, 0.10, 0.12, 0.15]:
                entry = mom & (puell < pthr)
                pos = trail_pos(close, entry.fillna(False), trail)
                consider(hits, "tsmom_puell", f"TSMOM{lb}+P{pthr}", {"lb": lb, "puell": pthr, "trail": trail}, eval_pos(close, pos))

    # --- IBS pullback + Puell gate ---
    for tma in range(100, 201, 25):
        ma = close.rolling(tma).mean().shift(LAG)
        ibs = ((close - low) / (high - low).replace(0, np.nan)).shift(LAG)
        rsi = vbt.RSI.run(close, 14).rsi.shift(LAG)
        for ibs_thr in [0.15, 0.20, 0.25, 0.30]:
            for rsi_thr in [30, 35, 40]:
                for pthr in [1.0, 1.1, 1.2, 1.5, 99.0]:
                    gate = (puell < pthr) if pthr < 10 else pd.Series(True, index=close.index)
                    e = gate & (close.shift(LAG) > ma) & (ibs < ibs_thr) & (rsi < rsi_thr)
                    x = (ibs > 0.5) | (close.shift(LAG) < ma)
                    consider(hits, "ibs_puell", f"IBS MA{tma} P{pthr}", {"tma": tma, "ibs": ibs_thr, "rsi": rsi_thr, "puell": pthr}, eval_pos(close, pos_from_signals(close, e.fillna(False), x.fillna(False))))

    # --- RSI+ER with Puell gate ---
    rsi = vbt.RSI.run(close, 14).rsi.shift(LAG)
    er = efficiency_ratio(close, 20).shift(LAG)
    for er_thr in [0.4, 0.5, 0.6]:
        for lo in [25, 30, 35]:
            for pthr in [1.0, 1.2, 1.5]:
                e = (er > er_thr) & (rsi < lo) & (puell < pthr)
                x = rsi > 50
                consider(hits, "rsi_er_puell", f"RSI<{lo} ER>{er_thr}", {"er": er_thr, "lo": lo, "puell": pthr}, eval_pos(close, pos_from_signals(close, e.fillna(False), x.fillna(False))))

    # --- Funding squeeze + Puell ---
    fund = align_to_close(load_coinglass_daily("futures_funding_rate_binance_1d.parquet"), close.index)
    mom5 = close.pct_change(5).shift(LAG) > 0
    for q in [0.05, 0.10, 0.15]:
        for pthr in [1.0, 1.2, 1.5]:
            e = (fund < fund.rolling(90).quantile(q)) & mom5 & (puell < pthr)
            x = fund > fund.rolling(90).quantile(0.5)
            consider(hits, "fund_puell", f"Fund q={q} P{pthr}", {"q": q, "puell": pthr}, eval_pos(close, pos_from_signals(close, e.fillna(False), x.fillna(False))))

    # --- Weekly SMA + Puell ---
    w = close.resample("W").last().dropna()
    for win in [8, 10, 12, 16, 20, 26, 30]:
        wma = w.rolling(win).mean().shift(LAG)
        wpos = (w.shift(LAG) > wma).astype(float)
        daily_trend = wpos.reindex(close.index, method="ffill").fillna(0)
        for pthr in [0.95, 1.0, 1.05, 1.10]:
            entry = (daily_trend > 0) & (puell < pthr)
            for trail in [0.08, 0.10, 0.12]:
                pos = trail_pos(close, entry.fillna(False), trail)
                consider(hits, "weekly_puell", f"WkSMA{win}+P{pthr}", {"win": win, "puell": pthr, "trail": trail}, eval_pos(close, pos))

    # --- Donchian breakout + Puell ---
    for ch in [20, 40, 55, 80]:
        upper = high.rolling(ch).max().shift(LAG)
        lower = low.rolling(ch).min().shift(LAG)
        for pthr in [1.0, 1.1, 1.2]:
            e = (close.shift(LAG) > upper.shift(1)) & (puell < pthr)
            x = close.shift(LAG) < lower.shift(1)
            consider(hits, "donchian_puell", f"Don{ch}+P{pthr}", {"ch": ch, "puell": pthr}, eval_pos(close, pos_from_signals(close, e.fillna(False), x.fillna(False))))

    return hits


def select_diverse(hits: list[Hit], k: int = 5) -> list[Hit]:
    hits = sorted(hits, key=lambda h: (-h.sharpe, h.max_dd), reverse=True)
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


def ensemble_metrics(close: pd.Series, positions: list[pd.Series]) -> dict:
    ens = pd.DataFrame(positions).mean(axis=1).clip(-1, 1)
    return eval_pos(close, ens)


def main() -> None:
    df, source = load_market_data("BTCUSDT", data_dir=DATA, interval="1d")
    df = df.sort_index()
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    vol = df["volume"].astype(float)
    puell = align_to_close(load_coinglass_daily("puell_multiple.csv", "puell_multiple"), close.index)

    print(f"Data: {source}, {len(close)} bars")
    hits = run_search(close, high, low, vol, puell)
    hits.sort(key=lambda h: -h.sharpe)

    print(f"\nQualifying hits (Sharpe>=1, DD<25%, trades>={MIN_TRADES}): {len(hits)}")
    for h in hits[:40]:
        print(f"  {h.family:18} {h.name[:45]:45} sh={h.sharpe:.3f} dd={h.max_dd:.1%} is={h.sharpe_is:.2f} oos={h.sharpe_oos:.2f} tr={h.trades}")

  # Near-misses
    near = []
    for ma in range(140, 160):
        for pthr in np.arange(0.96, 1.02, 0.005):
            for trail in np.arange(0.075, 0.085, 0.001):
                entry = (close.shift(LAG) > close.rolling(ma).mean().shift(LAG)) & (puell < pthr)
                pos = trail_pos(close, entry.fillna(False), float(trail))
                m = eval_pos(close, pos)
                if m["sharpe"] >= 0.99 and m["max_dd"] > -0.25:
                    near.append({"ma": ma, "puell": float(pthr), "trail": float(trail), **m})
    near.sort(key=lambda x: -x["sharpe"])
    print(f"\nNear-miss SMA+Puell+trail (sh>=0.99): {len(near)}")
    for n in near[:10]:
        print(f"  MA{n['ma']} P<{n['puell']:.3f} T{n['trail']:.1%} sh={n['sharpe']:.4f} dd={n['max_dd']:.1%}")

    diverse = select_diverse(hits, 5)
    out = {
        "data_source": source,
        "min_trades": MIN_TRADES,
        "total_hits": len(hits),
        "top_40": [asdict(h) for h in hits[:40]],
        "diverse_5": [asdict(h) for h in diverse],
        "near_miss_sma_puell_trail": near[:20],
    }
    (RUN / "artifacts").mkdir(parents=True, exist_ok=True)
    (RUN / "artifacts" / "final_search_hits.json").write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nDiverse 5: {len(diverse)}")
    for h in diverse:
        print(f"  {h.family}: {h.name} sh={h.sharpe:.3f} dd={h.max_dd:.1%}")


if __name__ == "__main__":
    main()
