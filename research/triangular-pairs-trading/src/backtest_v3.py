"""Walk-forward triangle selection and drawdown-aware portfolio scaling."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import BacktestResult, backtest_triangles, compute_metrics
from .data import log_prices
from .triangles import Triangle, enumerate_triangles, score_triangle_in_sample


def walk_forward_triangles(
    close: pd.DataFrame,
    anchors: tuple[str, ...],
    *,
    oos_start: pd.Timestamp,
    rebalance_freq: str = "365D",
    n_triangles: int = 10,
    adf_max: float = 0.05,
    window: int = 120,
) -> pd.DataFrame:
    """Return date -> list of active triangles selected using only prior data."""
    counts = close.notna().sum().sort_values(ascending=False)
    liquid = counts.head(80).index.tolist()
    for a in anchors:
        if a in close.columns and a not in liquid:
            liquid.append(a)

    log_panel = log_prices(close[liquid])
    candidates = enumerate_triangles(liquid, anchors)

    start_idx = 500
    rebalance_dates = pd.date_range(
        close.index[start_idx],
        close.index[-1],
        freq=rebalance_freq,
        tz="UTC",
    )
    schedule: list[dict] = []

    for reb_date in rebalance_dates:
        hist_end = reb_date - pd.Timedelta(days=1)
        if hist_end < close.index[start_idx]:
            continue
        rows = []
        for tri in candidates:
            row = score_triangle_in_sample(
                log_panel.loc[:hist_end],
                tri,
                oos_start=hist_end + pd.Timedelta(days=1),
                window=window,
            )
            if row["adf_p"] < adf_max and np.isfinite(row["score"]):
                rows.append(row)
        if not rows:
            continue
        ranked = pd.DataFrame(rows).sort_values("score", ascending=False).head(n_triangles)
        schedule.append(
            {
                "start": reb_date,
                "triangles": [
                    Triangle(target=r.target, leg1=r.leg1, leg2=r.leg2)
                    for r in ranked.itertuples()
                ],
            }
        )

    return schedule


def apply_drawdown_scale(returns: pd.Series, *, dd_start: float = -0.10, dd_floor: float = -0.25) -> pd.Series:
    """Reduce exposure as drawdown deepens (applied with 1-bar lag)."""
    equity = (1 + returns).cumprod()
    peak = equity.cummax()
    dd = equity / peak - 1
    scale = pd.Series(1.0, index=returns.index)
    # Linear ramp: 1 at dd_start, 0.25 at dd_floor.
    mask = dd < dd_start
    scale[mask] = np.clip(
        1.0 + (dd[mask] - dd_start) / (dd_floor - dd_start) * 0.75,
        0.25,
        1.0,
    )
    return scale.shift(1).fillna(1.0)


def backtest_walk_forward(
    close: pd.DataFrame,
    schedule: list[dict],
    *,
    window: int = 120,
    entry_z: float = 2.5,
    exit_z: float = 0.5,
    weight_cap: float = 0.20,
    max_gross: float = 0.85,
    use_dd_scale: bool = True,
) -> BacktestResult:
    """Stitch together walk-forward triangle selections."""
    if not schedule:
        raise ValueError("empty walk-forward schedule")

    segments: list[pd.Series] = []
    all_positions: list[pd.DataFrame] = []

    for i, entry in enumerate(schedule):
        start = entry["start"]
        end = schedule[i + 1]["start"] if i + 1 < len(schedule) else close.index[-1] + pd.Timedelta(days=1)
        mask = (close.index >= start) & (close.index < end)
        if not mask.any():
            continue
        tris = entry["triangles"]
        assets = sorted({a for t in tris for a in (t.target, t.leg1, t.leg2)})
        seg_close = close.loc[mask, assets]
        if len(seg_close) < 30:
            continue
        # Include warmup history before segment.
        warmup_start = close.index[max(0, close.index.get_loc(seg_close.index[0]) - window - 5)]
        hist = close.loc[warmup_start:seg_close.index[-1], assets]
        res = backtest_triangles(
            hist,
            tris,
            window=window,
            entry_z=entry_z,
            exit_z=exit_z,
            weight_cap=weight_cap,
        )
        seg_ret = res.daily_returns.loc[seg_close.index]
        seg_pos = res.positions.loc[seg_close.index]
        segments.append(seg_ret)
        all_positions.append(seg_pos)

    port_ret = pd.concat(segments).sort_index()
    port_ret = port_ret[~port_ret.index.duplicated(keep="last")]

    if use_dd_scale:
        dd_scale = apply_drawdown_scale(port_ret)
        # Re-scale returns approximately (positions not fully re-simulated).
        port_ret = port_ret * dd_scale

    # Gross exposure cap post-hoc approximation.
    if max_gross < 1.0:
        positions = pd.concat(all_positions).sort_index()
        positions = positions[~positions.index.duplicated(keep="last")]
        gross = positions.abs().sum(axis=1).reindex(port_ret.index).fillna(0)
        over = gross > max_gross
        scale = (max_gross / gross).clip(upper=1.0)
        port_ret[over] = port_ret[over] * scale[over]

    equity = (1 + port_ret).cumprod()
    return BacktestResult(
        daily_returns=port_ret,
        equity=equity,
        positions=pd.DataFrame(),
        metrics={},
    )
