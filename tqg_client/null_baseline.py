"""Null / random-entry baseline for a strategy's in-sample window.

Bias-matched occupancy: same number of in-market bars and the same long/short
mix as the observed position (when available). Falls back to a permutation of
strategy returns when only the return stream exists.

The null mean is a measure of manufactured IS Sharpe. Do not subtract it from
OOS Sharpe and call the remainder a forecast.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _sharpe(returns: pd.Series, annualization: float) -> float:
    r = pd.Series(returns).dropna().astype(float)
    if len(r) < 2:
        return 0.0
    vol = float(r.std(ddof=1))
    if vol == 0.0 or not np.isfinite(vol):
        return 0.0
    return float(np.sqrt(annualization) * r.mean() / vol)


def _position_from_returns(strategy_returns: pd.Series, asset_returns: pd.Series | None) -> pd.Series | None:
    if asset_returns is None:
        return None
    sr = pd.Series(strategy_returns).astype(float)
    ar = pd.Series(asset_returns).astype(float)
    idx = sr.index.intersection(ar.index)
    if len(idx) < 2:
        return None
    ar = ar.reindex(idx)
    sr = sr.reindex(idx)
    with np.errstate(divide="ignore", invalid="ignore"):
        pos = sr / ar.replace(0.0, np.nan)
    pos = pos.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    pos = pos.clip(-1.0, 1.0)
    if (pos.abs() < 1e-12).all():
        return None
    return pos


def random_entry_matched_hold(
    *,
    asset_returns: pd.Series,
    position: pd.Series | None = None,
    strategy_returns: pd.Series | None = None,
    n_sims: int = 200,
    seed: int = 42,
    annualization: float = 365,
    strategy_sharpe_is: float | None = None,
) -> dict[str, Any]:
    """Simulate random entries with matched occupancy; return null Sharpe stats."""
    ar = pd.Series(asset_returns).dropna().astype(float)
    if ar.empty:
        return {"method": "random_entry_matched_hold", "error": "empty_asset_returns"}

    pos = position
    if pos is not None:
        pos = pd.Series(pos).reindex(ar.index).fillna(0.0).astype(float)
    elif strategy_returns is not None:
        pos = _position_from_returns(strategy_returns, ar)

    rng = np.random.default_rng(int(seed))
    n_sims = max(1, int(n_sims))
    sharpes: list[float] = []

    if pos is not None and (pos.abs() > 1e-12).any():
        method = "random_entry_matched_hold"
        occ = pos.abs() > 1e-12
        n_on = int(occ.sum())
        signs = np.sign(pos.to_numpy())
        signs = signs[np.abs(signs) > 1e-12]
        if signs.size == 0:
            signs = np.array([1.0])
        n_on = min(n_on, len(ar))
        values = ar.to_numpy(dtype=float)
        for _ in range(n_sims):
            chosen = rng.choice(len(ar), size=n_on, replace=False)
            sim_pos = np.zeros(len(ar), dtype=float)
            sim_pos[chosen] = rng.choice(signs, size=n_on, replace=True)
            sim_r = sim_pos * values
            sharpes.append(_sharpe(pd.Series(sim_r, index=ar.index), annualization))
    elif strategy_returns is not None:
        method = "return_permutation"
        sr = pd.Series(strategy_returns).reindex(ar.index).fillna(0.0).astype(float)
        values = sr.to_numpy(dtype=float)
        for _ in range(n_sims):
            shuffled = rng.permutation(values)
            sharpes.append(_sharpe(pd.Series(shuffled, index=sr.index), annualization))
    else:
        method = "random_sign"
        values = ar.to_numpy(dtype=float)
        for _ in range(n_sims):
            signs = rng.choice(np.array([-1.0, 0.0, 1.0]), size=len(ar), p=[0.25, 0.5, 0.25])
            sharpes.append(_sharpe(pd.Series(signs * values, index=ar.index), annualization))

    arr = np.asarray(sharpes, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {"method": method, "error": "no_finite_sims", "n_sims": n_sims, "seed": seed}

    mean = float(arr.mean())
    p95 = float(np.quantile(arr, 0.95))
    out: dict[str, Any] = {
        "method": method,
        "n_sims": n_sims,
        "seed": int(seed),
        "sharpe_is_mean": mean,
        "sharpe_is_p95": p95,
        "sharpe_is_p05": float(np.quantile(arr, 0.05)),
        "note": (
            "Null IS Sharpe distribution. Do not subtract this from OOS Sharpe "
            "and treat the remainder as a forecast."
        ),
    }
    if strategy_sharpe_is is not None and np.isfinite(strategy_sharpe_is):
        out["strategy_is_sharpe"] = float(strategy_sharpe_is)
        out["strategy_is_percentile"] = float((arr <= float(strategy_sharpe_is)).mean())
    return out
