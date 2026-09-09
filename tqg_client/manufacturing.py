"""Empirical (N, k) manufacturing surface on a zero-mean return stream.

Kinlay (2026): draw N random candidates, keep the top k by IS Sharpe, equal-weight
them into a book, record the book's IS Sharpe. True alpha is zero by construction
if ``returns`` has been demeaned (or is a shuffle / synthetic noise).

This is a diagnostic of pipeline capacity, not a forecast of live P&L.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd


def _sharpe(arr: np.ndarray, annualization: float) -> float:
    x = np.asarray(arr, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 2:
        return 0.0
    vol = float(x.std(ddof=1))
    if vol == 0.0:
        return 0.0
    return float(np.sqrt(annualization) * x.mean() / vol)


def _random_candidates(
    returns: np.ndarray,
    n_pool: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Each candidate is a random ±1 overlay on the return stream (one-day lag)."""
    n = returns.shape[0]
    signs = rng.choice(np.array([-1.0, 1.0], dtype=float), size=(n_pool, n))
    # lag: cannot trade on contemporaneous return
    lagged = np.concatenate([np.zeros((n_pool, 1)), signs[:, :-1]], axis=1)
    return lagged * returns[np.newaxis, :]


def manufacturing_surface(
    returns: pd.Series | np.ndarray,
    *,
    n_values: Sequence[int] | None = None,
    k_values: Sequence[int] | None = None,
    n_pool: int = 400,
    seed: int = 42,
    annualization: float = 365,
    demean: bool = True,
) -> dict[str, Any]:
    r = pd.Series(returns).dropna().astype(float)
    if demean:
        r = r - r.mean()
    values = r.to_numpy(dtype=float)
    if values.size < 16:
        return {"error": "too_few_returns", "n_obs": int(values.size)}

    n_values = list(n_values or (25, 50, 100, 150, 200, 300, 400))
    k_values = list(k_values or (1, 3, 6, 12))
    n_pool = max(int(n_pool), max(n_values))
    rng = np.random.default_rng(int(seed))
    pnl = _random_candidates(values, n_pool, rng)
    candidate_sr = np.array([_sharpe(pnl[i], annualization) for i in range(n_pool)])

    cells: list[dict[str, Any]] = []
    lookup: dict[str, float] = {}
    for n in n_values:
        n = min(int(n), n_pool)
        order = np.argsort(candidate_sr[:n])[::-1]
        for k in k_values:
            k = max(1, min(int(k), n))
            top = order[:k]
            book = pnl[top].mean(axis=0)
            sr = _sharpe(book, annualization)
            cells.append({"n_trials": n, "n_legs": k, "sharpe_is": sr})
            lookup[f"{n}:{k}"] = sr

    return {
        "method": "top_k_of_n_random_sign",
        "seed": int(seed),
        "n_pool": n_pool,
        "n_obs": int(values.size),
        "demeaned": bool(demean),
        "annualization": float(annualization),
        "cells": cells,
        "lookup": lookup,
        "note": (
            "Manufacturing capacity: IS Sharpe of top-k-of-N random books on a "
            "zero-mean stream. Not an OOS forecast. Kinlay (2026)."
        ),
    }


def lookup_cell(surface: dict[str, Any], n_trials: int, n_legs: int) -> float | None:
    lookup = surface.get("lookup") or {}
    key = f"{int(n_trials)}:{int(n_legs)}"
    if key in lookup:
        return float(lookup[key])
    cells = surface.get("cells") or []
    if not cells:
        return None
    best = None
    best_dist = None
    for cell in cells:
        dist = abs(int(cell["n_trials"]) - int(n_trials)) + abs(int(cell["n_legs"]) - int(n_legs))
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best = cell
    if best is None:
        return None
    return float(best["sharpe_is"])
