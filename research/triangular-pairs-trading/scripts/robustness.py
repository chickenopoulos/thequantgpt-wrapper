#!/usr/bin/env python3
"""Robustness checks: signal lag shift and subperiod stability."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_best import BEST_PARAMS
from src.backtest import backtest_triangles, compute_metrics
from src.config import ANCHORS, OOS_START, RESULTS_DIR
from src.data import load_close_panel, log_prices
from src.triangles import Triangle, enumerate_triangles, score_triangle_in_sample


def bootstrap_sharpe(returns: pd.Series, n: int = 500, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    r = returns.dropna().to_numpy()
    if len(r) < 30:
        return {"p5": np.nan, "p50": np.nan, "p95": np.nan}
    sharpes = []
    for _ in range(n):
        sample = rng.choice(r, size=len(r), replace=True)
        vol = sample.std()
        sharpes.append((sample.mean() / vol * np.sqrt(365)) if vol > 0 else np.nan)
    arr = np.array(sharpes)
    return {"p5": float(np.nanpercentile(arr, 5)), "p50": float(np.nanpercentile(arr, 50)), "p95": float(np.nanpercentile(arr, 95))}


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    oos = pd.Timestamp(OOS_START, tz="UTC")
    close = load_close_panel(interval="1d", min_history=500)

    counts = close.notna().sum().sort_values(ascending=False)
    liquid = counts.head(80).index.tolist()
    for a in ANCHORS:
        if a in close.columns and a not in liquid:
            liquid.append(a)

    log_panel = log_prices(close[liquid])
    rows = [score_triangle_in_sample(log_panel, tri, oos_start=oos) for tri in enumerate_triangles(liquid, ANCHORS)]
    ranked = pd.DataFrame(rows).sort_values("score", ascending=False)
    ranked = ranked[ranked["adf_p"] < BEST_PARAMS["adf_max"]]
    triangles = [
        Triangle(target=r.target, leg1=r.leg1, leg2=r.leg2)
        for r in ranked.head(BEST_PARAMS["n_triangles"]).itertuples()
    ]
    assets = sorted({a for tri in triangles for a in (tri.target, tri.leg1, tri.leg2)})

    findings = {"baseline": {}, "lag_shift": {}, "yearly": {}, "bootstrap_oos": {}}

    base = backtest_triangles(
        close[assets],
        triangles,
        window=BEST_PARAMS["window"],
        entry_z=BEST_PARAMS["entry_z"],
        exit_z=BEST_PARAMS["exit_z"],
        weight_cap=BEST_PARAMS["weight_cap"],
        max_gross_exposure=BEST_PARAMS["max_gross_exposure"],
    )
    findings["baseline"] = compute_metrics(base.daily_returns, oos)

    # +1 bar lag stress: shift returns one day as conservative execution delay test.
    shifted = base.daily_returns.shift(1).fillna(0)
    findings["lag_shift"] = compute_metrics(shifted, oos)

    oos_ret = base.daily_returns[base.daily_returns.index >= oos]
    findings["bootstrap_oos"] = bootstrap_sharpe(oos_ret)

    yearly = []
    for year, grp in base.daily_returns.groupby(base.daily_returns.index.year):
        m = compute_metrics(grp, pd.Timestamp(f"{year}-01-01", tz="UTC"))
        yearly.append({"year": int(year), "sharpe": m["Sharpe"], "cagr": m["CAGR"], "max_dd": m["MaxDD"]})
    findings["yearly"] = yearly

    (RESULTS_DIR / "robustness.json").write_text(json.dumps(findings, indent=2))
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
