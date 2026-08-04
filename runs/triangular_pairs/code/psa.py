#!/usr/bin/env python3
"""In-sample PSA: entry_z x window (exit_z and weight_cap fixed at IS-best)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "runs" / "triangular_pairs" / "code"))

from engine import (  # noqa: E402
    OOS,
    RUN,
    discover_triangles_is,
    is_metrics,
    load_close_panel,
    run_backtest,
    save_json,
)

ENTRY_Z = [2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5]
WINDOWS = [90, 105, 120, 135, 150]


def load_fixed_params() -> dict:
    path = RUN / "artifacts" / "is_best_params.json"
    if path.exists():
        best = json.loads(path.read_text()).get("best", {})
        return {
            "n_triangles": int(best.get("n_triangles", 10)),
            "exit_z": float(best.get("exit_z", 0.75)),
            "weight_cap": float(best.get("weight_cap", 0.20)),
            "adf_max": 0.05,
        }
    return {"n_triangles": 10, "exit_z": 0.75, "weight_cap": 0.20, "adf_max": 0.05}


def main() -> None:
    fixed = load_fixed_params()
    close = load_close_panel(interval="1d", min_history=500)
    triangles, _ = discover_triangles_is(
        close,
        oos_start=OOS,
        adf_max=fixed["adf_max"],
        n_triangles=fixed["n_triangles"],
        window=120,
    )
    tris = triangles[: fixed["n_triangles"]]

    rows: list[dict] = []
    for w in WINDOWS:
        for ez in ENTRY_Z:
            if fixed["exit_z"] >= ez:
                continue
            rets = run_backtest(
                close,
                tris,
                window=w,
                entry_z=ez,
                exit_z=fixed["exit_z"],
                weight_cap=fixed["weight_cap"],
            )
            m = is_metrics(rets)
            rows.append({"window": w, "entry_z": ez, **m})

    df = pd.DataFrame(rows)
    pivot = df.pivot(index="window", columns="entry_z", values="Sharpe")
    save_json(
        RUN / "artifacts" / "psa_summary.json",
        {
            "test": "parameter_sensitivity",
            "segment": "in_sample",
            "fixed_params": fixed,
            "grid": {"entry_z": ENTRY_Z, "window": WINDOWS},
            "results": rows,
            "stable_region": {
                "sharpe_above_median": df[df["Sharpe"] >= df["Sharpe"].median()][["window", "entry_z", "Sharpe", "MaxDD"]].to_dict(orient="records"),
            },
        },
    )

    fig, ax = plt.subplots(figsize=(9, 6))
    im = ax.imshow(pivot.values, aspect="auto", cmap="RdYlGn", origin="lower")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([f"{c:.2f}" for c in pivot.columns])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_xlabel("entry_z")
    ax.set_ylabel("window")
    ax.set_title("IS PSA: Sharpe (entry_z × window)")
    plt.colorbar(im, ax=ax, label="IS Sharpe")
    for i, w in enumerate(pivot.index):
        for j, ez in enumerate(pivot.columns):
            val = pivot.loc[w, ez]
            if pd.notna(val):
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(RUN / "charts" / "psa_heatmap.png", dpi=120)
    plt.close(fig)

    print("=== IS PSA complete ===")
    print(pivot.round(2).to_string())
    print(f"Wrote {RUN / 'artifacts' / 'psa_summary.json'}")


if __name__ == "__main__":
    main()
