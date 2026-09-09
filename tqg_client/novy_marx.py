"""Novy-Marx (2015) combination-effect note for k > 1.

Selecting k in-sample winners and averaging them keeps the selected mean and
cuts variance. Legs are correlated, so the IS Sharpe lift is about
sqrt(k / (1+(k-1)ρ)), not sqrt(k). This is not a new Deflated Sharpe — DSR
does not absorb k. Cite Novy-Marx NBER 21329; Kinlay (2026) measured ρ̄ ≈ 0.41–0.47
in a price-only grammar.
"""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd


DEFAULT_RHO = 0.45
RHO_CEILING_NOTE = (
    "Combination multiplier saturates near 1.5× at ρ≈0.45 (Kinlay 2026). "
    "DSR is unadjusted for k."
)


def combination_multiplier(k: int, rho: float = DEFAULT_RHO) -> float:
    """IS Sharpe inflation factor for equal-weight selected legs, vs one leg."""
    k = max(1, int(k))
    rho = float(np.clip(rho, -0.999, 0.999))
    if k == 1:
        return 1.0
    denom = 1.0 + (k - 1) * rho
    if denom <= 0:
        return 1.0
    return float(np.sqrt(k / denom))


def estimate_rho(leg_returns: Iterable[pd.Series]) -> float | None:
    series = [pd.Series(s).dropna().astype(float) for s in leg_returns]
    series = [s for s in series if len(s) >= 8]
    if len(series) < 2:
        return None
    frame = pd.concat(series, axis=1, join="inner")
    if frame.shape[1] < 2 or len(frame) < 8:
        return None
    corr = frame.corr().to_numpy(dtype=float)
    n = corr.shape[0]
    off = corr[np.triu_indices(n, k=1)]
    off = off[np.isfinite(off)]
    if off.size == 0:
        return None
    return float(np.clip(off.mean(), -0.999, 0.999))


def novy_marx_note(
    *,
    k: int,
    rho: float | None = None,
    leg_returns: Iterable[pd.Series] | None = None,
) -> dict[str, Any]:
    k = max(1, int(k))
    rho_used = rho
    rho_source = "supplied"
    if rho_used is None and leg_returns is not None:
        rho_used = estimate_rho(leg_returns)
        rho_source = "pairwise_leg_returns"
    if rho_used is None:
        rho_used = DEFAULT_RHO
        rho_source = "kinlay_default_0.45"
    mult = combination_multiplier(k, rho_used)
    return {
        "citation": "Novy-Marx, Backtesting Strategies Based on Multiple Signals, NBER 21329 (2015)",
        "k": k,
        "rho": float(rho_used),
        "rho_source": rho_source,
        "combination_multiplier": mult,
        "warning": (
            f"k={k} selected legs inflate IS Sharpe by ~{mult:.2f}× vs a single "
            "leg at the assumed ρ. DSR does not adjust for this. Do not invent a "
            "blend-deflated Sharpe; report k next to DSR."
        ),
        "note": RHO_CEILING_NOTE,
    }
