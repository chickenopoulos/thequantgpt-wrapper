#!/usr/bin/env python3
"""Walk-forward triangular pairs backtest with drawdown control."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backtest import compute_metrics
from src.backtest_v3 import backtest_walk_forward, walk_forward_triangles
from src.config import ANCHORS, OOS_START, RESULTS_DIR
from src.data import load_close_panel


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    oos = pd.Timestamp(OOS_START, tz="UTC")
    close = load_close_panel(interval="1d", min_history=500)

    schedule = walk_forward_triangles(
        close,
        ANCHORS,
        oos_start=oos,
        rebalance_freq="365D",
        n_triangles=10,
        window=120,
    )
    print(f"Walk-forward schedule: {len(schedule)} rebalance points")

    result = backtest_walk_forward(
        close,
        schedule,
        window=120,
        entry_z=2.5,
        exit_z=0.5,
        weight_cap=0.20,
        max_gross=0.85,
        use_dd_scale=True,
    )
    result.metrics = compute_metrics(result.daily_returns, oos)
    result.metrics["variant"] = "v3_walk_forward"
    result.metrics["n_rebalances"] = len(schedule)

    result.daily_returns.to_csv(RESULTS_DIR / "daily_returns_v3.csv", header=["return"])
    result.equity.to_csv(RESULTS_DIR / "equity_curve_v3.csv", header=["equity"])
    (RESULTS_DIR / "metrics_v3.json").write_text(json.dumps(result.metrics, indent=2))

    m = result.metrics
    print("=== Triangular Pairs v3 (walk-forward + DD control) ===")
    print(f"Sharpe: {m['Sharpe']:.3f}  CAGR: {m['CAGR']:.2%}  MaxDD: {m['MaxDD']:.2%}")
    print(f"IS  Sharpe: {m['in_sample']['Sharpe']:.3f}  OOS Sharpe: {m['out_of_sample']['Sharpe']:.3f}")


if __name__ == "__main__":
    main()
