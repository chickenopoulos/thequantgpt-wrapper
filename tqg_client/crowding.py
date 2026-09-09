"""Crowding: pairwise IS-return correlation of same-symbol lab runs.

Kinlay (Aug 2026) measured 0.62 correlation across independent agent books on
the same universe. That is a different number from N; it is a portfolio-risk
exposure that does not appear in a single-run Sharpe.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import load_config, resolve_path


def _load_returns(run_root: Path) -> pd.Series | None:
    from .selection import load_is_returns

    return load_is_returns(run_root)


def crowding_report(
    *,
    symbol: str,
    runs_dir: Path | None = None,
    min_overlap: int = 40,
    limit: int = 24,
) -> dict[str, Any]:
    """Pairwise correlation of IS return streams for ``symbol``."""
    from .lab_index import search_runs  # local import: index may import selection

    cfg = load_config()
    base = runs_dir or resolve_path(cfg, "runs_dir")
    cards = search_runs(symbol=symbol, limit=limit, cfg=cfg, runs_dir=base)
    series: dict[str, pd.Series] = {}
    for card in cards:
        rid = str(card.get("run_id") or "")
        if not rid:
            continue
        s = _load_returns(base / rid)
        if s is None or s.dropna().shape[0] < min_overlap:
            continue
        series[rid] = s.dropna().astype(float)
    ids = sorted(series)
    if len(ids) < 2:
        return {
            "symbol": symbol,
            "n_runs_with_returns": len(ids),
            "mean_pairwise_corr": None,
            "pairs": [],
            "note": "Need at least two runs with artifacts/returns_is.json.",
        }
    pairs: list[dict[str, Any]] = []
    corrs: list[float] = []
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            joined = pd.concat([series[a], series[b]], axis=1, join="inner").dropna()
            if len(joined) < min_overlap:
                continue
            corr = float(joined.iloc[:, 0].corr(joined.iloc[:, 1]))
            if not np.isfinite(corr):
                continue
            corrs.append(corr)
            pairs.append({"a": a, "b": b, "corr": corr, "n_overlap": int(len(joined))})
    mean = float(np.mean(corrs)) if corrs else None
    return {
        "symbol": symbol,
        "n_runs_with_returns": len(ids),
        "n_pairs": len(pairs),
        "mean_pairwise_corr": mean,
        "pairs": pairs,
        "run_ids": ids,
        "note": (
            "Mean pairwise correlation of IS strategy returns. Kinlay (Aug 2026) "
            "measured 0.62 across independent agent books. Not a Sharpe correction."
        ),
    }
