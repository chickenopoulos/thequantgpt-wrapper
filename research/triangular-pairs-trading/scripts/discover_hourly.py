#!/usr/bin/env python3
"""Discover triangles on hourly Binance perp data (native hourly cointegration)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import OOS_START, RESULTS_DIR, profile
from src.data import load_close_panel
from src.discovery import discover_triangles, select_triangles, triangles_to_frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2023-01-01", help="hourly data load start")
    parser.add_argument("--discovery-start", default=None, help="IS scoring window start (default: --start)")
    parser.add_argument("--lookback-days", type=int, default=180, help="IS window length before OOS")
    parser.add_argument("--window", type=int, default=None, help="rolling OLS window (bars)")
    parser.add_argument("--liquid-top-n", type=int, default=30)
    parser.add_argument("--n-top", type=int, default=20, help="rows to save in summary json")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    prof = profile("1h")
    oos = pd.Timestamp(OOS_START, tz="UTC")
    load_start = pd.Timestamp(args.start, tz="UTC")
    discovery_end = oos
    if args.discovery_start:
        discovery_start = pd.Timestamp(args.discovery_start, tz="UTC")
    else:
        discovery_start = discovery_end - pd.Timedelta(days=args.lookback_days)

    window = args.window or prof["window"]
    min_periods = max(window // 2, prof["min_periods"] // 2)

    close = load_close_panel(interval="1h", start=load_start)
    print(
        f"Hourly discovery: {close.shape[1]} assets, "
        f"IS {discovery_start.date()} → {discovery_end.date()}, window={window}"
    )

    ranked = discover_triangles(
        close,
        oos_start=oos,
        discovery_start=discovery_start,
        discovery_end=discovery_end,
        liquid_top_n=args.liquid_top_n,
        window=window,
        min_periods=min_periods,
        half_life_cap=60 * 24,
        half_life_norm=120 * 24,
    )

    tag = f"lb{args.lookback_days}_w{window}"
    out_csv = RESULTS_DIR / f"triangle_discovery_hourly_{tag}.csv"
    ranked.to_csv(out_csv, index=False)

    top = ranked.head(args.n_top)
    payload = {
        "tag": tag,
        "discovery_start": discovery_start.isoformat(),
        "discovery_end": discovery_end.isoformat(),
        "window": window,
        "lookback_days": args.lookback_days,
        "top_triangles": top.to_dict(orient="records"),
        "selected_10": triangles_to_frame(select_triangles(ranked, 10)).to_dict(orient="records"),
    }
    out_json = RESULTS_DIR / f"hourly_discovery_{tag}.json"
    out_json.write_text(json.dumps(payload, indent=2))

    print(top.head(10).to_string(index=False))
    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    main()
