#!/usr/bin/env python3
"""Compare hourly vs rolling-refresh variants against the daily baseline."""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_best import BEST_PARAMS
from src.backtest import backtest_triangles, compute_metrics
from src.config import ANCHORS, OOS_START, RESULTS_DIR, profile
from src.data import load_close_panel, resample_to_daily
from src.rolling_refresh import backtest_rolling_refresh, build_rolling_schedule
from src.triangles import Triangle

OOS = pd.Timestamp(OOS_START, tz="UTC")


def baseline_daily(close: pd.DataFrame, triangles: list[Triangle]) -> dict:
    assets = sorted({a for t in triangles for a in (t.target, t.leg1, t.leg2)})
    r = backtest_triangles(close[assets], triangles, **{
        k: BEST_PARAMS[k] for k in ("window", "entry_z", "exit_z", "weight_cap", "max_gross_exposure")
    })
    return compute_metrics(r.daily_returns, OOS, ann_factor=365)


def load_triangles(n: int) -> list[Triangle]:
    ranked = pd.read_csv(RESULTS_DIR / "triangle_discovery.csv").sort_values("score", ascending=False)
    ranked = ranked[ranked["adf_p"] < 0.05].head(n)
    return [Triangle(r.target, r.leg1, r.leg2) for r in ranked.itertuples()]


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    triangles = load_triangles(BEST_PARAMS["n_triangles"])
    close_d = load_close_panel(interval="1d", min_history=500)

    findings: dict = {"baseline_daily_static": baseline_daily(close_d, triangles)}

    # --- Hourly sweep (subset: window x entry) ---
    prof_h = profile("1h")
    assets = sorted({a for t in triangles for a in (t.target, t.leg1, t.leg2)})
    close_h = load_close_panel(interval="1h", assets=assets, start=pd.Timestamp("2022-01-01", tz="UTC"))

    hourly_rows = []
    for window, entry_z in itertools.product([480, 720, 1440], [2.5, 3.0, 3.5]):
        r = backtest_triangles(
            close_h, triangles,
            window=window, min_periods=window // 2,
            entry_z=entry_z, exit_z=0.75, weight_cap=0.15,
        )
        hourly_m = compute_metrics(r.daily_returns, OOS, ann_factor=prof_h["ann_factor"])
        daily_m = compute_metrics(resample_to_daily(r.daily_returns), OOS, ann_factor=365)
        hourly_rows.append({
            "window": window, "entry_z": entry_z,
            "hourly_sharpe": hourly_m["Sharpe"], "hourly_oos": hourly_m["out_of_sample"]["Sharpe"],
            "daily_comp_sharpe": daily_m["Sharpe"], "daily_comp_oos": daily_m["out_of_sample"]["Sharpe"],
            "daily_comp_maxdd": daily_m["MaxDD"],
        })
    hourly_df = pd.DataFrame(hourly_rows).sort_values("daily_comp_oos", ascending=False)
    findings["hourly_sweep_top3"] = hourly_df.head(3).to_dict(orient="records")
    hourly_df.to_csv(RESULTS_DIR / "hourly_sweep.csv", index=False)

    best_h = hourly_df.iloc[0]
    findings["hourly_best"] = best_h.to_dict()

    # --- Rolling refresh sweep (daily) ---
    refresh_rows = []
    for freq, lookback, sticky in itertools.product(["90D", "180D"], [180, 365], [True, False]):
        sched = build_rolling_schedule(
            close_d, ANCHORS, interval="1d",
            refresh_freq=freq, lookback_days=lookback,
            n_triangles=10, sticky=sticky,
        )
        if len(sched) < 2:
            continue
        r = backtest_rolling_refresh(
            close_d, sched, interval="1d",
            entry_z=3.0, exit_z=0.75, weight_cap=0.20,
        )
        m = compute_metrics(r.daily_returns, OOS, ann_factor=365)
        refresh_rows.append({
            "freq": freq, "lookback": lookback, "sticky": sticky,
            "n_refreshes": len(sched),
            "sharpe": m["Sharpe"], "oos_sharpe": m["out_of_sample"]["Sharpe"],
            "max_dd": m["MaxDD"], "oos_max_dd": m["out_of_sample"]["MaxDD"],
        })
    refresh_df = pd.DataFrame(refresh_rows).sort_values("oos_sharpe", ascending=False)
    findings["rolling_sweep_top3"] = refresh_df.head(3).to_dict(orient="records")
    refresh_df.to_csv(RESULTS_DIR / "rolling_sweep.csv", index=False)
    if not refresh_df.empty:
        findings["rolling_best"] = refresh_df.iloc[0].to_dict()

    (RESULTS_DIR / "explore_summary.json").write_text(json.dumps(findings, indent=2))
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
