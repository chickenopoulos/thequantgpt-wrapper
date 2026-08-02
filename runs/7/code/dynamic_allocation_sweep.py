"""Sweep position sizing and dynamic allocation overlays on the always-in portfolio."""

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
    always_in_market_direction,
    backtest_weights,
    build_target_weights,
    compute_metrics,
)
from correlation_cluster_signal import expanding_corr_quintile, spread_signal_stats

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs" / "7"


def inverse_vol_leg_weights(
    direction: pd.Series,
    returns: pd.DataFrame,
    long_basket: list[str],
    short_basket: list[str],
    columns: pd.Index,
    vol_window: int = 20,
) -> pd.DataFrame:
    vol = returns.rolling(vol_window).std()
    weights = pd.DataFrame(0.0, index=direction.index, columns=columns)

    for t in direction.index:
        d = direction.loc[t]
        if d == 0:
            continue
        long_vols = vol.loc[t, [a for a in long_basket if a in vol.columns]].replace(0, np.nan)
        short_vols = vol.loc[t, [a for a in short_basket if a in vol.columns]].replace(0, np.nan)
        if long_vols.dropna().empty or short_vols.dropna().empty:
            continue
        lw = (1 / long_vols).fillna(0)
        sw = (1 / short_vols).fillna(0)
        lw = lw / lw.sum() * 0.5 if lw.sum() > 0 else lw
        sw = sw / sw.sum() * 0.5 if sw.sum() > 0 else sw
        for asset, w in lw.items():
            weights.at[t, asset] = d * w
        for asset, w in sw.items():
            weights.at[t, asset] += d * (-w)
    return weights


def spread_weighted_legs(
    direction: pd.Series,
    spread_map: dict[str, float],
    long_basket: list[str],
    short_basket: list[str],
    columns: pd.Index,
) -> pd.DataFrame:
    """Weight legs by IS-calibrated Q1-Q5 spread magnitude."""
    long_w = np.array([max(spread_map.get(a, 0), 0.01) for a in long_basket], dtype=float)
    short_w = np.array([max(abs(spread_map.get(a, 0)), 0.01) for a in short_basket], dtype=float)
    long_w = long_w / long_w.sum() * 0.5
    short_w = short_w / short_w.sum() * 0.5

    weights = pd.DataFrame(0.0, index=direction.index, columns=columns)
    for asset, w in zip(long_basket, long_w):
        if asset in weights.columns:
            weights[asset] = direction * w
    for asset, w in zip(short_basket, short_w):
        if asset in weights.columns:
            weights[asset] += direction * (-w)
    return weights


def vol_target_scale(
    weights: pd.DataFrame,
    returns: pd.DataFrame,
    target_ann_vol: float,
    window: int = 20,
    max_leverage: float = 1.5,
) -> pd.DataFrame:
    port_ret = (weights.shift(1).fillna(0) * returns).sum(axis=1)
    realized = port_ret.rolling(window).std() * np.sqrt(ANN)
    scale = (target_ann_vol / realized).clip(0, max_leverage).shift(1).fillna(0)
    return weights.mul(scale, axis=0)


def conviction_gross_scale(
    quintile: pd.Series,
    depth: pd.Series,
    direction: pd.Series,
    *,
    q_threshold: int = 3,
    depth_quantile: float = 0.35,
    min_gross: float = 0.5,
) -> pd.Series:
    """Scale gross exposure by regime conviction (1-bar lag)."""
    q = quintile.shift(1)
    depth_lag = depth.shift(1)
    depth_thr = depth_lag.expanding(min_periods=120).quantile(depth_quantile)

    # Distance from flip boundary: low corr + high depth = high conviction for +1
    corr_score = (q_threshold - q).clip(0, 2) / 2  # Q1=1, Q2=0.5, Q3+=0
    depth_score = ((depth_lag - depth_thr) / depth_thr.replace(0, np.nan)).clip(0, 1).fillna(0)
    flip = (q >= q_threshold) & (depth_lag < depth_thr)
    conv = (0.6 * corr_score + 0.4 * depth_score).fillna(0)
    conv[flip] = ((q - q_threshold + 1).clip(0, 2) / 2 + (1 - depth_lag / depth_thr).clip(0, 1).fillna(0)) / 2
    return (min_gross + (1 - min_gross) * conv).clip(min_gross, 1.0)


