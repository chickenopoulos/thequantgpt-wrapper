#!/usr/bin/env python3
"""Hourly triangular pairs backtest (uses daily-selected triangles by default)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backtest import backtest_triangles, compute_metrics
from src.config import ANCHORS, OOS_START, RESULTS_DIR, profile
from src.data import load_close_panel, resample_to_daily
from src.triangles import Triangle


def load_daily_triangles(n: int = 10) -> list[Triangle]:
    discovery = RESULTS_DIR / "triangle_discovery.csv"
    if not discovery.exists():
        raise FileNotFoundError("Run discover_triangles.py first to build triangle_discovery.csv")
    ranked = pd.read_csv(discovery).sort_values("score", ascending=False)
    ranked = ranked[ranked["adf_p"] < 0.05].head(n)
    return [Triangle(r.target, r.leg1, r.leg2) for r in ranked.itertuples()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entry-z", type=float, default=3.0)
    parser.add_argument("--exit-z", type=float, default=0.75)
    parser.add_argument("--weight-cap", type=float, default=0.15)
    parser.add_argument("--window", type=int, default=None, help="override hourly window (bars)")
    parser.add_argument("--start", default="2022-01-01", help="hourly sample start (memory)")
    parser.add_argument("--n-triangles", type=int, default=10)
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    oos = pd.Timestamp(OOS_START, tz="UTC")
    prof = profile("1h")
    window = args.window or prof["window"]

    triangles = load_daily_triangles(args.n_triangles)
    assets = sorted({a for t in triangles for a in (t.target, t.leg1, t.leg2)})

    start = pd.Timestamp(args.start, tz="UTC")
    close = load_close_panel(interval="1h", assets=assets, start=start)
    print(f"Hourly panel: {close.shape[0]} bars x {close.shape[1]} assets from {close.index[0]}")

    result = backtest_triangles(
        close,
        triangles,
        window=window,
        min_periods=prof["min_periods"],
        entry_z=args.entry_z,
        exit_z=args.exit_z,
        weight_cap=args.weight_cap,
    )

    ann = prof["ann_factor"]
    result.metrics = compute_metrics(result.daily_returns, oos, ann_factor=ann)
    result.metrics["interval"] = "1h"
    result.metrics["params"] = vars(args)
    result.metrics["triangles"] = [t.key for t in triangles]

    # Daily-compounded view for apples-to-apples vs daily baseline.
    daily_comp = resample_to_daily(result.daily_returns)
    daily_metrics = compute_metrics(daily_comp, oos, ann_factor=365)
    result.metrics["daily_compounded"] = daily_metrics

    result.daily_returns.to_csv(RESULTS_DIR / "hourly_returns.csv", header=["return"])
    daily_comp.to_csv(RESULTS_DIR / "hourly_compounded_daily.csv", header=["return"])
    (RESULTS_DIR / "metrics_hourly.json").write_text(json.dumps(result.metrics, indent=2))

    m = result.metrics
    dc = m["daily_compounded"]
    print("=== Hourly Triangular Pairs ===")
    print(f"Hourly Sharpe: {m['Sharpe']:.3f}  CAGR: {m['CAGR']:.2%}  MaxDD: {m['MaxDD']:.2%}")
    print(f"OOS hourly:    {m['out_of_sample']['Sharpe']:.3f}  MaxDD: {m['out_of_sample']['MaxDD']:.2%}")
    print(f"Daily-compound Sharpe: {dc['Sharpe']:.3f}  OOS: {dc['out_of_sample']['Sharpe']:.3f}")


if __name__ == "__main__":
    main()
