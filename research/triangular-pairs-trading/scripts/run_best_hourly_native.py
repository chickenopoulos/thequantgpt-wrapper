#!/usr/bin/env python3
"""Run best hourly-native triangular pairs configuration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backtest import backtest_triangles, compute_metrics
from src.config import OOS_START, RESULTS_DIR, profile
from src.data import load_close_panel, resample_to_daily
from src.discovery import discover_triangles, select_triangles, triangles_to_frame

# Best from sweep_hourly_native.py (2023+ hourly panel, daily-compounded metrics).
BEST = {
    "load_start": "2023-01-01",
    "disc_lookback_days": 365,
    "disc_window": 720,
    "bt_window": 1440,
    "entry_z": 2.5,
    "exit_z": 0.75,
    "weight_cap": 0.15,
    "n_triangles": 10,
    "adf_max": 0.05,
}


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    oos = pd.Timestamp(OOS_START, tz="UTC")
    prof = profile("1h")
    load_start = pd.Timestamp(BEST["load_start"], tz="UTC")
    disc_start = oos - pd.Timedelta(days=BEST["disc_lookback_days"])

    close = load_close_panel(interval="1h", start=load_start)
    ranked = discover_triangles(
        close,
        oos_start=oos,
        discovery_start=disc_start,
        discovery_end=oos,
        liquid_top_n=prof["liquid_top_n"],
        window=BEST["disc_window"],
        min_periods=max(BEST["disc_window"] // 2, 360),
        half_life_cap=60 * 24,
        half_life_norm=120 * 24,
        progress_every=50,
    )
    ranked.to_csv(RESULTS_DIR / "triangle_discovery_hourly_best.csv", index=False)
    triangles = select_triangles(ranked, BEST["n_triangles"], adf_max=BEST["adf_max"])
    assets = sorted({a for t in triangles for a in (t.target, t.leg1, t.leg2)})

    result = backtest_triangles(
        close[assets],
        triangles,
        window=BEST["bt_window"],
        min_periods=BEST["bt_window"] // 2,
        entry_z=BEST["entry_z"],
        exit_z=BEST["exit_z"],
        weight_cap=BEST["weight_cap"],
    )

    daily = resample_to_daily(result.daily_returns)
    hourly_eq = (1 + result.daily_returns).cumprod()
    daily_eq = (1 + daily).cumprod()
    m_hourly = compute_metrics(result.daily_returns, oos, ann_factor=prof["ann_factor"])
    m_daily = compute_metrics(daily, oos, ann_factor=365)

    hourly_eq.to_csv(RESULTS_DIR / "equity_curve_hourly_native_hourly.csv", header=["equity"])
    daily_eq.to_csv(RESULTS_DIR / "equity_curve_hourly_native_daily.csv", header=["equity"])
    result.daily_returns.to_csv(RESULTS_DIR / "returns_hourly_native_hourly.csv", header=["return"])
    daily.to_csv(RESULTS_DIR / "hourly_native_best_daily.csv", header=["return"])

    payload = {
        "params": BEST,
        "triangles": triangles_to_frame(triangles).to_dict(orient="records"),
        "hourly_metrics": m_hourly,
        "daily_compounded_metrics": m_daily,
    }
    (RESULTS_DIR / "metrics_hourly_native_best.json").write_text(json.dumps(payload, indent=2))

    print("=== Best Hourly-Native System ===")
    print(f"Triangles ({len(triangles)}):")
    for t in triangles:
        print(f"  {t.key}")
    md = m_daily
    print(
        f"Daily-compound  Sharpe: {md['Sharpe']:.3f}  "
        f"OOS: {md['out_of_sample']['Sharpe']:.3f}  "
        f"MaxDD: {md['MaxDD']:.2%}  "
        f"OOS MaxDD: {md['out_of_sample']['MaxDD']:.2%}"
    )


if __name__ == "__main__":
    main()
