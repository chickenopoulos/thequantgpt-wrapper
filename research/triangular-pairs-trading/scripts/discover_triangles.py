#!/usr/bin/env python3
"""Discover and rank triangular cointegration candidates (in-sample only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import ANCHORS, OOS_START, RESULTS_DIR
from src.data import load_close_panel, log_prices
from src.triangles import enumerate_triangles, score_triangle_in_sample


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    oos = pd.Timestamp(OOS_START, tz="UTC")

    close = load_close_panel(interval="1d", min_history=500)
    counts = close.notna().sum().sort_values(ascending=False)
    liquid = counts.head(80).index.tolist()
    for a in ANCHORS:
        if a in close.columns and a not in liquid:
            liquid.append(a)

    panel = close[liquid]
    log_panel = log_prices(panel)

    triangles = enumerate_triangles(liquid, ANCHORS)
    print(f"Evaluating {len(triangles)} candidate triangles (IS only)...")

    rows = []
    for i, tri in enumerate(triangles):
        if i % 100 == 0:
            print(f"  {i}/{len(triangles)}")
        rows.append(score_triangle_in_sample(log_panel, tri, oos_start=oos))

    ranked = pd.DataFrame(rows).sort_values("score", ascending=False)
    ranked.to_csv(RESULTS_DIR / "triangle_discovery.csv", index=False)

    top = ranked.head(20)
    top_list = [
        {
            "target": r.target,
            "leg1": r.leg1,
            "leg2": r.leg2,
            "adf_p": float(r.adf_p),
            "half_life": float(r.half_life) if r.half_life < 1e6 else None,
            "score": float(r.score),
        }
        for r in top.itertuples()
    ]
    (RESULTS_DIR / "top_triangles.json").write_text(json.dumps(top_list, indent=2))
    print(top.head(10).to_string(index=False))
    print(f"Wrote {RESULTS_DIR / 'triangle_discovery.csv'}")


if __name__ == "__main__":
    main()
