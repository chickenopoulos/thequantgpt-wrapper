#!/usr/bin/env python3
"""Run triangular pairs trading backtest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backtest import BacktestResult, backtest_triangles, compute_metrics
from src.config import ANCHORS, OOS_START, RESULTS_DIR
from src.data import load_close_panel, log_prices
from src.triangles import Triangle, enumerate_triangles, score_triangle_in_sample


def load_top_triangles(path: Path, n: int) -> list[Triangle]:
    data = json.loads(path.read_text())
    return [Triangle(target=d["target"], leg1=d["leg1"], leg2=d["leg2"]) for d in data[:n]]


def discover_and_select(
    close: pd.DataFrame,
    *,
    n_triangles: int,
    oos: pd.Timestamp,
) -> list[Triangle]:
    counts = close.notna().sum().sort_values(ascending=False)
    liquid = counts.head(80).index.tolist()
    for a in ANCHORS:
        if a in close.columns and a not in liquid:
            liquid.append(a)

    log_panel = log_prices(close[liquid])
    candidates = enumerate_triangles(liquid, ANCHORS)
    rows = [score_triangle_in_sample(log_panel, tri, oos_start=oos) for tri in candidates]
    ranked = pd.DataFrame(rows).sort_values("score", ascending=False)
    ranked = ranked[ranked["adf_p"] < 0.10]
    top = ranked.head(n_triangles)
    return [
        Triangle(target=r.target, leg1=r.leg1, leg2=r.leg2)
        for r in top.itertuples()
    ]


def run_backtest(
    *,
    n_triangles: int = 15,
    window: int = 120,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
    weight_cap: float = 0.20,
    use_cached_triangles: bool = True,
) -> BacktestResult:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    oos = pd.Timestamp(OOS_START, tz="UTC")
    close = load_close_panel(interval="1d", min_history=500)

    cache = RESULTS_DIR / "top_triangles.json"
    if use_cached_triangles and cache.exists():
        triangles = load_top_triangles(cache, n_triangles)
    else:
        triangles = discover_and_select(close, n_triangles=n_triangles, oos=oos)

    if not triangles:
        raise RuntimeError("No triangles selected; run discovery first.")

    assets = sorted({a for tri in triangles for a in (tri.target, tri.leg1, tri.leg2)})
    panel = close[assets]

    result = backtest_triangles(
        panel,
        triangles,
        window=window,
        entry_z=entry_z,
        exit_z=exit_z,
        weight_cap=weight_cap,
    )
    result.metrics = compute_metrics(result.daily_returns, oos)
    result.metrics["triangles"] = [tri.key for tri in triangles]
    result.metrics["params"] = {
        "window": window,
        "entry_z": entry_z,
        "exit_z": exit_z,
        "weight_cap": weight_cap,
        "n_triangles": len(triangles),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-triangles", type=int, default=15)
    parser.add_argument("--window", type=int, default=120)
    parser.add_argument("--entry-z", type=float, default=2.0)
    parser.add_argument("--exit-z", type=float, default=0.5)
    parser.add_argument("--weight-cap", type=float, default=0.20)
    parser.add_argument("--rediscover", action="store_true")
    args = parser.parse_args()

    result = run_backtest(
        n_triangles=args.n_triangles,
        window=args.window,
        entry_z=args.entry_z,
        exit_z=args.exit_z,
        weight_cap=args.weight_cap,
        use_cached_triangles=not args.rediscover,
    )

    result.daily_returns.to_csv(RESULTS_DIR / "daily_returns.csv", header=["return"])
    result.equity.to_csv(RESULTS_DIR / "equity_curve.csv", header=["equity"])
    (RESULTS_DIR / "metrics.json").write_text(json.dumps(result.metrics, indent=2))

    m = result.metrics
    print("=== Triangular Pairs Backtest ===")
    print(f"Sharpe: {m['Sharpe']:.3f}  CAGR: {m['CAGR']:.2%}  MaxDD: {m['MaxDD']:.2%}")
    print(f"IS  Sharpe: {m['in_sample']['Sharpe']:.3f}  OOS Sharpe: {m['out_of_sample']['Sharpe']:.3f}")
    print(f"Triangles: {len(m['triangles'])}")


if __name__ == "__main__":
    main()
