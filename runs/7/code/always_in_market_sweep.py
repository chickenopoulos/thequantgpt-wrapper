"""Find max-Sharpe always-invested market-neutral portfolio variants."""

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
)
from correlation_cluster_signal import expanding_corr_quintile

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs" / "7"
MIN_GROSS = 0.95


def direction_variants(quintile: pd.Series, corr: pd.Series, depth: pd.Series) -> dict[str, pd.Series]:
    q = quintile.shift(1)
    corr_lag = corr.shift(1)
    depth_lag = depth.shift(1)
    idx = quintile.index

    corr_rank = corr_lag.expanding(min_periods=120).rank(pct=True)
    depth_rank = depth_lag.expanding(min_periods=120).rank(pct=True)

    out: dict[str, pd.Series] = {}

    out["always_on"] = pd.Series(1.0, index=idx)

    # Never flat: |direction| = 1 always
    d = pd.Series(1.0, index=idx)
    d[q >= 4] = -1.0
    out["regime_switch_q4"] = d  # Q1-Q3 long dispersion, Q4-Q5 flip

    d = pd.Series(1.0, index=idx)
    d[q >= 3] = -1.0
    out["regime_switch_q3"] = d  # Q1-Q2 long, Q3-Q5 flip

    out["regime_flip"] = pd.Series(0.0, index=idx)
    out["regime_flip"].loc[q.isin([1, 2])] = 1.0
    out["regime_flip"].loc[q.isin([4, 5])] = -1.0

    # Continuous corr rank mapped to {-1, +1} with full investment
    out["corr_rank_sign"] = np.sign(0.5 - corr_rank).replace(0, 1.0)

    # Blend corr + depth ranks -> sign
    blend = 0.6 * corr_rank + 0.4 * depth_rank
    out["corr_depth_blend_sign"] = np.sign(0.5 - blend).replace(0, 1.0)

    # Quintile linear: map Q1..Q5 to +1..-1, normalize to unit magnitude
    qmap = {1: 1.0, 2: 0.5, 3: 0.0, 4: -0.5, 5: -1.0}
    lin = q.map(qmap).fillna(0)
    out["quintile_linear_scaled"] = np.sign(lin).replace(0, 1.0)  # Q3 -> +1

    lin2 = q.map({1: 1.0, 2: 1.0, 3: -1.0, 4: -1.0, 5: -1.0}).fillna(1.0)
    out["quintile_half_split"] = lin2

    # Smoothed sign: 5d MA of quintile centered
    q_centered = q - 3
    smooth = q_centered.rolling(5, min_periods=3).mean()
    out["quintile_smooth_sign"] = np.sign(-smooth).replace(0, 1.0)

    # High-corr only flip when depth also weak
    d = pd.Series(1.0, index=idx)
    flip = (q >= 4) & (depth_lag < depth_lag.expanding(min_periods=120).median())
    d[flip] = -1.0
    out["flip_high_corr_weak_depth"] = d

    # High-corr flip OR low depth
    d = pd.Series(1.0, index=idx)
    flip = (q >= 4) | (depth_lag < depth_lag.expanding(min_periods=120).quantile(0.35))
    d[flip] = -1.0
    out["flip_high_corr_or_low_depth"] = d

    return out


def main() -> None:
    close = load_close_panel(FUTURES_PATH)
    returns = close.pct_change()
    corr = rolling_mean_pairwise_corr(returns)
    quintile = expanding_corr_quintile(corr)
    depth = market_depth_pct(close)

    directions = direction_variants(quintile, corr, depth)
    results = []

    for name, direction in directions.items():
        weights = build_target_weights(direction, LIQUID_LONG_BASKET, LIQUID_SHORT_BASKET, close.columns)
        port = backtest_weights(close, weights)
        m = compute_metrics(port, weights)
        gross = m["avg_gross_exposure"]
        if gross < MIN_GROSS:
            continue
        results.append(
            {
                "variant": name,
                "full_sharpe": m["Sharpe"],
                "is_sharpe": m["in_sample"]["Sharpe"],
                "oos_sharpe": m["out_of_sample"]["Sharpe"],
                "max_dd": m["MaxDD"],
                "cagr": m["CAGR"],
                "avg_gross_exposure": gross,
                "trades": m["trades"],
            }
        )

    ranked = sorted(results, key=lambda x: x["is_sharpe"], reverse=True)
    payload = {"min_gross_exposure": MIN_GROSS, "ranked_by_is_sharpe": ranked}
    out = RUN / "artifacts" / "always_in_market_sweep.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(ranked[:8], indent=2))


if __name__ == "__main__":
    main()
