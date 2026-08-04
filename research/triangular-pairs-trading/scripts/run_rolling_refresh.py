#!/usr/bin/env python3
"""Rolling triangle refresh backtest (daily or hourly)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backtest import compute_metrics
from src.config import ANCHORS, OOS_START, RESULTS_DIR, profile
from src.data import load_close_panel, resample_to_daily
from src.rolling_refresh import backtest_rolling_refresh, build_rolling_schedule, save_schedule


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", choices=["1d", "1h"], default="1d")
    parser.add_argument("--refresh-freq", default=None, help="e.g. 90D daily, 30D hourly")
    parser.add_argument("--lookback-days", type=int, default=None)
    parser.add_argument("--n-triangles", type=int, default=10)
    parser.add_argument("--entry-z", type=float, default=3.0)
    parser.add_argument("--exit-z", type=float, default=0.75)
    parser.add_argument("--weight-cap", type=float, default=0.20)
    parser.add_argument("--no-sticky", action="store_true")
    parser.add_argument("--start", default=None, help="hourly sample start")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    oos = pd.Timestamp(OOS_START, tz="UTC")
    prof = profile(args.interval)

    start = pd.Timestamp(args.start, tz="UTC") if args.start else None
    if args.interval == "1h":
        close = load_close_panel(interval="1h", start=start or pd.Timestamp("2022-01-01", tz="UTC"))
    else:
        close = load_close_panel(interval="1d", min_history=prof["min_history"])

    print(f"Building rolling schedule ({args.interval}, refresh={args.refresh_freq or prof['refresh_freq']})...")
    schedule = build_rolling_schedule(
        close,
        ANCHORS,
        interval=args.interval,
        refresh_freq=args.refresh_freq,
        lookback_days=args.lookback_days,
        n_triangles=args.n_triangles,
        sticky=not args.no_sticky,
    )
    print(f"Schedule: {len(schedule)} refresh points")

    tag = args.interval
    save_schedule(schedule, RESULTS_DIR / f"rolling_schedule_{tag}.json")

    result = backtest_rolling_refresh(
        close,
        schedule,
        interval=args.interval,
        entry_z=args.entry_z,
        exit_z=args.exit_z,
        weight_cap=args.weight_cap,
    )

    ann = prof["ann_factor"]
    result.metrics = compute_metrics(result.daily_returns, oos, ann_factor=ann)
    result.metrics["interval"] = args.interval
    result.metrics["n_refreshes"] = len(schedule)
    result.metrics["sticky"] = not args.no_sticky
    result.metrics["params"] = vars(args)

    if args.interval == "1h":
        daily_comp = resample_to_daily(result.daily_returns)
        result.metrics["daily_compounded"] = compute_metrics(daily_comp, oos, ann_factor=365)

    out = RESULTS_DIR / f"metrics_rolling_{tag}.json"
    result.daily_returns.to_csv(RESULTS_DIR / f"returns_rolling_{tag}.csv", header=["return"])
    out.write_text(json.dumps(result.metrics, indent=2))

    m = result.metrics
    print(f"=== Rolling Refresh ({args.interval}) ===")
    print(f"Sharpe: {m['Sharpe']:.3f}  CAGR: {m['CAGR']:.2%}  MaxDD: {m['MaxDD']:.2%}")
    print(f"OOS Sharpe: {m['out_of_sample']['Sharpe']:.3f}  OOS MaxDD: {m['out_of_sample']['MaxDD']:.2%}")
    if "daily_compounded" in m:
        dc = m["daily_compounded"]
        print(f"Daily-compound OOS Sharpe: {dc['out_of_sample']['Sharpe']:.3f}")


if __name__ == "__main__":
    main()
