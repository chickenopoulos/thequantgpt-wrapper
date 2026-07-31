#!/usr/bin/env python3
"""Test ensemble variants: majority vote, weighted, MR-14+Puell, optimized mix."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
import vectorbt as vbt

from tqg_client.market_data import load_market_data
from tqg_client.strategy_sweep_core import (
    FEE, LAG, OOS, SLIPPAGE, align_to_close, atr, efficiency_ratio, load_coinglass_daily,
)

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "data"
ANN = 365


def trail_pos(close, entry, trail_pct):
    pos = pd.Series(0.0, index=close.index)
    state, peak = 0.0, 0.0
    for t in close.index:
        sig = bool(entry.loc[t])
        p = float(close.loc[t])
        if state == 0.0 and sig:
            state, peak = 1.0, p
        elif state > 0:
            peak = max(peak, p)
            if (p / peak - 1) < -trail_pct or not sig:
                state = 0.0
        pos.loc[t] = state
    return pos


def pos_sig(close, e, x):
    pos = pd.Series(0.0, index=close.index)
    state = 0.0
    for t in close.index:
        if state == 0.0 and e.loc[t]:
            state = 1.0
        elif state > 0 and x.loc[t]:
            state = 0.0
        pos.loc[t] = state
    return pos


def rets(close, pos):
    return pos.shift(1).fillna(0) * close.pct_change().fillna(0) - pos.diff().abs().fillna(0) * (FEE + SLIPPAGE)


def met(r, pos):
    rr = r.dropna()
    if len(rr) < 30 or rr.std() == 0:
        return {"sharpe": 0, "max_dd": 0, "trades": 0}
    sh = float(np.sqrt(ANN) * rr.mean() / rr.std())
    dd = float(((1 + rr).cumprod() / (1 + rr).cumprod().cummax() - 1).min())
    return {"sharpe": sh, "max_dd": dd, "trades": int(pos.diff().abs().gt(0).sum())}


def main():
    df, _ = load_market_data("BTCUSDT", data_dir=DATA, interval="1d")
    df = df.sort_index()
    close = df["close"].astype(float)
    high, low, vol = df["high"].astype(float), df["low"].astype(float), df["volume"].astype(float)
    puell = align_to_close(load_coinglass_daily("puell_multiple.csv", "puell_multiple"), close.index)
    fund = align_to_close(load_coinglass_daily("futures_funding_rate_binance_1d.parquet"), close.index)
    log_p = np.log(close)
    ibs = ((close - low) / (high - low).replace(0, np.nan)).shift(LAG)
    rsi = vbt.RSI.run(close, 14).rsi.shift(LAG)
    er = efficiency_ratio(close, 20).shift(LAG)

    sleeves = {}

    # S1 best
    ma151 = close.rolling(151).mean().shift(LAG)
    e1 = (close.shift(LAG) > ma151) & (puell < 0.99)
    sleeves["S1_sma_puell"] = trail_pos(close, e1.fillna(False), 0.08)

    # S2 puell value
    e2 = (close.shift(LAG) > close.rolling(200).mean().shift(LAG)) & (puell < 0.70)
    x2 = puell > 1.50
    sleeves["S2_puell"] = pos_sig(close, e2.fillna(False), x2.fillna(False))

    # S3 IBS
    ma150 = close.rolling(150).mean().shift(LAG)
    e3 = (close.shift(LAG) > ma150) & (ibs < 0.20) & (rsi < 35)
    x3 = (ibs > 0.50) | (close.shift(LAG) < ma150)
    sleeves["S3_ibs"] = pos_sig(close, e3.fillna(False), x3.fillna(False))

    # S4 funding
    e4 = (fund < fund.rolling(90).quantile(0.10)) & (close.pct_change(5).shift(LAG) > 0)
    x4 = fund > fund.rolling(90).quantile(0.5)
    sleeves["S4_fund"] = pos_sig(close, e4.fillna(False), x4.fillna(False))

    # S5 RSI+ER
    e5 = (er > 0.50) & (rsi < 30)
    x5 = rsi > 50
    sleeves["S5_rsi_er"] = pos_sig(close, e5.fillna(False), x5.fillna(False))

    # T02 CMMA
    cmma = ((log_p - log_p.rolling(40).mean()) / atr(high, low, close)).shift(LAG)
    e6 = cmma > 0
    x6 = cmma < 0
    sleeves["T02_cmma"] = pos_sig(close, e6.fillna(False), x6.fillna(False))

    # MR14 low vol fade + puell
    vq = vol.rolling(20).quantile(0.15).shift(LAG)
    for drop in [0.015, 0.02, 0.025]:
        for pthr in [1.2, 1.5, 99]:
            gate = (puell < pthr) if pthr < 10 else pd.Series(True, index=close.index)
            e = gate & (vol.shift(LAG) < vq) & (close.pct_change().shift(LAG) < -drop)
            x = close.pct_change().shift(LAG) > 0
            pos = pos_sig(close, e.fillna(False), x.fillna(False))
            m = met(rets(close, pos), pos)
            if m["sharpe"] >= 0.8:
                sleeves[f"MR14_d{drop}_p{pthr}"] = pos

    # CG08 orderbook
    ob = pd.read_parquet(DATA / "coinglass" / "futures_orderbook_pair_binance_1d.parquet")
    ob = ob[ob["symbol"].astype(str).str.upper() == "BTCUSDT"]
    ob.index = pd.to_datetime(ob["date"], utc=True)
    imb = align_to_close((ob["bids_usd"] - ob["asks_usd"]) / (ob["bids_usd"] + ob["asks_usd"]), close.index)
    for ent in [0.06, 0.08, 0.10]:
        e = (close.shift(LAG) > close.rolling(150).mean().shift(LAG)) & (imb > ent)
        x = imb < 0
        pos = pos_sig(close, e.fillna(False), x.fillna(False))
        m = met(rets(close, pos), pos)
        if m["max_dd"] > -0.25:
            sleeves[f"OB_{ent}"] = pos

    print(f"Built {len(sleeves)} sleeve variants\n")

    # Individual metrics
    ind = {}
    for name, pos in sleeves.items():
        m = met(rets(close, pos), pos)
        ind[name] = m
        if m["sharpe"] >= 0.9 and m["max_dd"] > -0.30:
            print(f"  {name:20} sh={m['sharpe']:.3f} dd={m['max_dd']:.1%} tr={m['trades']}")

    # Ensemble variants on core 5 + CMMA
    core = ["S1_sma_puell", "S2_puell", "S3_ibs", "S4_fund", "S5_rsi_er"]
    all_pos = pd.DataFrame({k: sleeves[k] for k in core + ["T02_cmma"] if k in sleeves})

    variants = []
    # Equal weight
    for subset_name, cols in [
        ("eq5", core),
        ("eq5+cmma", core + ["T02_cmma"]),
        ("lowdd4", ["S1_sma_puell", "S2_puell", "S3_ibs", "S5_rsi_er"]),
    ]:
        ens = all_pos[cols].mean(axis=1).clip(-1, 1)
        m = met(rets(close, ens), ens)
        variants.append({"name": subset_name, **m})

    # Majority vote (>=3 of 5)
    vote = (all_pos[core] > 0.5).sum(axis=1)
    ens_vote = (vote >= 3).astype(float)
    m = met(rets(close, ens_vote), ens_vote)
    variants.append({"name": "vote3of5", **m})

  # Vote 2 of 5 with CMMA boost
    vote2 = ((all_pos[core] > 0.5).sum(axis=1) >= 2).astype(float)
    m = met(rets(close, vote2), vote2)
    variants.append({"name": "vote2of5", **m})

    # Weight grid on core 5 (coarse)
    best_w = None
    for w1 in [0.1, 0.2, 0.3, 0.4]:
        for w2 in [0.1, 0.2, 0.3]:
            for w3 in [0.1, 0.2, 0.3]:
                for w4 in [0.05, 0.1, 0.15]:
                    w5 = 1.0 - w1 - w2 - w3 - w4
                    if w5 < 0.05:
                        continue
                    w = np.array([w1, w2, w3, w4, w5])
                    ens = (all_pos[core] * w).sum(axis=1).clip(-1, 1)
                    m = met(rets(close, ens), ens)
                    if m["max_dd"] > -0.20 and m["sharpe"] > (best_w["sharpe"] if best_w else 0):
                        best_w = {"weights": w.tolist(), "cols": core, **m}

    print("\n=== Ensemble variants ===")
    for v in sorted(variants, key=lambda x: -x["sharpe"]):
        ok = "PASS" if v["sharpe"] > 2 and v["max_dd"] > -0.15 else ""
        print(f"  {v['name']:12} sh={v['sharpe']:.2f} dd={v['max_dd']:.1%} {ok}")
    if best_w:
        print(f"\nBest weighted (DD<-20%): sh={best_w['sharpe']:.2f} dd={best_w['max_dd']:.1%} w={best_w['weights']}")

    out = REPO / "runs" / "5" / "artifacts" / "ensemble_variants.json"
    out.write_text(json.dumps({"individual": ind, "variants": variants, "best_weighted": best_w}, indent=2) + "\n")


if __name__ == "__main__":
    main()
