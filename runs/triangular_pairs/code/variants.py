"""Extended metrics and variant runners for deep-dive research."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
RESEARCH = REPO / "research" / "triangular-pairs-trading"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from src.backtest import backtest_triangles, compute_metrics  # noqa: E402
from src.config import ANCHORS, OOS_START  # noqa: E402
from src.data import load_close_panel, log_prices, resample_to_daily  # noqa: E402
from src.discovery import discover_triangles, select_triangles  # noqa: E402
from src.layered_refresh import DEFAULT_PARAMS, walk_forward as layered_wf  # noqa: E402
from src.rolling_refresh import backtest_rolling_refresh, build_rolling_schedule  # noqa: E402
from src.triangles import Triangle  # noqa: E402

from engine import (  # noqa: E402
    ANN,
    OOS,
    discover_triangles_is,
    is_metrics,
    robust_score,
    run_backtest,
    yearly_sharpes,
)

LOAD_HOURLY = pd.Timestamp("2022-01-01", tz="UTC")


def sharpe(r: pd.Series, ann: int = ANN) -> float:
    r = r.dropna()
    if r.empty or r.std() == 0:
        return float("nan")
    return float(r.mean() / r.std() * np.sqrt(ann))


def segment_metrics(returns: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    seg = returns.loc[(returns.index >= start) & (returns.index < end)].dropna()
    if seg.empty:
        return {"Sharpe": float("nan"), "CAGR": float("nan"), "MaxDD": float("nan"), "n_days": 0}
    m = compute_metrics(seg, end)
    return {"Sharpe": m["Sharpe"], "CAGR": m["CAGR"], "MaxDD": m["MaxDD"], "n_days": m["n_days"]}


def wf_fold_score(
    returns: pd.Series,
    folds: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> dict:
    """Score walk-forward validation folds (all pre-OOS)."""
    sharpes = []
    for start, end in folds:
        m = segment_metrics(returns, start, end)
        if np.isfinite(m["Sharpe"]):
            sharpes.append(m["Sharpe"])
    if not sharpes:
        return {"wf_mean": float("nan"), "wf_std": float("nan"), "wf_min": float("nan"), "wf_score": float("-inf")}
    mean_s = float(np.mean(sharpes))
    std_s = float(np.std(sharpes))
    min_s = float(min(sharpes))
    return {
        "wf_mean": mean_s,
        "wf_std": std_s,
        "wf_min": min_s,
        "wf_score": mean_s - 0.5 * std_s + 0.2 * min_s,
        "wf_sharpes": sharpes,
    }


IS_WF_FOLDS = [
    (pd.Timestamp("2021-01-01", tz="UTC"), pd.Timestamp("2022-01-01", tz="UTC")),
    (pd.Timestamp("2022-01-01", tz="UTC"), pd.Timestamp("2023-01-01", tz="UTC")),
    (pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2024-01-01", tz="UTC")),
    (pd.Timestamp("2024-01-01", tz="UTC"), OOS),
]


def composite_robust_score(
    returns: pd.Series,
    *,
    oos_start: pd.Timestamp = OOS,
) -> dict:
    """IS metrics + yearly stability + walk-forward folds."""
    is_m = is_metrics(returns, oos_start)
    yearly = yearly_sharpes(returns, oos_start)
    rs = robust_score(is_m, yearly)
    wf = wf_fold_score(returns, IS_WF_FOLDS)
    sharpes = [v for v in yearly.values() if np.isfinite(v)]
    min_y = min(sharpes) if sharpes else float("nan")
    # Composite: robust_score + walk-forward consistency
    composite = rs * 0.55 + wf["wf_score"] * 0.35
    if np.isfinite(min_y) and min_y < 0:
        composite += min_y * 0.10
    return {
        **is_m,
        "yearly_sharpes": yearly,
        "min_yearly_sharpe": min_y,
        "robust_score": rs,
        **wf,
        "composite_score": composite,
    }


def run_daily_static(
    close_d: pd.DataFrame,
    params: dict,
    *,
    oos_start: pd.Timestamp = OOS,
) -> tuple[pd.Series, list[Triangle]]:
    tris, _ = discover_triangles_is(
        close_d,
        oos_start=oos_start,
        adf_max=params.get("adf_max", 0.05),
        n_triangles=params["n_triangles"],
        window=params.get("disc_window", params["window"]),
    )
    rets = run_backtest(
        close_d,
        tris,
        window=params["window"],
        entry_z=params["entry_z"],
        exit_z=params["exit_z"],
        weight_cap=params["weight_cap"],
    )
    return rets, tris


def run_daily_rolling(
    close_d: pd.DataFrame,
    params: dict,
) -> pd.Series:
    sched = build_rolling_schedule(
        close_d,
        ANCHORS,
        interval="1d",
        refresh_freq=params.get("refresh_freq", "180D"),
        lookback_days=params.get("lookback_days", 180),
        n_triangles=params["n_triangles"],
        adf_max=params.get("adf_max", 0.05),
        sticky=params.get("sticky", False),
        discovery_window=params.get("disc_window", params["window"]),
    )
    if not sched:
        return pd.Series(dtype=float)
    res = backtest_rolling_refresh(
        close_d,
        sched,
        interval="1d",
        entry_z=params["entry_z"],
        exit_z=params["exit_z"],
        weight_cap=params["weight_cap"],
        bt_window=params["window"],
    )
    return res.daily_returns


def run_hourly_daily_triangles(
    close_h: pd.DataFrame,
    close_d: pd.DataFrame,
    params: dict,
    *,
    oos_start: pd.Timestamp = OOS,
) -> pd.Series:
    """Daily IS discovery, hourly execution, daily-compounded returns."""
    tris, _ = discover_triangles_is(
        close_d,
        oos_start=oos_start,
        adf_max=params.get("adf_max", 0.05),
        n_triangles=params["n_triangles"],
        window=params.get("disc_window", params["window"]),
    )
    assets = sorted({a for t in tris for a in (t.target, t.leg1, t.leg2)})
    panel = close_h[[c for c in assets if c in close_h.columns]]
    bt_w = params.get("bt_window", params["window"] * 24)
    res = backtest_triangles(
        panel,
        tris,
        window=bt_w,
        min_periods=bt_w // 2,
        entry_z=params["entry_z"],
        exit_z=params["exit_z"],
        weight_cap=params["weight_cap"],
    )
    return resample_to_daily(res.daily_returns)


def run_hourly_native(
    close_h: pd.DataFrame,
    params: dict,
    *,
    oos_start: pd.Timestamp = OOS,
    disc_lookback_days: int = 365,
) -> pd.Series:
    disc_start = oos_start - pd.Timedelta(days=disc_lookback_days)
    ranked = discover_triangles(
        close_h,
        oos_start=oos_start,
        discovery_start=disc_start,
        discovery_end=oos_start,
        liquid_top_n=params.get("liquid_top_n", 30),
        window=params.get("disc_window", 720),
        min_periods=max(params.get("disc_window", 720) // 2, 360),
    )
    tris = select_triangles(ranked, params["n_triangles"], adf_max=params.get("adf_max", 0.05))
    assets = sorted({a for t in tris for a in (t.target, t.leg1, t.leg2)})
    panel = close_h[[c for c in assets if c in close_h.columns]]
    bt_w = params.get("bt_window", 1440)
    res = backtest_triangles(
        panel,
        tris,
        window=bt_w,
        min_periods=bt_w // 2,
        entry_z=params["entry_z"],
        exit_z=params["exit_z"],
        weight_cap=params["weight_cap"],
    )
    return resample_to_daily(res.daily_returns)


def run_layered_hourly(
    close_h: pd.DataFrame,
    params: dict,
    *,
    enable_refresh: bool = True,
    trade_start: pd.Timestamp | None = None,
) -> pd.Series:
    p = {**DEFAULT_PARAMS, **params}
    res = layered_wf(
        close_h,
        oos_start=OOS,
        params=p,
        enable_refresh=enable_refresh,
        trade_start=trade_start,
    )
    return res.daily_returns


def evaluate_variant(
    name: str,
    returns: pd.Series,
    params: dict,
    extra: dict | None = None,
) -> dict:
    if returns is None or returns.empty:
        return {"variant": name, "params": params, "error": "empty returns", "composite_score": float("-inf")}
    scores = composite_robust_score(returns)
    full = compute_metrics(returns.dropna(), OOS)
    row = {
        "variant": name,
        "params": params,
        **scores,
        "full_sharpe": full["Sharpe"],
        "full_max_dd": full["MaxDD"],
    }
    if extra:
        row.update(extra)
    return row
