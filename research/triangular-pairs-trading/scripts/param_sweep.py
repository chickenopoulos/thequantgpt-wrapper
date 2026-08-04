#!/usr/bin/env python3
"""Parameter sweep for triangular pairs strategy."""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_backtest import run_backtest
from src.config import OOS_START, RESULTS_DIR


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    oos = pd.Timestamp(OOS_START, tz="UTC")

    grid = {
        "n_triangles": [8, 12, 15, 20],
        "window": [60, 90, 120, 180],
        "entry_z": [1.5, 2.0, 2.5],
        "exit_z": [0.25, 0.5, 0.75],
        "weight_cap": [0.15, 0.20, 0.25],
    }

    keys = list(grid.keys())
    combos = list(itertools.product(*grid.values()))
    print(f"Sweeping {len(combos)} configurations...")

    rows = []
    for i, values in enumerate(combos):
        params = dict(zip(keys, values))
        if params["exit_z"] >= params["entry_z"]:
            continue
        try:
            result = run_backtest(**params, use_cached_triangles=True)
            m = result.metrics
            rows.append(
                {
                    **params,
                    "sharpe": m["Sharpe"],
                    "cagr": m["CAGR"],
                    "max_dd": m["MaxDD"],
                    "oos_sharpe": m["out_of_sample"]["Sharpe"],
                    "is_sharpe": m["in_sample"]["Sharpe"],
                }
            )
        except Exception as exc:
            rows.append({**params, "error": str(exc)})
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(combos)}")

    df = pd.DataFrame(rows)
    df = df.sort_values("oos_sharpe", ascending=False, na_position="last")
    df.to_csv(RESULTS_DIR / "param_sweep.csv", index=False)

    best = df.dropna(subset=["oos_sharpe"]).head(10)
    print("\nTop 10 by OOS Sharpe:")
    print(best.to_string(index=False))
    (RESULTS_DIR / "best_params.json").write_text(
        json.dumps(best.iloc[0].to_dict() if not best.empty else {}, indent=2)
    )


if __name__ == "__main__":
    main()
