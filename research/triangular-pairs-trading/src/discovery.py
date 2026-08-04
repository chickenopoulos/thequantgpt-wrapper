"""Batch triangle discovery helpers."""

from __future__ import annotations

import pandas as pd

from .config import ANCHORS
from .data import liquid_universe, log_prices
from .triangles import Triangle, enumerate_triangles, score_triangle_in_sample


def discover_triangles(
    close: pd.DataFrame,
    *,
    oos_start: pd.Timestamp,
    discovery_start: pd.Timestamp | None = None,
    discovery_end: pd.Timestamp | None = None,
    liquid_top_n: int = 30,
    window: int = 720,
    min_periods: int | None = None,
    half_life_cap: float = 60.0,
    half_life_norm: float = 120.0,
    progress_every: int = 50,
) -> pd.DataFrame:
    """Rank triangles on hourly or daily close panel (in-sample only)."""
    if discovery_end is None:
        discovery_end = oos_start
    if discovery_start is None:
        discovery_start = close.index[0]

    liquid = liquid_universe(close, liquid_top_n)
    panel = close[liquid]
    log_panel = log_prices(panel)

    is_mask = (log_panel.index >= discovery_start) & (log_panel.index < discovery_end)
    log_is = log_panel.loc[is_mask]
    if min_periods is None:
        min_periods = max(window // 2, 90)

    candidates = enumerate_triangles(liquid, ANCHORS)
    rows = []
    for i, tri in enumerate(candidates):
        if progress_every and i % progress_every == 0:
            print(f"    scoring {i}/{len(candidates)}")
        rows.append(
            score_triangle_in_sample(
                log_is,
                tri,
                oos_start=discovery_end,
                window=window,
                min_periods=min_periods,
                half_life_cap=half_life_cap,
                half_life_norm=half_life_norm,
            )
        )
    return pd.DataFrame(rows).sort_values("score", ascending=False)


def select_triangles(ranked: pd.DataFrame, n: int, adf_max: float = 0.05) -> list[Triangle]:
    filt = ranked[ranked["adf_p"] < adf_max].head(n)
    return [Triangle(r.target, r.leg1, r.leg2) for r in filt.itertuples()]


def triangles_to_frame(triangles: list[Triangle]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"target": t.target, "leg1": t.leg1, "leg2": t.leg2, "key": t.key} for t in triangles]
    )
