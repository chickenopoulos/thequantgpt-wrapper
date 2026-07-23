#!/usr/bin/env python3
"""BTC-only percentile-rank momentum edge study.

User spec:
- Long when recent rise is unusually strong vs historical rises
- Short when drop is unusually strong vs historical drops
- Wide entry/exit thresholds to limit turnover
- 0.1% round-trip all-in cost (fee + slippage)
- OOS cut-off 2025-01-01
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

REPO = Path(__file__).resolve().parents[3]
CODE = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE))

from calibration_pipeline import load_hourly, row_to_params  # noqa: E402
from prm_engine import (  # noqa: E402
    ANN_HOURLY,
    BASELINE,
    PRMParams,
    composite_scores,
    fast_backtest_metrics,
    parametric_grid,
    sharpe_ratio,
    state_machine_signals,
    total_return,
)

RUN = REPO / "runs" / "prm_landolfi_momentum"
OOS_START = pd.Timestamp("2025-01-01", tz="UTC")
# 0.1% round-trip all-in => 5 bps per side
COST_PER_SIDE = 0.0005
SYMBOL = "BTCUSDT"


def wide_threshold_grid() -> list[PRMParams]:
    """Grid emphasizing wide hysteresis bands and longer holds."""
    horizon_sets = [
        (6, 24, 72),
        (12, 48, 168),
        (24, 72, 168),
    ]
    weight_sets = [
        (0.5, 0.3, 0.2),
        (0.4, 0.35, 0.25),
    ]
    rank_windows = [720, 1440, 2160, 2880]  # 30d to 120d hourly
    # Wide bands only — user asked to avoid overtrading
    threshold_pairs = [
        (0.55, 0.85),
        (0.60, 0.90),
        (0.65, 0.92),
        (0.70, 0.95),
    ]
    hold_caps = [72, 96, 168, 240]
    vol_flags = [True, False]

    grid: list[PRMParams] = []
    for horizons in horizon_sets:
        for weights in weight_sets:
            for rw in rank_windows:
                for qx, qe in threshold_pairs:
                    if qx >= qe:
                        continue
                    for mh in hold_caps:
                        for vn in vol_flags:
                            grid.append(
                                PRMParams(
                                    horizons=horizons,
                                    weights=weights,
                                    rank_window=rw,
                                    vol_span=24,
                                    vol_norm=vn,
                                    qe=qe,
                                    qx=qx,
                                    max_hold=mh,
                                )
                            )
    return grid


def backtest_returns(
    close: pd.Series,
    s_long: pd.Series,
    s_short: pd.Series,
    params: PRMParams,
    *,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> pd.Series:
    """Return series with 0.1% RT cost model."""
    le, lx, se, sx = state_machine_signals(
        s_long, s_short, qe=params.qe, qx=params.qx, max_hold=params.max_hold
    )
    le = le.shift(1, fill_value=False).astype(bool)
    lx = lx.shift(1, fill_value=False).astype(bool)
    se = se.shift(1, fill_value=False).astype(bool)
    sx = sx.shift(1, fill_value=False).astype(bool)

    idx = close.index
    if start is not None:
        mask = idx >= start
        le, lx, se, sx = le & mask, lx & mask, se & mask, sx & mask
    if end is not None:
        mask = idx < end
        le, lx, se, sx = le & mask, lx & mask, se & mask, sx & mask

    n = len(close)
    position = np.zeros(n, dtype=np.int8)
    pos = 0
    le_a, lx_a, se_a, sx_a = le.to_numpy(), lx.to_numpy(), se.to_numpy(), sx.to_numpy()
    for i in range(n):
        if le_a[i]:
            pos = 1
        elif se_a[i]:
            pos = -1
        elif lx_a[i] or sx_a[i]:
            pos = 0
        position[i] = pos

    ret = close.pct_change().fillna(0.0).to_numpy()
    strat = np.zeros(n)
    for i in range(1, n):
        strat[i] = position[i - 1] * ret[i]
        if position[i] != position[i - 1]:
            strat[i] -= COST_PER_SIDE * abs(position[i] - position[i - 1])

    return pd.Series(strat, index=close.index)


def segment_metrics(rets: pd.Series, trades: float, avg_hold: float) -> dict:
    r = rets.dropna()
    if r.empty:
        return {
            "sharpe": 0.0,
            "total_return": 0.0,
            "cagr": 0.0,
            "max_dd": 0.0,
            "num_trades": trades,
            "avg_hold_h": avg_hold,
        }
    eq = (1 + r).cumprod()
    dd = eq / eq.cummax() - 1
    years = len(r) / ANN_HOURLY
    cagr = float(eq.iloc[-1] ** (1 / years) - 1) if years > 0 and eq.iloc[-1] > 0 else 0.0
    return {
        "sharpe": sharpe_ratio(r, ANN_HOURLY),
        "total_return": total_return(r),
        "cagr": cagr,
        "max_dd": float(dd.min()),
        "num_trades": trades,
        "avg_hold_h": avg_hold,
    }


def evaluate_config(close: pd.Series, params: PRMParams) -> dict:
    s_long, s_short = composite_scores(close, params)
    full = fast_backtest_metrics(
        close, s_long, s_short, params, fee=COST_PER_SIDE, slippage=0.0, ann=ANN_HOURLY
    )
    rets = backtest_returns(close, s_long, s_short, params)
    is_rets = rets[rets.index < OOS_START]
    oos_rets = rets[rets.index >= OOS_START]
    is_m = segment_metrics(is_rets, full["num_trades"], full["avg_hold_h"])
    oos_m = segment_metrics(oos_rets, full["num_trades"], full["avg_hold_h"])
    return {
        **params.as_dict(),
        "full_sharpe": full["sharpe"],
        "full_return": full["total_return"],
        "full_trades": full["num_trades"],
        "full_avg_trade_bps": full["avg_trade_bps"],
        "full_avg_hold_h": full["avg_hold_h"],
        "is_sharpe": is_m["sharpe"],
        "is_return": is_m["total_return"],
        "is_cagr": is_m["cagr"],
        "is_max_dd": is_m["max_dd"],
        "oos_sharpe": oos_m["sharpe"],
        "oos_return": oos_m["total_return"],
        "oos_cagr": oos_m["cagr"],
        "oos_max_dd": oos_m["max_dd"],
    }


def trade_level_stats(close: pd.Series, params: PRMParams) -> dict:
    """Per-trade PnL on OOS for significance testing."""
    s_long, s_short = composite_scores(close, params)
    le, lx, se, sx = state_machine_signals(
        s_long, s_short, qe=params.qe, qx=params.qx, max_hold=params.max_hold
    )
    le = le.shift(1, fill_value=False).astype(bool)
    lx = lx.shift(1, fill_value=False).astype(bool)
    se = se.shift(1, fill_value=False).astype(bool)
    sx = sx.shift(1, fill_value=False).astype(bool)
    rets = backtest_returns(close, s_long, s_short, params)

    trade_pnls: list[float] = []
    in_trade = False
    entry_i = 0
    for i in range(1, len(close)):
        ts = close.index[i]
        if ts < OOS_START:
            if le.iloc[i] or se.iloc[i]:
                in_trade = True
                entry_i = i
            elif in_trade and (lx.iloc[i] or sx.iloc[i]):
                in_trade = False
            continue
        if not in_trade and (le.iloc[i] or se.iloc[i]):
            in_trade = True
            entry_i = i
        elif in_trade and (lx.iloc[i] or sx.iloc[i]):
            trade_pnls.append(float((1 + rets.iloc[entry_i + 1 : i + 1]).prod() - 1))
            in_trade = False

    if len(trade_pnls) < 2:
        return {"n_trades": len(trade_pnls), "mean_bps": 0.0, "t_stat": 0.0, "p_value": 1.0}
    arr = np.array(trade_pnls)
    t_stat, p_val = stats.ttest_1samp(arr, 0.0)
    return {
        "n_trades": len(trade_pnls),
        "mean_bps": float(arr.mean() * 10_000),
        "win_rate": float((arr > 0).mean()),
        "t_stat": float(t_stat),
        "p_value": float(p_val),
    }


def run_study() -> dict:
    close = load_hourly(SYMBOL)
    print(f"BTC bars: {len(close)} | {close.index.min()} -> {close.index.max()}")
    print(f"Cost: {COST_PER_SIDE * 2 * 100:.2f}% round-trip | OOS from {OOS_START.date()}")

    # 1) Wide-threshold grid (user focus)
    wide_grid = wide_threshold_grid()
    print(f"\nWide-threshold grid: {len(wide_grid)} configs")
    wide_rows = []
    signal_cache: dict = {}
    for i, p in enumerate(wide_grid):
        key = (p.horizons, p.weights, p.rank_window, p.vol_norm, p.lag)
        if key not in signal_cache:
            signal_cache[key] = composite_scores(close, p)
        s_long, s_short = signal_cache[key]
        m = evaluate_config(close, p)
        wide_rows.append(m)
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(wide_grid)}", flush=True)

    wide_df = pd.DataFrame(wide_rows)
    wide_df.to_csv(RUN / "artifacts" / "BTCUSDT_wide_grid_10bps.csv", index=False)

    # 2) Original 648 grid at 10bps for comparison
    orig_grid = parametric_grid()
    print(f"\nOriginal grid at 10bps: {len(orig_grid)} configs")
    orig_rows = []
    signal_cache = {}
    for i, p in enumerate(orig_grid):
        key = (p.horizons, p.weights, p.rank_window, p.vol_norm, p.lag)
        if key not in signal_cache:
            signal_cache[key] = composite_scores(close, p)
        orig_rows.append(evaluate_config(close, p))
        if (i + 1) % 150 == 0:
            print(f"  {i + 1}/{len(orig_grid)}", flush=True)
    orig_df = pd.DataFrame(orig_rows)
    orig_df.to_csv(RUN / "artifacts" / "BTCUSDT_orig_grid_10bps.csv", index=False)

    # 3) Select configs for deep dive
    baseline_m = evaluate_config(close, BASELINE)
    best_is = wide_df.sort_values("is_sharpe", ascending=False).iloc[0]
    best_oos = wide_df.sort_values("oos_sharpe", ascending=False).iloc[0]
    # Best OOS among configs with <= 500 full-sample trades (low turnover)
    low_turn = wide_df[wide_df["full_trades"] <= 500]
    best_oos_low_turn = (
        low_turn.sort_values("oos_sharpe", ascending=False).iloc[0]
        if not low_turn.empty
        else best_oos
    )
    median_wide = wide_df.sort_values("is_sharpe").iloc[len(wide_df) // 2]

    candidates = {
        "baseline": BASELINE,
        "best_is_wide": row_to_params(best_is.to_dict()),
        "best_oos_wide": row_to_params(best_oos.to_dict()),
        "best_oos_low_turnover": row_to_params(best_oos_low_turn.to_dict()),
        "median_wide": row_to_params(median_wide.to_dict()),
    }

    presented: dict = {}
    for label, params in candidates.items():
        m = evaluate_config(close, params)
        trade_stats = trade_level_stats(close, params)
        presented[label] = {**m, "oos_trade_stats": trade_stats}

    # 4) Grid-level OOS statistics
    oos_positive_frac = float((wide_df["oos_sharpe"] > 0).mean())
    oos_sharpe_median = float(wide_df["oos_sharpe"].median())
    oos_sharpe_p90 = float(wide_df["oos_sharpe"].quantile(0.9))
    # Definitive verdict logic
    best_oos_sharpe = presented["best_oos_wide"]["oos_sharpe"]
    best_oos_p = presented["best_oos_wide"]["oos_trade_stats"]["p_value"]
    baseline_oos_sharpe = presented["baseline"]["oos_sharpe"]
    low_turn_oos_sharpe = presented["best_oos_low_turnover"]["oos_sharpe"]

    if best_oos_sharpe > 0.5 and best_oos_p < 0.05:
        verdict = "MODERATE_EDGE"
        verdict_detail = (
            "Top OOS config shows positive risk-adjusted returns with statistically significant "
            "per-trade edge, but selection was informed by grid search — treat as exploratory."
        )
    elif best_oos_sharpe > 0 and oos_positive_frac >= 0.4:
        verdict = "WEAK_INCONCLUSIVE"
        verdict_detail = (
            "Some parameter sets are OOS-positive, but results are fragile and likely "
            "overfit; no robust edge after costs."
        )
    else:
        verdict = "NO_EDGE"
        verdict_detail = (
            "After 0.1% round-trip costs, BTC percentile-rank momentum does not show a "
            "reliable OOS edge. IS winners do not generalize; median/baseline configs are negative OOS."
        )

    summary = {
        "symbol": SYMBOL,
        "cost_round_trip_pct": COST_PER_SIDE * 2 * 100,
        "oos_start": str(OOS_START.date()),
        "data_range": [str(close.index.min()), str(close.index.max())],
        "wide_grid_size": len(wide_grid),
        "orig_grid_size": len(orig_grid),
        "wide_grid_oos_sharpe_positive_frac": oos_positive_frac,
        "wide_grid_oos_sharpe_median": oos_sharpe_median,
        "wide_grid_oos_sharpe_p90": oos_sharpe_p90,
        "verdict": verdict,
        "verdict_detail": verdict_detail,
        "presented_configs": presented,
        "baseline_oos_sharpe": baseline_oos_sharpe,
        "best_oos_sharpe": best_oos_sharpe,
        "best_oos_low_turnover_sharpe": low_turn_oos_sharpe,
    }

    # Charts
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))

    ax = axes[0, 0]
    ax.scatter(wide_df["is_sharpe"], wide_df["oos_sharpe"], alpha=0.3, s=8)
    ax.axhline(0, color="gray", ls="--", lw=0.8)
    ax.axvline(0, color="gray", ls="--", lw=0.8)
    ax.set_xlabel("In-sample Sharpe")
    ax.set_ylabel("OOS Sharpe")
    ax.set_title("Wide grid: IS vs OOS Sharpe (10bps RT)")

    ax = axes[0, 1]
    ax.hist(wide_df["oos_sharpe"], bins=40, alpha=0.85)
    ax.axvline(0, color="red", ls="--")
    ax.set_xlabel("OOS Sharpe")
    ax.set_title(f"OOS Sharpe dist (median={oos_sharpe_median:.2f})")

    ax = axes[1, 0]
    for label in ("baseline", "best_oos_low_turnover"):
        p = candidates[label]
        s_long, s_short = composite_scores(close, p)
        rets = backtest_returns(close, s_long, s_short, p)
        eq = (1 + rets.fillna(0)).cumprod()
        ax.plot(eq.index, eq, label=label.replace("_", " "))
    ax.axvline(OOS_START, color="gray", ls=":", label="OOS start")
    ax.set_ylabel("Equity (1 = start)")
    ax.set_title("Equity curves @ 10bps RT")
    ax.legend(fontsize=8)

    ax = axes[1, 1]
    ax.scatter(wide_df["full_trades"], wide_df["oos_sharpe"], alpha=0.3, s=8, c=wide_df["qe"])
    ax.set_xlabel("Full-sample trades")
    ax.set_ylabel("OOS Sharpe")
    ax.set_title("Turnover vs OOS Sharpe (color=qe)")

    fig.suptitle(f"BTC PRM edge study — {verdict}", fontsize=12)
    fig.tight_layout()
    fig.savefig(RUN / "charts" / "BTCUSDT_edge_study_10bps.png", dpi=130)
    plt.close(fig)

    out_path = RUN / "artifacts" / "btc_edge_study.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nWrote {out_path}")
    print(f"VERDICT: {verdict}")
    print(f"  {verdict_detail}")
    return summary


if __name__ == "__main__":
  run_study()
