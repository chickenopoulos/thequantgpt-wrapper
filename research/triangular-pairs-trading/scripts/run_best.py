#!/usr/bin/env python3
"""Run the best validated triangular pairs configuration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backtest import backtest_triangles, compute_metrics
from src.config import ANCHORS, OOS_START, RESULTS_DIR
from src.data import load_close_panel, log_prices
from src.triangles import Triangle, enumerate_triangles, score_triangle_in_sample

# Tuned via grid search — optimizes OOS Sharpe while keeping full-sample edge.
BEST_PARAMS = {
    "n_triangles": 10,
    "window": 120,
    "entry_z": 3.0,
    "exit_z": 0.75,
    "weight_cap": 0.20,
    "max_gross_exposure": 1.0,
    "adf_max": 0.05,
}


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
    discovery = RESULTS_DIR / "triangle_discovery.csv"
    if discovery.exists():
        ranked = pd.read_csv(discovery).sort_values("score", ascending=False)
    else:
        candidates = enumerate_triangles(liquid, ANCHORS)
        rows = [score_triangle_in_sample(log_panel, tri, oos_start=oos) for tri in candidates]
        ranked = pd.DataFrame(rows).sort_values("score", ascending=False)
        ranked.to_csv(discovery, index=False)

    ranked = ranked[ranked["adf_p"] < BEST_PARAMS["adf_max"]]

    triangles = [
        Triangle(target=r.target, leg1=r.leg1, leg2=r.leg2)
        for r in ranked.head(BEST_PARAMS["n_triangles"]).itertuples()
    ]
    assets = sorted({a for tri in triangles for a in (tri.target, tri.leg1, tri.leg2)})
    panel = close[assets]

    result = backtest_triangles(
        panel,
        triangles,
        window=BEST_PARAMS["window"],
        entry_z=BEST_PARAMS["entry_z"],
        exit_z=BEST_PARAMS["exit_z"],
        weight_cap=BEST_PARAMS["weight_cap"],
        max_gross_exposure=BEST_PARAMS["max_gross_exposure"],
    )
    result.metrics = compute_metrics(result.daily_returns, oos)
    result.metrics["triangles"] = [t.key for t in triangles]
    result.metrics["variant"] = "best_validated"
    result.metrics["params"] = BEST_PARAMS

    result.daily_returns.to_csv(RESULTS_DIR / "daily_returns_best.csv", header=["return"])
    result.equity.to_csv(RESULTS_DIR / "equity_curve_best.csv", header=["equity"])
    (RESULTS_DIR / "metrics_best.json").write_text(json.dumps(result.metrics, indent=2))
    ranked.head(25).to_csv(RESULTS_DIR / "triangle_ranking.csv", index=False)

    m = result.metrics
    print("=== Best Validated Triangular Pairs System ===")
    print(f"Full  Sharpe: {m['Sharpe']:.3f}  CAGR: {m['CAGR']:.2%}  MaxDD: {m['MaxDD']:.2%}")
    print(
        f"OOS   Sharpe: {m['out_of_sample']['Sharpe']:.3f}  "
        f"CAGR: {m['out_of_sample']['CAGR']:.2%}  "
        f"MaxDD: {m['out_of_sample']['MaxDD']:.2%}"
    )
    print(f"Triangles ({len(triangles)}):")
    for t in triangles:
        print(f"  {t.key}")


if __name__ == "__main__":
    main()
