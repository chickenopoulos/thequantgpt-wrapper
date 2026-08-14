#!/usr/bin/env python3
"""Run enhanced triangular pairs backtest (v2)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backtest import compute_metrics
from src.backtest_v2 import backtest_enhanced, select_diverse_triangles
from src.config import ANCHORS, OOS_START, RESULTS_DIR
from src.data import load_close_panel, log_prices
from src.triangles import enumerate_triangles, score_triangle_in_sample


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-triangles", type=int, default=10)
    parser.add_argument("--window", type=int, default=120)
    parser.add_argument("--entry-z", type=float, default=2.5)
    parser.add_argument("--exit-z", type=float, default=0.5)
    parser.add_argument("--weight-cap", type=float, default=0.20)
    parser.add_argument("--no-corr-gate", action="store_true")
    parser.add_argument("--no-vol-scale", action="store_true")
    parser.add_argument("--no-funding", action="store_true")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    oos = pd.Timestamp(OOS_START, tz="UTC")

    close = load_close_panel(interval="1d", min_history=500)
    counts = close.notna().sum().sort_values(ascending=False)
    liquid = counts.head(80).index.tolist()
    for a in ANCHORS:
        if a in close.columns and a not in liquid:
            liquid.append(a)

    log_panel = log_prices(close[liquid])
    candidates = enumerate_triangles(liquid, ANCHORS)
    rows = [score_triangle_in_sample(log_panel, tri, oos_start=oos) for tri in candidates]
    ranked = pd.DataFrame(rows).sort_values("score", ascending=False)
    ranked = ranked[ranked["adf_p"] < 0.05]

    triangles = select_diverse_triangles(ranked, args.n_triangles, max_per_target=1)
    assets = sorted({a for tri in triangles for a in (tri.target, tri.leg1, tri.leg2)})
    panel = close[assets]

    result = backtest_enhanced(
        panel,
        triangles,
        window=args.window,
        entry_z=args.entry_z,
        exit_z=args.exit_z,
        weight_cap=args.weight_cap,
        use_corr_gate=not args.no_corr_gate,
        use_vol_scale=not args.no_vol_scale,
        use_funding=not args.no_funding,
    )
    result.metrics = compute_metrics(result.daily_returns, oos)
    result.metrics["triangles"] = [t.key for t in triangles]
    result.metrics["variant"] = "v2_enhanced"
    result.metrics["params"] = vars(args)

    result.daily_returns.to_csv(RESULTS_DIR / "daily_returns_v2.csv", header=["return"])
    result.equity.to_csv(RESULTS_DIR / "equity_curve_v2.csv", header=["equity"])
    (RESULTS_DIR / "metrics_v2.json").write_text(json.dumps(result.metrics, indent=2))

    m = result.metrics
    print("=== Triangular Pairs v2 (enhanced) ===")
    print(f"Sharpe: {m['Sharpe']:.3f}  CAGR: {m['CAGR']:.2%}  MaxDD: {m['MaxDD']:.2%}")
    print(f"IS  Sharpe: {m['in_sample']['Sharpe']:.3f}  OOS Sharpe: {m['out_of_sample']['Sharpe']:.3f}")
    print(f"Triangles ({len(triangles)}):")
    for t in triangles:
        print(f"  {t.key}")


if __name__ == "__main__":
    main()
