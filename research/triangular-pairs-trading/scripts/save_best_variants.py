#!/usr/bin/env python3
"""Save best hourly + rolling configs from exploration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backtest import backtest_triangles, compute_metrics
from src.config import ANCHORS, OOS_START, RESULTS_DIR
from src.data import load_close_panel, resample_to_daily
from src.rolling_refresh import backtest_rolling_refresh, build_rolling_schedule, save_schedule
from src.triangles import Triangle

HOURLY_BEST = {"window": 1440, "entry_z": 2.5, "exit_z": 0.75, "weight_cap": 0.15, "start": "2022-01-01"}
ROLLING_BEST = {
    "refresh_freq": "180D",
    "lookback_days": 180,
    "sticky": False,
    "n_triangles": 10,
    "entry_z": 3.0,
    "exit_z": 0.75,
    "weight_cap": 0.20,
}


def load_triangles(n: int = 10) -> list[Triangle]:
    ranked = pd.read_csv(RESULTS_DIR / "triangle_discovery.csv").sort_values("score", ascending=False)
    ranked = ranked[ranked["adf_p"] < 0.05].head(n)
    return [Triangle(r.target, r.leg1, r.leg2) for r in ranked.itertuples()]


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    oos = pd.Timestamp(OOS_START, tz="UTC")
    triangles = load_triangles()

    # Hourly
    assets = sorted({a for t in triangles for a in (t.target, t.leg1, t.leg2)})
    close_h = load_close_panel(
        interval="1h",
        assets=assets,
        start=pd.Timestamp(HOURLY_BEST["start"], tz="UTC"),
    )
    rh = backtest_triangles(
        close_h,
        triangles,
        window=HOURLY_BEST["window"],
        min_periods=HOURLY_BEST["window"] // 2,
        entry_z=HOURLY_BEST["entry_z"],
        exit_z=HOURLY_BEST["exit_z"],
        weight_cap=HOURLY_BEST["weight_cap"],
    )
    mh = compute_metrics(resample_to_daily(rh.daily_returns), oos, ann_factor=365)
    (RESULTS_DIR / "best_hourly.json").write_text(
        json.dumps({"params": HOURLY_BEST, "metrics_daily_compounded": mh}, indent=2)
    )

    # Rolling daily
    close_d = load_close_panel(interval="1d", min_history=500)
    sched = build_rolling_schedule(
        close_d,
        ANCHORS,
        interval="1d",
        refresh_freq=ROLLING_BEST["refresh_freq"],
        lookback_days=ROLLING_BEST["lookback_days"],
        n_triangles=ROLLING_BEST["n_triangles"],
        sticky=ROLLING_BEST["sticky"],
    )
    save_schedule(sched, RESULTS_DIR / "rolling_schedule_best.json")
    rr = backtest_rolling_refresh(
        close_d,
        sched,
        interval="1d",
        entry_z=ROLLING_BEST["entry_z"],
        exit_z=ROLLING_BEST["exit_z"],
        weight_cap=ROLLING_BEST["weight_cap"],
    )
    mr = compute_metrics(rr.daily_returns, oos, ann_factor=365)
    (RESULTS_DIR / "best_rolling.json").write_text(
        json.dumps({"params": ROLLING_BEST, "n_refreshes": len(sched), "metrics": mr}, indent=2)
    )

    print("Hourly (daily-compounded) OOS Sharpe:", mh["out_of_sample"]["Sharpe"])
    print("Rolling daily OOS Sharpe:", mr["out_of_sample"]["Sharpe"])


if __name__ == "__main__":
    main()
