#!/usr/bin/env python3
"""In-sample PSA for BTC five-strategy ensemble (runs/5).

2D grids per sleeve on tunable parameters; sample = in-sample only (pre-2025-01-01).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
CODE = REPO / "runs" / "5" / "code"
sys.path.insert(0, str(CODE))

from btc_all_providers_data import load_all_features  # noqa: E402
from btc_all_providers_ensemble import (  # noqa: E402
    BUILDERS,
    SELECTED,
    SleeveSpec,
    returns_from_position,
)
from btc_all_providers_search import ANN, OOS, eval_pos  # noqa: E402

RUN = REPO / "runs" / "5"
SHARPE_TOL = 0.05
MIN_STABLE_CELLS = 3

PSA_GRIDS: dict[str, dict[str, list]] = {
    "exchange_flow": {
        "q_ent": [0.03, 0.05, 0.07, 0.10, 0.15],
        "q_ex": [0.75, 0.80, 0.85, 0.90, 0.95],
    },
    "derivatives_funding": {
        "q_ent": [0.05, 0.10, 0.15, 0.20, 0.25],
        "q_ex": [0.75, 0.80, 0.85, 0.90, 0.95],
    },
    "open_interest": {
        "q_ent": [0.05, 0.10, 0.15, 0.20, 0.25],
        "q_ex": [0.70, 0.75, 0.80, 0.85, 0.90],
    },
    "liquidation_fade": {
        "q": [0.90, 0.93, 0.95, 0.97, 0.99],
        "hold": [3, 5, 7, 10, 14],
    },
}

MIN_TRADES_BY_FAMILY = {
    "exchange_flow": 30,
    "derivatives_funding": 4,
    "open_interest": 4,
    "liquidation_fade": 15,
}


def is_metrics(close: pd.Series, pos: pd.Series) -> dict:
    rets = returns_from_position(close, pos)
    is_idx = rets.index < OOS
    r = rets.loc[is_idx].dropna()
    if len(r) < 20 or r.std() == 0:
        return {"Sharpe": 0.0, "MaxDD": 0.0, "num_trades": 0}
    sh = float(np.sqrt(ANN) * r.mean() / r.std())
    cum = (1 + r).cumprod()
    dd = float((cum / cum.cummax() - 1).min())
    trades = int(pos.loc[is_idx].diff().abs().fillna(0).gt(0).sum())
    return {"Sharpe": sh, "MaxDD": dd, "num_trades": trades}


def run_sleeve_psa(close: pd.Series, f: dict, spec: SleeveSpec) -> dict:
    grid_def = PSA_GRIDS[spec.family]
    keys = list(grid_def.keys())
    baseline = dict(spec.params)
    rows: list[dict] = []

    for q_ent in grid_def[keys[0]]:
        for q_ex in grid_def[keys[1]]:
            params = dict(baseline)
            params[keys[0]] = q_ent
            params[keys[1]] = q_ex
            pos = BUILDERS[spec.family](close, f, params)
            m = is_metrics(close, pos)
            rows.append({keys[0]: q_ent, keys[1]: q_ex, **m})

    baseline_row = next(
        (r for r in rows if r[keys[0]] == baseline[keys[0]] and r[keys[1]] == baseline[keys[1]]),
        rows[0],
    )
    b_sh = baseline_row["Sharpe"]
    min_tr = MIN_TRADES_BY_FAMILY.get(spec.family, 10)
    stable = [r for r in rows if r["Sharpe"] >= b_sh - SHARPE_TOL and r["num_trades"] >= min_tr]
    rep = max(stable, key=lambda r: r["Sharpe"]) if stable else None

    sharpe_mat = pd.DataFrame(
        index=grid_def[keys[0]],
        columns=grid_def[keys[1]],
        dtype=float,
    )
    for r in rows:
        sharpe_mat.loc[r[keys[0]], r[keys[1]]] = r["Sharpe"]

    return {
        "id": spec.id,
        "family": spec.family,
        "provider": spec.provider,
        "name": spec.name,
        "baseline_params": {k: baseline[k] for k in keys},
        "baseline_is": {k: baseline_row[k] for k in ("Sharpe", "MaxDD", "num_trades")},
        "grid_axes": grid_def,
        "grid_cells": len(rows),
        "stable_cells": len(stable),
        "stable_status": "STABLE" if len(stable) >= MIN_STABLE_CELLS else "NO_STABLE",
        "representative_params": (
            {keys[0]: rep[keys[0]], keys[1]: rep[keys[1]], "Sharpe": rep["Sharpe"], "MaxDD": rep["MaxDD"]}
            if rep
            else None
        ),
        "sharpe_tolerance": SHARPE_TOL,
        "min_trades": min_tr,
        "results": rows,
        "sharpe_matrix": sharpe_mat,
        "x_key": keys[1],
        "y_key": keys[0],
    }


def plot_heatmap(psa: dict, path: Path) -> None:
    mat = psa["sharpe_matrix"]
    fig, ax = plt.subplots(figsize=(6, 5))
    vals = mat.values.astype(float)
    im = ax.imshow(
        vals,
        aspect="auto",
        origin="lower",
        cmap="RdYlGn",
        vmin=max(-0.5, np.nanmin(vals)),
        vmax=max(0.5, np.nanmax(vals)),
    )
    ax.set_title(f"{psa['id']} IS Sharpe PSA\n{psa['name'][:50]}")
    ax.set_xticks(range(len(mat.columns)))
    ax.set_xticklabels([f"{c:.2f}" if isinstance(c, float) else str(c) for c in mat.columns], rotation=45)
    ax.set_yticks(range(len(mat.index)))
    ax.set_yticklabels([f"{i:.2f}" if isinstance(i, float) else str(i) for i in mat.index])
    ax.set_xlabel(psa["x_key"])
    ax.set_ylabel(psa["y_key"])
    plt.colorbar(im, ax=ax, fraction=0.046)
    # mark baseline
    bp = psa["baseline_params"]
    try:
        xi = list(mat.columns).index(bp[psa["x_key"]])
        yi = list(mat.index).index(bp[psa["y_key"]])
        ax.scatter([xi], [yi], s=120, edgecolors="black", facecolors="none", linewidths=2)
    except ValueError:
        pass
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main() -> None:
    for sub in ("artifacts", "charts", "logs"):
        (RUN / sub).mkdir(parents=True, exist_ok=True)

    _, f, meta = load_all_features()
    close = f["close"]

    sleeve_results = []
    for spec in SELECTED:
        psa = run_sleeve_psa(close, f, spec)
        plot_heatmap(psa, RUN / "charts" / f"psa_{spec.id}_heatmap.png")
        sleeve_results.append({
            k: v for k, v in psa.items() if k not in ("sharpe_matrix",)
        })

    n_stable = sum(1 for s in sleeve_results if s["stable_status"] == "STABLE")

    summary = {
        "test": "parameter_sensitivity",
        "sample": "in_sample",
        "oos_start_ts": str(OOS),
        "symbol": "BTCUSDT",
        "data_providers": meta["providers"],
        "sharpe_tolerance": SHARPE_TOL,
        "min_stable_cells": MIN_STABLE_CELLS,
        "sleeves_stable": n_stable,
        "sleeves_total": len(sleeve_results),
        "strategies": sleeve_results,
    }
    (RUN / "artifacts" / "psa_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")

    # Combined overview chart
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    axes = axes.flatten()
    for ax, spec in zip(axes, SELECTED):
        psa = run_sleeve_psa(close, f, spec)
        mat = psa["sharpe_matrix"]
        im = ax.imshow(mat.values, aspect="auto", origin="lower", cmap="RdYlGn", vmin=-0.5, vmax=2.0)
        ax.set_title(f"{spec.id} ({psa['stable_status']})")
        plt.colorbar(im, ax=ax, fraction=0.046)
    if len(SELECTED) < len(axes):
        axes[-1].axis("off")
    fig.suptitle("BTC Ensemble PSA — In-Sample Sharpe Grids")
    fig.tight_layout()
    fig.savefig(RUN / "charts" / "psa_heatmap.png", dpi=120)
    plt.close(fig)

    run_state = json.loads((RUN / "run.json").read_text())
    run_state["last_scope"] = "psa_in_sample"
    completed = run_state.get("completed_steps", [])
    if "psa_in_sample" not in completed:
        completed.append("psa_in_sample")
    run_state["completed_steps"] = completed
    (RUN / "run.json").write_text(json.dumps(run_state, indent=2) + "\n")

    print("=== BTC Ensemble PSA (in-sample) ===")
    for s in sleeve_results:
        bp = s["baseline_is"]
        rep = s["representative_params"]
        print(
            f"{s['id']} [{s['stable_status']}] baseline IS Sharpe={bp['Sharpe']:.3f} "
            f"stable_cells={s['stable_cells']}/{s['grid_cells']}"
        )
        if rep:
            print(f"  rep: {s['x_key']}={rep[s['x_key']]}, {s['y_key']}={rep[s['y_key']]} -> Sharpe={rep['Sharpe']:.3f}")
    print(f"\nStable sleeves: {n_stable}/{len(sleeve_results)}")
    print(f"Wrote {RUN / 'artifacts' / 'psa_summary.json'}")


if __name__ == "__main__":
    main()
