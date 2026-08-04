#!/usr/bin/env python3
"""In-sample parameter sweep for triangular pairs (TQG-compliant selection).

Ranks by robust_score (IS Sharpe + yearly stability + drawdown penalty).
Does NOT use OOS segment for tuning.
"""

from __future__ import annotations

import itertools
import json
import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "runs" / "triangular_pairs" / "code"))

from engine import (  # noqa: E402
    OOS,
    RUN,
    discover_triangles_is,
    is_metrics,
    load_close_panel,
    robust_score,
    run_backtest,
    save_json,
    yearly_sharpes,
)

# Coarse grid first; refined around daily-static research defaults.
GRID = {
    "n_triangles": [8, 10, 12],
    "window": [90, 120, 150],
    "entry_z": [2.0, 2.5, 3.0],
    "exit_z": [0.5, 0.75],
    "weight_cap": [0.15, 0.20, 0.25],
}
ADF_MAX = 0.05


def main() -> None:
    log_path = RUN / "logs" / "is_param_sweep.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    close = load_close_panel(interval="1d", min_history=500)
    print(f"Loaded panel {close.shape}")

    # Triangle universe fixed from IS discovery at baseline window.
    triangles, ranked = discover_triangles_is(
        close,
        oos_start=OOS,
        adf_max=ADF_MAX,
        n_triangles=15,
        window=120,
    )
    ranked.to_csv(RUN / "artifacts" / "triangle_discovery_is.csv", index=False)
    print(f"IS discovery: {len(ranked)} candidates, top={triangles[0].key if triangles else 'none'}")

    keys = list(GRID.keys())
    combos = list(itertools.product(*GRID.values()))
    print(f"Sweeping {len(combos)} configs on IS only...")

    rows: list[dict] = []
    for i, values in enumerate(combos):
        params = dict(zip(keys, values))
        if params["exit_z"] >= params["entry_z"]:
            continue
        n = params["n_triangles"]
        tris = triangles[:n]
        if len(tris) < 3:
            continue
        try:
            rets = run_backtest(
                close,
                tris,
                window=params["window"],
                entry_z=params["entry_z"],
                exit_z=params["exit_z"],
                weight_cap=params["weight_cap"],
            )
            is_m = is_metrics(rets)
            yearly = yearly_sharpes(rets)
            score = robust_score(is_m, yearly)
            rows.append(
                {
                    **params,
                    "is_sharpe": is_m["Sharpe"],
                    "is_cagr": is_m["CAGR"],
                    "is_max_dd": is_m["MaxDD"],
                    "is_n_days": is_m["n_days"],
                    "robust_score": score,
                    "min_yearly_sharpe": min(v for v in yearly.values() if pd.notna(v)) if yearly else float("nan"),
                    "yearly_sharpes": yearly,
                }
            )
        except Exception as exc:
            rows.append({**params, "error": str(exc)})
        if (i + 1) % 30 == 0:
            print(f"  {i + 1}/{len(combos)} ({time.time() - t0:.0f}s)")

    df = pd.DataFrame(rows)
    df_ok = df.dropna(subset=["robust_score"]).sort_values("robust_score", ascending=False)
    df_ok.to_csv(RUN / "artifacts" / "is_param_sweep.csv", index=False)

    best = df_ok.iloc[0].to_dict() if not df_ok.empty else {}
    selection = {
        "method": "IS-only robust_score = 0.55*IS_Sharpe + 0.30*stability + 0.15*min_yearly + dd_penalty",
        "oos_start": str(OOS),
        "adf_max": ADF_MAX,
        "discovery_window": 120,
        "n_combos": len(combos),
        "n_valid": len(df_ok),
        "elapsed_sec": time.time() - t0,
        "best": {k: best[k] for k in keys + ["is_sharpe", "is_cagr", "is_max_dd", "robust_score", "min_yearly_sharpe", "yearly_sharpes"] if k in best},
        "top5": df_ok.head(5)[["n_triangles", "window", "entry_z", "exit_z", "weight_cap", "is_sharpe", "is_max_dd", "robust_score"]].to_dict(orient="records"),
    }
    save_json(RUN / "artifacts" / "is_best_params.json", selection)

    print("\n=== IS robust selection (top 5) ===")
    print(df_ok.head(5)[["n_triangles", "window", "entry_z", "exit_z", "weight_cap", "is_sharpe", "is_max_dd", "robust_score"]].to_string(index=False))
    print(f"\nWrote {RUN / 'artifacts' / 'is_best_params.json'}")


if __name__ == "__main__":
    main()
