"""Layered triangle refresh: filtered discovery, trigger monitors, partial updates."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .backtest import BacktestResult, backtest_triangles, compute_metrics
from .config import ANCHORS, profile
from .data import resample_to_daily
from .discovery import discover_triangles, select_triangles
from .triangles import Triangle

# Targets excluded from discovery (peg / stable mean-reversion traps).
STABLECOIN_TARGETS = frozenset(
    {"USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "BUSDUSDT", "USDPUSDT", "DAIUSDT", "EURUSDT"}
)

DEFAULT_PARAMS = {
    "disc_lookback_days": 365,
    "disc_window": 720,
    "bt_window": 1440,
    "entry_z": 2.5,
    "exit_z": 0.75,
    "weight_cap": 0.15,
    "n_triangles": 10,
    "adf_max": 0.05,
    "liquid_top_n": 30,
    "min_resid_std": 0.0008,
    "max_per_target": 3,
    "top_keep": 20,
    "top_drop": 30,
    "sharpe_window_days": 90,
    "sharpe_streak_days": 30,
    "calendar_months": 12,
    "triggers_required": 2,
    "check_freq": "7D",
}


@dataclass
class RefreshEvent:
    date: pd.Timestamp
    triggers: dict[str, bool]
    n_kept: int
    n_added: int
    n_dropped: int
    triangles_before: list[str]
    triangles_after: list[str]


@dataclass
class LayeredWalkForwardResult:
    daily_returns: pd.Series
    hourly_returns: pd.Series
    equity: pd.Series
    schedule: list[dict]
    refresh_events: list[RefreshEvent] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def _sharpe(r: pd.Series, ann: int = 365) -> float:
    r = r.dropna()
    if r.empty or r.std() == 0:
        return float("nan")
    return float(r.mean() / r.std() * np.sqrt(ann))


def apply_discovery_filters(
    ranked: pd.DataFrame,
    *,
    min_resid_std: float,
    max_per_target: int,
    n_triangles: int,
    adf_max: float,
) -> list[Triangle]:
    """Apply hard filters and concentration cap; return up to n_triangles."""
    if ranked.empty:
        return []

    filt = ranked[
        (~ranked["target"].isin(STABLECOIN_TARGETS))
        & (ranked["adf_p"] < adf_max)
        & (ranked["resid_std"] >= min_resid_std)
        & np.isfinite(ranked["score"])
    ].copy()

    selected: list[Triangle] = []
    for row in filt.itertuples():
        if len(selected) >= n_triangles:
            break
        n_same = sum(1 for t in selected if t.target == row.target)
        if n_same >= max_per_target:
            continue
        selected.append(Triangle(row.target, row.leg1, row.leg2))
    return selected


def filtered_discovery(
    close: pd.DataFrame,
    as_of: pd.Timestamp,
    params: dict,
) -> pd.DataFrame:
    """Rank triangles on trailing lookback ending at as_of (no future data)."""
    lookback = pd.Timedelta(days=params["disc_lookback_days"])
    disc_end = as_of
    disc_start = disc_end - lookback
    ranked = discover_triangles(
        close,
        oos_start=disc_end + pd.Timedelta(hours=1),
        discovery_start=disc_start,
        discovery_end=disc_end,
        liquid_top_n=params["liquid_top_n"],
        window=params["disc_window"],
        min_periods=max(params["disc_window"] // 2, 360),
        half_life_cap=60 * 24,
        half_life_norm=120 * 24,
        progress_every=0,
    )
    return ranked


def initial_triangles(close: pd.DataFrame, deploy: pd.Timestamp, params: dict) -> list[Triangle]:
    ranked = filtered_discovery(close, deploy, params)
    return apply_discovery_filters(
        ranked,
        min_resid_std=params["min_resid_std"],
        max_per_target=params["max_per_target"],
        n_triangles=params["n_triangles"],
        adf_max=params["adf_max"],
    )


def partial_refresh(
    current: list[Triangle],
    ranked: pd.DataFrame,
    params: dict,
) -> tuple[list[Triangle], int, int, int]:
    """Keep top-20 incumbents; drop outside top-30; fill from filtered ranked list."""
    top_keep = params["top_keep"]
    top_drop = params["top_drop"]
    n_tri = params["n_triangles"]
    adf_max = params["adf_max"]

    filt = ranked[
        (~ranked["target"].isin(STABLECOIN_TARGETS))
        & (ranked["adf_p"] < adf_max)
        & (ranked["resid_std"] >= params["min_resid_std"])
        & np.isfinite(ranked["score"])
    ]

    top20 = set(filt.head(top_keep)["triangle"])
    current_keys = {t.key for t in current}

    kept = [t for t in current if t.key in top20]
    n_dropped = len(current) - len(kept)

    selected = list(kept)
    selected_keys = {t.key for t in selected}
    n_added = 0

    for row in filt.itertuples():
        if len(selected) >= n_tri:
            break
        tri = Triangle(row.target, row.leg1, row.leg2)
        if tri.key in selected_keys:
            continue
        n_same = sum(1 for t in selected if t.target == tri.target)
        if n_same >= params["max_per_target"]:
            continue
        selected.append(tri)
        selected_keys.add(tri.key)
        if tri.key not in current_keys:
            n_added += 1

    return selected[:n_tri], len(kept), n_added, n_dropped


def sharpe_decay_trigger(
    daily_returns: pd.Series,
    as_of: pd.Timestamp,
    *,
    window_days: int = 90,
    streak_days: int = 30,
) -> bool:
    """True if trailing window_days Sharpe < 0 for streak_days consecutive days."""
    r = daily_returns[daily_returns.index <= as_of].dropna()
    need = window_days + streak_days
    if len(r) < need:
        return False
    for i in range(streak_days):
        dt = r.index[-(i + 1)]
        window = r.loc[:dt].tail(window_days)
        if len(window) < window_days or _sharpe(window) >= 0:
            return False
    return True


def ranking_drift_trigger(
    current: list[Triangle],
    ranked: pd.DataFrame,
    *,
    min_in_top20: int = 5,
    top_keep: int = 20,
) -> bool:
    """True if fewer than min_in_top20 current triangles still rank in top_keep."""
    top20 = set(ranked.head(top_keep)["triangle"])
    n = sum(1 for t in current if t.key in top20)
    return n < min_in_top20


def calendar_trigger(
    as_of: pd.Timestamp,
    last_refresh: pd.Timestamp,
    *,
    months: int = 12,
) -> bool:
    return as_of >= last_refresh + pd.DateOffset(months=months)


def evaluate_triggers(
    daily_returns: pd.Series,
    current: list[Triangle],
    ranked: pd.DataFrame,
    as_of: pd.Timestamp,
    last_refresh: pd.Timestamp,
    params: dict,
) -> dict[str, bool]:
    return {
        "sharpe_decay": sharpe_decay_trigger(
            daily_returns,
            as_of,
            window_days=params["sharpe_window_days"],
            streak_days=params["sharpe_streak_days"],
        ),
        "ranking_drift": ranking_drift_trigger(
            current,
            ranked,
            min_in_top20=5,
            top_keep=params["top_keep"],
        ),
        "calendar": calendar_trigger(
            as_of,
            last_refresh,
            months=params["calendar_months"],
        ),
    }


def deploy_date(close: pd.DataFrame, interval: str = "1h", lookback_days: int = 365) -> pd.Timestamp:
    """First bar with enough history for discovery lookback + backtest warmup."""
    prof = profile(interval)
    min_bars = prof["min_history"] + lookback_days * (24 if interval == "1h" else 1)
    if len(close) <= min_bars:
        raise ValueError("insufficient history for walk-forward deploy")
    return close.index[min_bars]


def _backtest_segment(
    close: pd.DataFrame,
    triangles: list[Triangle],
    start: pd.Timestamp,
    end: pd.Timestamp,
    params: dict,
) -> pd.Series:
    if not triangles:
        return pd.Series(dtype=float)

    mask = (close.index >= start) & (close.index < end)
    if not mask.any():
        return pd.Series(dtype=float)

    seg_idx = close.index[mask]
    assets = sorted({a for t in triangles for a in (t.target, t.leg1, t.leg2)})
    loc0 = close.index.get_loc(seg_idx[0])
    warmup = params["bt_window"] + 5
    warmup_i = max(0, loc0 - warmup)
    hist = close.iloc[warmup_i : close.index.get_loc(seg_idx[-1]) + 1][assets]

    res = backtest_triangles(
        hist,
        triangles,
        window=params["bt_window"],
        min_periods=params["bt_window"] // 2,
        entry_z=params["entry_z"],
        exit_z=params["exit_z"],
        weight_cap=params["weight_cap"],
    )
    return res.daily_returns.loc[seg_idx]


def walk_forward(
    close: pd.DataFrame,
    *,
    oos_start: pd.Timestamp,
    params: dict | None = None,
    enable_refresh: bool = True,
    fixed_triangles: list[Triangle] | None = None,
    trade_start: pd.Timestamp | None = None,
) -> LayeredWalkForwardResult:
    """Walk-forward backtest with optional layered refresh triggers."""
    p = {**DEFAULT_PARAMS, **(params or {})}
    deploy = trade_start or deploy_date(close, "1h", p["disc_lookback_days"])

    if fixed_triangles is not None:
        triangles = fixed_triangles
    else:
        triangles = initial_triangles(close, deploy, p)
        if not triangles:
            raise ValueError(f"no triangles at deploy {deploy}")

    schedule: list[dict] = [{"start": deploy, "triangles": triangles}]
    events: list[RefreshEvent] = []
    segments: list[pd.Series] = []

    last_refresh = deploy
    seg_start = deploy
    end = close.index[-1] + pd.Timedelta(hours=1)
    checkpoints = pd.date_range(deploy, close.index[-1], freq=p["check_freq"], tz="UTC")

    if not enable_refresh:
        hourly_returns = _backtest_segment(close, triangles, deploy, end, p)
    else:
        for check_dt in checkpoints[1:]:
            seg_ret = _backtest_segment(close, triangles, seg_start, check_dt, p)
            if not seg_ret.empty:
                segments.append(seg_ret)

            hourly_so_far = pd.concat(segments).sort_index()
            hourly_so_far = hourly_so_far[~hourly_so_far.index.duplicated(keep="last")]
            daily_so_far = resample_to_daily(hourly_so_far)

            cheap_triggers = {
                "sharpe_decay": sharpe_decay_trigger(
                    daily_so_far,
                    check_dt,
                    window_days=p["sharpe_window_days"],
                    streak_days=p["sharpe_streak_days"],
                ),
                "calendar": calendar_trigger(check_dt, last_refresh, months=p["calendar_months"]),
            }
            if cheap_triggers["sharpe_decay"] or cheap_triggers["calendar"]:
                ranked = filtered_discovery(close, check_dt, p)
                triggers = {
                    **cheap_triggers,
                    "ranking_drift": ranking_drift_trigger(
                        triangles, ranked, min_in_top20=5, top_keep=p["top_keep"]
                    ),
                }
            else:
                triggers = {**cheap_triggers, "ranking_drift": False}

            if sum(triggers.values()) >= p["triggers_required"]:
                new_tris, n_kept, n_added, n_dropped = partial_refresh(triangles, ranked, p)
                if new_tris and {t.key for t in new_tris} != {t.key for t in triangles}:
                    events.append(
                        RefreshEvent(
                            date=check_dt,
                            triggers=triggers,
                            n_kept=n_kept,
                            n_added=n_added,
                            n_dropped=n_dropped,
                            triangles_before=[t.key for t in triangles],
                            triangles_after=[t.key for t in new_tris],
                        )
                    )
                    triangles = new_tris
                    schedule.append({"start": check_dt, "triangles": triangles})
                    last_refresh = check_dt
                    seg_start = check_dt

        tail = _backtest_segment(close, triangles, seg_start, end, p)
        if not tail.empty:
            segments.append(tail)
        hourly_returns = pd.concat(segments).sort_index()
        hourly_returns = hourly_returns[~hourly_returns.index.duplicated(keep="last")]

    daily_returns = resample_to_daily(hourly_returns)
    equity = (1 + hourly_returns).cumprod()

    return LayeredWalkForwardResult(
        daily_returns=daily_returns,
        hourly_returns=hourly_returns,
        equity=equity,
        schedule=schedule,
        refresh_events=events,
        metrics=compute_metrics(daily_returns, oos_start),
    )
