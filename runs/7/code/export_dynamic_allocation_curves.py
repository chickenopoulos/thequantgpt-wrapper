"""Export linear equity curves for dynamic allocation variants vs baseline."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from binance_market_indicators import FUTURES_PATH, load_close_panel, market_depth_pct, rolling_mean_pairwise_corr
from corr_regime_market_neutral import (
    LIQUID_LONG_BASKET,
    LIQUID_SHORT_BASKET,
    OOS,
    always_in_market_direction,
    backtest_weights,
    build_target_weights,
)
from correlation_cluster_signal import expanding_corr_quintile
from dynamic_allocation_sweep import (
    apply_gross_scale,
    calibrate_spread_map,
    conviction_gross_scale,
    spread_weighted_legs,
    vol_target_scale,
)

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs" / "7"
BASELINE = "baseline_equal_weight"

# Variants to chart (baseline + meaningful overlays from sweep)
CHART_VARIANTS = {
    BASELINE: "Baseline (equal weight)",
    "spread_weighted_is": "Spread-weighted legs",
    "conviction_sizing_50_100": "Conviction sizing 50–100%",
    "conviction_sizing_70_100": "Conviction sizing 70–100%",
    "vol_target_15pct": "Vol target 15%",
    "vol_target_20pct": "Vol target 20%",
}


def build_variants(close: pd.DataFrame) -> dict[str, pd.DataFrame]:
    returns = close.pct_change()
    corr = rolling_mean_pairwise_corr(returns)
    quintile = expanding_corr_quintile(corr)
    depth = market_depth_pct(close)
    direction = always_in_market_direction(quintile, depth)
    base_w = build_target_weights(direction, LIQUID_LONG_BASKET, LIQUID_SHORT_BASKET, close.columns)
    spread_map = calibrate_spread_map(close, quintile)

    return {
        BASELINE: base_w,
        "spread_weighted_is": spread_weighted_legs(
            direction, spread_map, LIQUID_LONG_BASKET, LIQUID_SHORT_BASKET, close.columns
        ),
        "conviction_sizing_50_100": apply_gross_scale(
            base_w, conviction_gross_scale(quintile, depth, direction, min_gross=0.5)
        ),
        "conviction_sizing_70_100": apply_gross_scale(
            base_w, conviction_gross_scale(quintile, depth, direction, min_gross=0.7)
        ),
        "vol_target_15pct": vol_target_scale(base_w, returns, 0.15),
        "vol_target_20pct": vol_target_scale(base_w, returns, 0.20),
    }


def equity_frame(returns: dict[str, pd.Series]) -> pd.DataFrame:
    df = pd.DataFrame(returns)
    eq = (1 + df).cumprod()
    eq.columns = [CHART_VARIANTS.get(c, c) for c in eq.columns]
    eq["sample"] = ["in_sample" if t < OOS else "out_of_sample" for t in eq.index]
    return eq


def plot_linear(equity: pd.DataFrame, out_path: Path) -> None:
    value_cols = [c for c in equity.columns if c != "sample"]
    fig, ax = plt.subplots(figsize=(12, 6))

    colors = {
        "Baseline (equal weight)": "#333333",
        "Spread-weighted legs": "#27ae60",
        "Conviction sizing 50–100%": "#2980b9",
        "Conviction sizing 70–100%": "#8e44ad",
        "Vol target 15%": "#e67e22",
        "Vol target 20%": "#c0392b",
    }

    for col in value_cols:
        lw = 2.2 if col.startswith("Baseline") else 1.3
        ls = "--" if col.startswith("Baseline") else "-"
        ax.plot(
            equity.index,
            equity[col],
            label=col,
            linewidth=lw,
            linestyle=ls,
            color=colors.get(col),
            alpha=0.95 if col.startswith("Baseline") else 0.85,
        )

    ax.axvline(OOS, color="gray", linestyle=":", linewidth=0.9, label="OOS start")
    ax.set_ylabel("Growth of $1")
    ax.set_xlabel("Date (UTC)")
    ax.set_title("Dynamic allocation variants vs baseline (linear)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def main() -> None:
    close = load_close_panel(FUTURES_PATH)
    weight_variants = build_variants(close)

    returns: dict[str, pd.Series] = {}
    for name, weights in weight_variants.items():
        returns[name] = backtest_weights(close, weights)

    equity = equity_frame(returns)

    charts = RUN / "charts"
    artifacts = RUN / "artifacts"
    charts.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)

    plot_linear(equity, charts / "dynamic_allocation_vs_baseline_linear.png")
    equity.to_csv(artifacts / "dynamic_allocation_vs_baseline.csv")

    meta = {
        "baseline": BASELINE,
        "variants": list(CHART_VARIANTS.values()),
        "chart": "charts/dynamic_allocation_vs_baseline_linear.png",
        "csv": "artifacts/dynamic_allocation_vs_baseline.csv",
        "oos_start": str(OOS.date()),
    }
    (artifacts / "dynamic_allocation_export_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
