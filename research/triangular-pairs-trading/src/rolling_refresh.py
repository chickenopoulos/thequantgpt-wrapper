"""Rolling triangle refresh with a restricted liquid universe."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import BacktestResult, backtest_triangles, compute_metrics
from .config import ANCHORS, profile
from .data import liquid_universe, log_prices
from .triangles import Triangle, enumerate_triangles, score_triangle_in_sample


def rank_triangles_on_window(
    log_close: pd.DataFrame,
    close: pd.DataFrame,
    anchors: tuple[str, ...],
    *,
    window: int,
    min_periods: int,
    adf_max: float,
    top_n: int,
    liquid_top_n: int,
    half_life_cap: float = 60.0,
    half_life_norm: float = 120.0,
) -> pd.DataFrame:
    """Score triangles using only data in `log_close` (caller supplies the window)."""
    liquid = liquid_universe(close, liquid_top_n)
    panel = log_close[liquid]
    candidates = enumerate_triangles(liquid, anchors)
    rows = []
    pseudo_oos = log_close.index[-1] + pd.Timedelta(seconds=1)
    for tri in candidates:
        row = score_triangle_in_sample(
            panel,
            tri,
            oos_start=pseudo_oos,
            window=window,
            min_periods=min_periods,
            half_life_cap=half_life_cap,
            half_life_norm=half_life_norm,
        )
        if row["adf_p"] < adf_max and np.isfinite(row["score"]):
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("score", ascending=False).head(top_n)


def build_rolling_schedule(
    close: pd.DataFrame,
    anchors: tuple[str, ...],
    *,
    interval: str = "1d",
    refresh_freq: str | None = None,
    lookback_days: int | None = None,
    n_triangles: int = 10,
    adf_max: float = 0.05,
    sticky: bool = True,
    discovery_window: int | None = None,
    discovery_min_periods: int | None = None,
    half_life_cap: float | None = None,
    half_life_norm: float | None = None,
) -> list[dict]:
    """Build refresh schedule using trailing lookback only (no future data)."""
    prof = profile(interval)
    window = discovery_window if discovery_window is not None else prof["window"]
    min_periods = discovery_min_periods if discovery_min_periods is not None else prof["min_periods"]
    liquid_top_n = prof["liquid_top_n"]
    if half_life_cap is None:
        half_life_cap = 60 * 24 if interval == "1h" else 60.0
    if half_life_norm is None:
        half_life_norm = 120 * 24 if interval == "1h" else 120.0
    if refresh_freq is None:
        refresh_freq = prof["refresh_freq"]
    if lookback_days is None:
        lookback_days = prof["lookback_days"]

    lookback = pd.Timedelta(days=lookback_days)
    warmup_bars = prof["min_history"]
    if len(close) <= warmup_bars:
        return []

    rebalance_dates = pd.date_range(
        close.index[warmup_bars],
        close.index[-1],
        freq=refresh_freq,
        tz="UTC",
    )

    schedule: list[dict] = []
    prev_keys: set[str] = set()

    for reb_date in rebalance_dates:
        hist_end = reb_date - pd.Timedelta(hours=1 if interval == "1h" else 24)
        hist_start = hist_end - lookback
        hist = close.loc[(close.index >= hist_start) & (close.index <= hist_end)]
        if len(hist) < min_periods + 30:
            continue

        ranked = rank_triangles_on_window(
            log_prices(hist),
            hist,
            anchors,
            window=window,
            min_periods=min_periods,
            adf_max=adf_max,
            top_n=n_triangles * 2 if sticky else n_triangles,
            liquid_top_n=liquid_top_n,
            half_life_cap=half_life_cap,
            half_life_norm=half_life_norm,
        )
        if ranked.empty:
            continue

        selected: list[Triangle] = []
        if sticky and prev_keys:
            for row in ranked.itertuples():
                if row.triangle in prev_keys:
                    selected.append(Triangle(row.target, row.leg1, row.leg2))
                if len(selected) >= n_triangles:
                    break

        for row in ranked.itertuples():
            if len(selected) >= n_triangles:
                break
            tri = Triangle(row.target, row.leg1, row.leg2)
            if tri.key not in {t.key for t in selected}:
                selected.append(tri)

        if not selected:
            continue

        prev_keys = {t.key for t in selected}
        schedule.append({"start": reb_date, "triangles": selected})

    return schedule


def backtest_rolling_refresh(
    close: pd.DataFrame,
    schedule: list[dict],
    *,
    interval: str = "1d",
    entry_z: float = 3.0,
    exit_z: float = 0.75,
    weight_cap: float = 0.20,
    max_gross_exposure: float = 1.0,
    bt_window: int | None = None,
    bt_min_periods: int | None = None,
) -> BacktestResult:
    """Stitch walk-forward segments from a rolling refresh schedule."""
    if not schedule:
        raise ValueError("empty schedule")

    prof = profile(interval)
    window = bt_window if bt_window is not None else prof["window"]
    min_periods = bt_min_periods if bt_min_periods is not None else prof["min_periods"]

    segments: list[pd.Series] = []
    all_pos: list[pd.DataFrame] = []

    for i, entry in enumerate(schedule):
        start = entry["start"]
        end = schedule[i + 1]["start"] if i + 1 < len(schedule) else close.index[-1] + pd.Timedelta(hours=1)
        mask = (close.index >= start) & (close.index < end)
        if not mask.any():
            continue

        tris = entry["triangles"]
        assets = sorted({a for t in tris for a in (t.target, t.leg1, t.leg2)})
        seg_idx = close.index[mask]
        loc0 = close.index.get_loc(seg_idx[0])
        warmup_i = max(0, loc0 - window - 5)
        hist = close.iloc[warmup_i : close.index.get_loc(seg_idx[-1]) + 1][assets]

        res = backtest_triangles(
            hist,
            tris,
            window=window,
            min_periods=min_periods,
            entry_z=entry_z,
            exit_z=exit_z,
            weight_cap=weight_cap,
            max_gross_exposure=max_gross_exposure,
        )
        segments.append(res.daily_returns.loc[seg_idx])
        all_pos.append(res.positions.loc[seg_idx])

    port_ret = pd.concat(segments).sort_index()
    port_ret = port_ret[~port_ret.index.duplicated(keep="last")]

    positions = pd.concat(all_pos).sort_index() if all_pos else pd.DataFrame()
    if not positions.empty:
        positions = positions[~positions.index.duplicated(keep="last")]

    equity = (1 + port_ret).cumprod()
    return BacktestResult(
        daily_returns=port_ret,
        equity=equity,
        positions=positions,
        metrics={},
    )


def save_schedule(schedule: list[dict], path: Path) -> None:
    payload = [
        {
            "start": entry["start"].isoformat(),
            "triangles": [
                {"target": t.target, "leg1": t.leg1, "leg2": t.leg2, "key": t.key}
                for t in entry["triangles"]
            ],
        }
        for entry in schedule
    ]
    path.write_text(json.dumps(payload, indent=2))
