"""Sweep Sharpe enhancement levers for the correlation-regime market-neutral book."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from binance_market_indicators import FUTURES_PATH, load_close_panel, market_depth_pct, rolling_mean_pairwise_corr
from corr_regime_market_neutral import (
    ANN,
    LIQUID_LONG_BASKET,
    LIQUID_SHORT_BASKET,
    OOS,
    backtest_weights,
    build_target_weights,
    compute_metrics,
    regime_direction,
)
from correlation_cluster_signal import expanding_corr_quintile

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs" / "7"


def vol_scaled_weights(weights: pd.DataFrame, returns: pd.DataFrame, target_ann_vol: float = 0.15, window: int = 20) -> pd.DataFrame:
    port_ret = (weights.shift(1).fillna(0) * returns).sum(axis=1)
    realized = port_ret.rolling(window).std() * np.sqrt(ANN)
    scale = (target_ann_vol / realized).clip(0, 2).shift(1).fillna(0)
    return weights.mul(scale, axis=0)


def smoothed_direction(quintile: pd.Series, min_days: int = 3) -> pd.Series:
    q = quintile.shift(1)
    out = pd.Series(0.0, index=quintile.index)
    for val in (1, 2):
        streak = (q == val).astype(int)
        run = streak.groupby((streak != streak.shift()).cumsum()).cumsum()
        out[(q == val) & (run >= min_days)] = 1.0
    return out


def depth_gated_direction(base_dir: pd.Series, depth: pd.Series, min_depth_pct: float = 50.0) -> pd.Series:
    """Only trade low-corr longs when market breadth is above median."""
    depth_lag = depth.shift(1)
    med = depth_lag.expanding(min_periods=120).median()
    gate = depth_lag >= med
    out = base_dir.copy()
    out[(base_dir > 0) & ~gate] = 0.0
    return out


def top_n_basket(basket: list[str], n: int) -> list[str]:
    return basket[:n]


def main() -> None:
    close = load_close_panel(FUTURES_PATH)
    returns = close.pct_change()
    corr = rolling_mean_pairwise_corr(returns)
    quintile = expanding_corr_quintile(corr)
    depth = market_depth_pct(close)

    variants: dict[str, pd.DataFrame] = {}

    # Baseline
    d = regime_direction(quintile, "regime_flip")
    variants["baseline_regime_flip"] = build_target_weights(d, LIQUID_LONG_BASKET, LIQUID_SHORT_BASKET, close.columns)

    d = regime_direction(quintile, "low_only")
    variants["low_corr_only"] = build_target_weights(d, LIQUID_LONG_BASKET, LIQUID_SHORT_BASKET, close.columns)

    # Concentrated baskets (top 5 by spread rank in fixed lists)
    d = regime_direction(quintile, "low_only")
    variants["low_only_top5"] = build_target_weights(
        d, top_n_basket(LIQUID_LONG_BASKET, 5), top_n_basket(LIQUID_SHORT_BASKET, 5), close.columns
    )

    # Smoothed entry: require 3 consecutive low-corr days
    d = smoothed_direction(quintile, min_days=3)
    variants["low_only_smoothed_3d"] = build_target_weights(d, LIQUID_LONG_BASKET, LIQUID_SHORT_BASKET, close.columns)

    # Market depth gate on low-corr longs
    d = depth_gated_direction(regime_direction(quintile, "low_only"), depth)
    variants["low_only_depth_gate"] = build_target_weights(d, LIQUID_LONG_BASKET, LIQUID_SHORT_BASKET, close.columns)

    # Vol targeting 15% ann
    base_w = variants["low_corr_only"]
    variants["low_only_vol_target_15"] = vol_scaled_weights(base_w, returns, target_ann_vol=0.15)

    # Weekly rebalance: hold weights constant within each week
    weekly = variants["low_corr_only"].resample("W-FRI").last().reindex(close.index, method="ffill").fillna(0)
    variants["low_only_weekly_rebal"] = weekly

    results = {}
    for name, weights in variants.items():
        port = backtest_weights(close, weights)
        m = compute_metrics(port, weights)
        results[name] = m

    ranked = sorted(results.items(), key=lambda x: x[1]["Sharpe"], reverse=True)
    summary = {
        "ranked_by_full_sharpe": [
            {"variant": k, "Sharpe": v["Sharpe"], "oos_sharpe": v["out_of_sample"]["Sharpe"], "max_dd": v["MaxDD"]}
            for k, v in ranked
        ],
        "details": results,
    }
    out = RUN / "artifacts" / "sharpe_enhancement_sweep.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary["ranked_by_full_sharpe"], indent=2))


if __name__ == "__main__":
    main()
