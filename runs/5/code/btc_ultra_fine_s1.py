#!/usr/bin/env python3
"""Ultra-fine SMA+Puell+trail search + Binance data cross-check."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from tqg_client.market_data import load_market_data
from tqg_client.strategy_sweep_core import FEE, LAG, OOS, SLIPPAGE, align_to_close, load_coinglass_daily

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


def metrics(close, pos):
    r = pos.shift(1).fillna(0) * close.pct_change().fillna(0) - pos.diff().abs().fillna(0) * (FEE + SLIPPAGE)
    rr = r.dropna()
    if len(rr) < 30 or rr.std() == 0:
        return None
    sh = float(np.sqrt(ANN) * rr.mean() / rr.std())
    dd = float(((1 + rr).cumprod() / (1 + rr).cumprod().cummax() - 1).min())
    tr = int(pos.diff().abs().fillna(0).gt(0).sum())
    return {"sharpe": sh, "max_dd": dd, "trades": tr}


def search_label(source: str, close: pd.Series, puell: pd.Series) -> list[dict]:
    hits, near = [], []
    for ma in range(140, 160):
        ma_s = close.rolling(ma).mean().shift(LAG)
        for pthr in np.arange(0.96, 1.02, 0.001):
            entry = (close.shift(LAG) > ma_s) & (puell < pthr)
            for trail in np.arange(0.070, 0.090, 0.0005):
                pos = trail_pos(close, entry.fillna(False), float(trail))
                m = metrics(close, pos)
                if m is None:
                    continue
                row = {"source": source, "ma": ma, "puell": float(pthr), "trail": float(trail), **m}
                if m["sharpe"] >= 1.0 and m["max_dd"] > -0.25 and m["trades"] >= 5:
                    hits.append(row)
                elif m["sharpe"] >= 0.995 and m["max_dd"] > -0.25:
                    near.append(row)
    hits.sort(key=lambda x: -x["sharpe"])
    near.sort(key=lambda x: -x["sharpe"])
    return hits, near


def main():
    results = {}
    for sym_path in [("talos", "BTCUSDT"), ("binance", "BTCUSDT")]:
        try:
            df, src = load_market_data("BTCUSDT", data_dir=DATA, interval="1d")
            if sym_path[0] == "binance":
                alt = DATA / "binance" / "BTCUSDT_1d.parquet"
                if alt.exists():
                    df = pd.read_parquet(alt)
                    if "timestamp" in df.columns:
                        df = df.set_index("timestamp")
                    df.index = pd.to_datetime(df.index, utc=True)
                    src = str(alt)
            df = df.sort_index()
            close = df["close"].astype(float)
            puell = align_to_close(load_coinglass_daily("puell_multiple.csv", "puell_multiple"), close.index)
            hits, near = search_label(sym_path[0], close, puell)
            results[sym_path[0]] = {"source": src, "hits": hits[:20], "near": near[:10], "n_hits": len(hits)}
            print(f"\n=== {sym_path[0]} ({src}) ===")
            print(f"Hits (sh>=1, dd<25%): {len(hits)}")
            for h in hits[:5]:
                print(f"  MA{h['ma']} P<{h['puell']:.3f} T{h['trail']:.2%} sh={h['sharpe']:.4f} dd={h['max_dd']:.1%}")
            print(f"Top near-miss:")
            for h in near[:3]:
                print(f"  MA{h['ma']} P<{h['puell']:.3f} T{h['trail']:.2%} sh={h['sharpe']:.4f} dd={h['max_dd']:.1%}")
        except Exception as e:
            results[sym_path[0]] = {"error": str(e)}
            print(f"{sym_path[0]} error: {e}")

    out = REPO / "runs" / "5" / "artifacts" / "ultra_fine_sma_puell.json"
    out.write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
