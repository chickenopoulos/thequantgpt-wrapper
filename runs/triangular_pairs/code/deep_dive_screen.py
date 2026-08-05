#!/usr/bin/env python3
"""Phase 1 (fast): cached discovery + daily/hourly variant screen."""

from __future__ import annotations

import itertools
import json
import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "runs" / "triangular_pairs" / "code"))

from engine import OOS, RUN, discover_triangles_is, save_json  # noqa: E402
from src.data import load_close_panel  # noqa: E402
from variants import evaluate_variant, run_backtest, run_hourly_daily_triangles, run_hourly_native  # noqa: E402

DAILY_GRID = {
    "n_triangles": [8, 10, 12],
    "window": [90, 105, 120],
    "entry_z": [2.0, 2.25, 2.5],
    "exit_z": [0.5, 0.75],
    "weight_cap": [0.15, 0.20],
}


def daily_combos() -> list[dict]:
    out = []
    for vals in itertools.product(*DAILY_GRID.values()):
        p = dict(zip(DAILY_GRID.keys(), vals))
        if p["exit_z"] >= p["entry_z"]:
            continue
        p["adf_max"] = 0.05
        out.append(p)
    return out


def main() -> None:
    t0 = time.time()
    out_dir = RUN / "artifacts"
    rows: list[dict] = []

    print("Loading data...", flush=True)
    close_d = load_close_panel(interval="1d", min_history=500)
    close_h = load_close_panel(interval="1h", start=pd.Timestamp("2022-01-01", tz="UTC"))

    print("Discovering triangles once (IS, window=120)...", flush=True)
    _, ranked = discover_triangles_is(close_d, window=120, n_triangles=15)
    ranked.to_csv(out_dir / "triangle_discovery_is.csv", index=False)
    print(f"  {len(ranked)} candidates", flush=True)

    combos = daily_combos()
    print(f"\n[A] Daily static ({len(combos)}) with cached discovery...", flush=True)
    for i, p in enumerate(combos):
        tris, _ = discover_triangles_is(close_d, n_triangles=p["n_triangles"], ranked_cache=ranked)
        try:
            rets = run_backtest(close_d, tris, window=p["window"], entry_z=p["entry_z"], exit_z=p["exit_z"], weight_cap=p["weight_cap"])
            rows.append(evaluate_variant("daily_static", rets, p))
        except Exception as exc:
            rows.append({"variant": "daily_static", "params": p, "error": str(exc), "composite_score": float("-inf")})
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(combos)}", flush=True)

    df = pd.DataFrame(rows).sort_values("composite_score", ascending=False)
    top5 = df.head(5)
    print(f"\nTop daily: {top5.iloc[0]['composite_score']:.3f} Sharpe={top5.iloc[0]['Sharpe']:.3f} params={top5.iloc[0]['params']}", flush=True)

    print("\n[B] Hourly exec (top 5 daily params)...", flush=True)
    for _, r in top5.iterrows():
        p = r["params"]
        hp = {**p, "bt_window": 1440 if p["window"] >= 105 else 720}
        try:
            rets = run_hourly_daily_triangles(close_h, close_d, hp)
            rows.append(evaluate_variant("hourly_exec_daily_tris", rets, hp))
            print(f"  w={p['window']} ez={p['entry_z']} -> composite={rows[-1]['composite_score']:.3f}", flush=True)
        except Exception as exc:
            rows.append({"variant": "hourly_exec_daily_tris", "params": hp, "error": str(exc), "composite_score": float("-inf")})

    print("\n[C] Hourly native (top 3 × 2 configs)...", flush=True)
    for _, r in top5.head(3).iterrows():
        p = r["params"]
        for disc_w, lb in [(720, 365), (1440, 365)]:
            hp = {**p, "disc_window": disc_w, "bt_window": 1440, "liquid_top_n": 30}
            try:
                rets = run_hourly_native(close_h, hp, disc_lookback_days=lb)
                rows.append(evaluate_variant(f"hourly_native_lb{lb}_w{disc_w}", rets, hp))
                print(f"  lb{lb} w{disc_w} composite={rows[-1]['composite_score']:.3f}", flush=True)
            except Exception as exc:
                rows.append({"variant": "hourly_native", "params": hp, "error": str(exc), "composite_score": float("-inf")})

    df = pd.DataFrame(rows).sort_values("composite_score", ascending=False, na_position="last")
    df.to_csv(out_dir / "deep_dive_screen.csv", index=False)
    winner = df.iloc[0].to_dict()
    save_json(out_dir / "deep_dive_screen.json", {
        "elapsed_sec": time.time() - t0,
        "winner_variant": winner["variant"],
        "winner_composite": float(winner["composite_score"]),
        "winner_sharpe": float(winner["Sharpe"]),
        "winner_wf_min": float(winner["wf_min"]),
        "top10": df.head(10)[["variant", "Sharpe", "MaxDD", "wf_min", "composite_score"]].to_dict(orient="records"),
    })
    save_json(out_dir / "deep_dive_winner_candidate.json", {"variant": winner["variant"], "params": winner["params"]})

    print("\n=== TOP 10 ===", flush=True)
    print(df.head(10)[["variant", "Sharpe", "MaxDD", "wf_min", "composite_score"]].to_string(index=False), flush=True)
    print(f"Done in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
