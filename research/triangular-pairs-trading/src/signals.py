"""Signal generation for triangular mean-reversion."""

from __future__ import annotations

import pandas as pd


def zscore_positions(
    z: pd.Series,
    *,
    entry: float = 2.0,
    exit_: float = 0.5,
    max_pos: float = 1.0,
) -> pd.Series:
    """Stateful mean-reversion position in [-max_pos, max_pos] on residual z-score."""
    pos = 0.0
    out = []
    for val in z:
        if pd.isna(val):
            out.append(pos)
            continue
        if pos == 0.0:
            if val >= entry:
                pos = -max_pos
            elif val <= -entry:
                pos = max_pos
        elif pos > 0 and val >= -exit_:
            pos = 0.0
        elif pos < 0 and val <= exit_:
            pos = 0.0
        out.append(pos)
    return pd.Series(out, index=z.index, name="position")


def triangle_weights(
    position: float,
    beta1: float,
    beta2: float,
) -> tuple[float, float, float]:
    """Dollar-neutral-ish weights: +1 target, -beta1 leg1, -beta2 leg2 scaled by position."""
    if position == 0 or pd.isna(beta1) or pd.isna(beta2):
        return 0.0, 0.0, 0.0
    # Normalize gross exposure to 1.
    gross = 1.0 + abs(beta1) + abs(beta2)
    w_target = position / gross
    w_leg1 = -position * beta1 / gross
    w_leg2 = -position * beta2 / gross
    return w_target, w_leg1, w_leg2
