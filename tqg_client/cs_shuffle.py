"""Cross-sectional label shuffle (zero-alpha diagnostic).

Breaks the name identity of forward returns while keeping the cross-sectional
covariance of the panel: at each date, permute columns of the return matrix.
Re-apply a fixed rank/weight rule and record the IS Sharpe distribution.

This is the TQG analogue of Kinlay's zero-alpha panels for L/S factor books.
It is a diagnostic, not an OOS forecast.
"""

from __future__ import annotations

from typing import Any, Callable

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


def _default_ls_book(signal: pd.DataFrame, fwd: pd.DataFrame) -> pd.Series:
    """Dollar-neutral rank-weighted long/short from a signal panel."""
    sig = signal.rank(axis=1, pct=True)
    weights = sig.sub(sig.mean(axis=1), axis=0)
    denom = weights.abs().sum(axis=1).replace(0.0, np.nan)
    weights = weights.div(denom, axis=0)
    aligned = weights.reindex(index=fwd.index, columns=fwd.columns).fillna(0.0)
    book = (aligned.shift(1) * fwd).sum(axis=1)
    return book


def label_shuffle_cs(
    signal: pd.DataFrame,
    forward_returns: pd.DataFrame,
    *,
    n_sims: int = 200,
    seed: int = 42,
    annualization: float = 365,
    book_builder: Callable[[pd.DataFrame, pd.DataFrame], pd.Series] | None = None,
    observed_sharpe: float | None = None,
) -> dict[str, Any]:
    """Shuffle names in ``forward_returns`` independently on each date."""
    sig = pd.DataFrame(signal).astype(float)
    fwd = pd.DataFrame(forward_returns).astype(float)
    cols = [c for c in sig.columns if c in fwd.columns]
    if len(cols) < 3 or len(fwd) < 8:
        return {"method": "cs_label_shuffle", "error": "panel_too_small"}
    sig = sig.reindex(columns=cols)
    fwd = fwd.reindex(columns=cols)
    builder = book_builder or _default_ls_book
    rng = np.random.default_rng(int(seed))
    n_sims = max(1, int(n_sims))
    names = np.array(cols)
    sharpes: list[float] = []
    values = fwd.to_numpy(dtype=float)
    index = fwd.index
    for _ in range(n_sims):
        shuffled = np.empty_like(values)
        for i in range(values.shape[0]):
            perm = rng.permutation(names.size)
            shuffled[i] = values[i, perm]
        sh_fwd = pd.DataFrame(shuffled, index=index, columns=fwd.columns)
        book = builder(sig, sh_fwd)
        sharpes.append(_sharpe(book, annualization))
    arr = np.asarray(sharpes, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {"method": "cs_label_shuffle", "error": "no_finite_sims"}
    out: dict[str, Any] = {
        "method": "cs_label_shuffle",
        "n_sims": n_sims,
        "seed": int(seed),
        "n_names": int(len(cols)),
        "n_dates": int(len(fwd)),
        "sharpe_is_mean": float(arr.mean()),
        "sharpe_is_p95": float(np.quantile(arr, 0.95)),
        "sharpe_is_p05": float(np.quantile(arr, 0.05)),
        "note": (
            "Zero-alpha diagnostic: names of forward returns shuffled per date. "
            "Not an OOS forecast."
        ),
    }
    if observed_sharpe is not None and np.isfinite(observed_sharpe):
        out["observed_sharpe"] = float(observed_sharpe)
        out["observed_percentile"] = float((arr <= float(observed_sharpe)).mean())
    return out