def apply_gross_scale(weights: pd.DataFrame, scale: pd.Series) -> pd.DataFrame:
    return weights.mul(scale.reindex(weights.index).fillna(0), axis=0)


def calibrate_spread_map(close: pd.DataFrame, quintile: pd.Series) -> dict[str, float]:
    is_idx = close.index[close.index < OOS]
    spread = spread_signal_stats(close.loc[is_idx].pct_change(), quintile.reindex(is_idx))
    return spread.set_index("asset")["spread_q1_minus_q5"].to_dict()


def main() -> None:
    close = load_close_panel(FUTURES_PATH)
    returns = close.pct_change()
    corr = rolling_mean_pairwise_corr(returns)
    quintile = expanding_corr_quintile(corr)
    depth = market_depth_pct(close)
    direction = always_in_market_direction(quintile, depth)
    base_w = build_target_weights(direction, LIQUID_LONG_BASKET, LIQUID_SHORT_BASKET, close.columns)
    spread_map = calibrate_spread_map(close, quintile)

    variants: dict[str, pd.DataFrame] = {
        "baseline_equal_weight": base_w,
        "inverse_vol_20d": inverse_vol_leg_weights(direction, returns, LIQUID_LONG_BASKET, LIQUID_SHORT_BASKET, close.columns, 20),
        "inverse_vol_40d": inverse_vol_leg_weights(direction, returns, LIQUID_LONG_BASKET, LIQUID_SHORT_BASKET, close.columns, 40),
        "spread_weighted_is": spread_weighted_legs(direction, spread_map, LIQUID_LONG_BASKET, LIQUID_SHORT_BASKET, close.columns),
        "vol_target_15pct": vol_target_scale(base_w, returns, 0.15),
        "vol_target_20pct": vol_target_scale(base_w, returns, 0.20),
        "vol_target_25pct": vol_target_scale(base_w, returns, 0.25),
        "conviction_sizing_50_100": apply_gross_scale(
            base_w, conviction_gross_scale(quintile, depth, direction, min_gross=0.5)
        ),
        "conviction_sizing_70_100": apply_gross_scale(
            base_w, conviction_gross_scale(quintile, depth, direction, min_gross=0.7)
        ),
        "invvol_plus_voltarget_20": vol_target_scale(
            inverse_vol_leg_weights(direction, returns, LIQUID_LONG_BASKET, LIQUID_SHORT_BASKET, close.columns, 20),
            returns,
            0.20,
        ),
        "spread_plus_voltarget_20": vol_target_scale(
            spread_weighted_legs(direction, spread_map, LIQUID_LONG_BASKET, LIQUID_SHORT_BASKET, close.columns),
            returns,
            0.20,
        ),
    }

    rows = []
    for name, weights in variants.items():
        port = backtest_weights(close, weights)
        m = compute_metrics(port, weights)
        rows.append(
            {
                "variant": name,
                "full_sharpe": m["Sharpe"],
                "is_sharpe": m["in_sample"]["Sharpe"],
                "oos_sharpe": m["out_of_sample"]["Sharpe"],
                "max_dd": m["MaxDD"],
                "cagr": m["CAGR"],
                "avg_gross": m["avg_gross_exposure"],
                "trades": m["trades"],
            }
        )

    ranked = sorted(rows, key=lambda x: x["full_sharpe"], reverse=True)
    payload = {"baseline": "always_in_equal_weight", "ranked": ranked}
    out = RUN / "artifacts" / "dynamic_allocation_sweep.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(ranked, indent=2))


if __name__ == "__main__":
    main()
