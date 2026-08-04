"""In-sample PSA for beta-hedged funding harvest (run 9).

2D parameter grids on locked short-only carry logic; sample = pre-OOS only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_CODE_DIR = Path(__file__).resolve().parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_core import (
    ANN,
    HarvestConfig,
    OOS,
    RUN,
    align_universe,
    load_close_panel,
    load_coinglass_panel,
    load_daily_funding_payments,
    run_config,
    write_json,
)

SHARPE_TOL = 0.05
MIN_STABLE_CELLS = 3

BASELINE = HarvestConfig(
    fund_window=7,
    beta_window=120,
    top_pct=0.15,
    min_abs_funding=0.00003,
    rebalance_days=5,
    liquidity_top_n=75,
    long_short=False,
    vol_adjust=False,
    portfolio_hedge=False,
)

PSA_GRIDS: list[dict] = [
    {
        "id": "fund_window_x_top_pct",
        "x_key": "fund_window",
        "y_key": "top_pct",
        "x_vals": [3, 5, 7, 10, 14],
        "y_vals": [0.10, 0.15, 0.20, 0.25],
    },
    {
        "id": "beta_window_x_rebalance",
        "x_key": "beta_window",
        "y_key": "rebalance_days",
        "x_vals": [60, 90, 120, 150],
        "y_vals": [3, 5, 7, 10],
    },
    {
        "id": "min_funding_x_liquidity",
        "x_key": "min_abs_funding",
        "y_key": "liquidity_top_n",
        "x_vals": [0.0, 0.00003, 0.0001, 0.0002],
        "y_vals": [50, 75, 100],
    },
]


def is_metrics(returns: pd.Series) -> dict:
    r = returns.loc[returns.index < OOS].dropna()
    if len(r) < 60 or r.std() == 0:
        return {"Sharpe": 0.0, "CAGR": 0.0, "MaxDD": 0.0, "n_days": int(len(r))}
    sh = float(r.mean() / r.std() * np.sqrt(ANN))
    eq = (1 + r).cumprod()
    cagr = float(eq.iloc[-1] ** (ANN / len(r)) - 1)
    dd = float((eq / eq.cummax() - 1).min())
    return {"Sharpe": sh, "CAGR": cagr, "MaxDD": dd, "n_days": int(len(r))}


def cfg_from_baseline(**overrides) -> HarvestConfig:
    d = {**BASELINE.__dict__, **overrides}
    return HarvestConfig(**d)


def run_grid(
    grid: dict,
    close: pd.DataFrame,
    funding: pd.DataFrame,
    oi: pd.DataFrame,
) -> dict:
    x_key, y_key = grid["x_key"], grid["y_key"]
    rows: list[dict] = []

    for xv in grid["x_vals"]:
        for yv in grid["y_vals"]:
            params = {x_key: xv, y_key: yv}
            cfg = cfg_from_baseline(**params)
            ret = run_config(close, funding, oi, cfg)["returns"]
            m = is_metrics(ret)
            rows.append({x_key: xv, y_key: yv, **m})

    baseline_x = BASELINE.__dict__[x_key]
    baseline_y = BASELINE.__dict__[y_key]
    baseline_row = next(
        (r for r in rows if r[x_key] == baseline_x and r[y_key] == baseline_y),
        rows[0],
    )
    b_sh = baseline_row["Sharpe"]
    stable = [r for r in rows if r["Sharpe"] >= b_sh - SHARPE_TOL]
    rep = max(stable, key=lambda r: r["Sharpe"]) if stable else None

    sharpe_mat = pd.DataFrame(index=grid["x_vals"], columns=grid["y_vals"], dtype=float)
    for r in rows:
        sharpe_mat.loc[r[x_key], r[y_key]] = r["Sharpe"]

    return {
        "id": grid["id"],
        "x_key": x_key,
        "y_key": y_key,
        "baseline_params": {x_key: baseline_x, y_key: baseline_y},
        "baseline_is": {k: baseline_row[k] for k in ("Sharpe", "CAGR", "MaxDD", "n_days")},
        "grid_axes": {x_key: grid["x_vals"], y_key: grid["y_vals"]},
        "grid_cells": len(rows),
        "stable_cells": len(stable),
        "stable_status": "STABLE" if len(stable) >= MIN_STABLE_CELLS else "NO_STABLE",
        "representative_params": (
            {x_key: rep[x_key], y_key: rep[y_key], "Sharpe": rep["Sharpe"], "MaxDD": rep["MaxDD"]}
            if rep
            else None
        ),
        "sharpe_matrix": sharpe_mat,
        "rows": rows,
    }


def plot_heatmap(psa: dict, path: Path) -> None:
    mat = psa["sharpe_matrix"].astype(float)
    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(mat.values, aspect="auto", cmap="RdYlGn", vmin=mat.values.min(), vmax=mat.values.max())
    ax.set_xticks(range(len(mat.columns)))
    ax.set_xticklabels([str(c) for c in mat.columns], rotation=45, ha="right")
    ax.set_yticks(range(len(mat.index)))
    ax.set_yticklabels([str(i) for i in mat.index])
    ax.set_xlabel(psa["x_key"])
    ax.set_ylabel(psa["y_key"])
    ax.set_title(f"{psa['id']} — IS Sharpe ({psa['stable_status']})")
    plt.colorbar(im, ax=ax, label="IS Sharpe")

    bp = psa["baseline_params"]
    try:
        xi = list(mat.columns).index(bp[psa["y_key"]])
        yi = list(mat.index).index(bp[psa["x_key"]])
        ax.scatter([xi], [yi], s=120, facecolors="none", edgecolors="black", linewidths=2)
    except (ValueError, KeyError):
        pass

    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            val = mat.iloc[i, j]
            if pd.notna(val):
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8, color="black")

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main() -> None:
    close = load_close_panel()
    funding = load_daily_funding_payments()
    oi = load_coinglass_panel("futures_open_interest_history_ohlc_binance_1d.parquet", "close")
    close, funding, oi = align_universe(close, funding, oi)

    results: list[dict] = []
    psa_objs: list[dict] = []

    for i, grid in enumerate(PSA_GRIDS):
        print(f"Grid {i+1}/{len(PSA_GRIDS)}: {grid['id']}")
        psa = run_grid(grid, close, funding, oi)
        plot_heatmap(psa, RUN / "charts" / f"psa_{psa['id']}_heatmap.png")
        psa_objs.append(psa)
        results.append({k: v for k, v in psa.items() if k not in ("sharpe_matrix", "rows")})

    overall_stable = sum(1 for p in psa_objs if p["stable_status"] == "STABLE")
    summary = {
        "test": "parameter_sensitivity_analysis",
        "sample": "in_sample",
        "oos_start_ts": str(OOS),
        "baseline_config": BASELINE.__dict__,
        "sharpe_tolerance": SHARPE_TOL,
        "min_stable_cells": MIN_STABLE_CELLS,
        "grids_tested": len(PSA_GRIDS),
        "stable_grids": overall_stable,
        "overall_status": "STABLE" if overall_stable >= 2 else "MARGINAL" if overall_stable == 1 else "UNSTABLE",
        "grids": results,
    }
    write_json(RUN / "artifacts" / "psa_summary.json", summary)

    # Combined heatmap figure
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    for ax, psa in zip(axes, psa_objs):
        mat = psa["sharpe_matrix"].astype(float)
        im = ax.imshow(mat.values, aspect="auto", cmap="RdYlGn")
        ax.set_title(f"{psa['id']}\n({psa['stable_status']})")
        ax.set_xticks(range(len(mat.columns)))
        ax.set_xticklabels([str(c) for c in mat.columns], rotation=45, ha="right", fontsize=7)
        ax.set_yticks(range(len(mat.index)))
        ax.set_yticklabels([str(i) for i in mat.index], fontsize=7)
        plt.colorbar(im, ax=ax, fraction=0.046)
    fig.suptitle("Run 9 — Beta-hedged funding harvest PSA (in-sample Sharpe)", y=1.02)
    fig.tight_layout()
    fig.savefig(RUN / "charts" / "psa_heatmap.png", dpi=130, bbox_inches="tight")
    plt.close(fig)

    report = [
        "# PSA — Beta-hedged funding harvest",
        "",
        f"In-sample only (pre-{OOS.date()}). Sharpe tolerance ±{SHARPE_TOL}.",
        "",
        f"**Overall:** {summary['overall_status']} ({overall_stable}/{len(PSA_GRIDS)} grids stable)",
        "",
        "| Grid | Baseline IS Sharpe | Stable cells | Status | Representative |",
        "|------|-------------------|--------------|--------|----------------|",
    ]
    for psa in psa_objs:
        rep = psa["representative_params"]
        rep_s = (
            f"{psa['x_key']}={rep[psa['x_key']]}, {psa['y_key']}={rep[psa['y_key']]}, Sharpe={rep['Sharpe']:.2f}"
            if rep
            else "—"
        )
        report.append(
            f"| {psa['id']} | {psa['baseline_is']['Sharpe']:.2f} | "
            f"{psa['stable_cells']}/{psa['grid_cells']} | {psa['stable_status']} | {rep_s} |"
        )
    report.extend([
        "",
        "## Charts",
        "- `charts/psa_heatmap.png`",
        "- `charts/psa_fund_window_x_top_pct_heatmap.png`",
        "- `charts/psa_beta_window_x_rebalance_heatmap.png`",
        "- `charts/psa_min_funding_x_liquidity_heatmap.png`",
    ])
    (RUN / "report_psa.md").write_text("\n".join(report), encoding="utf-8")

    print(f"\nOverall: {summary['overall_status']}")
    for psa in psa_objs:
        print(f"  {psa['id']}: {psa['stable_status']} ({psa['stable_cells']}/{psa['grid_cells']} stable)")


if __name__ == "__main__":
    main()
