"""Probability of backtest overfitting via combinatorially symmetric CV.

Bailey, Borwein, López de Prado & Zhu. Input is a matrix of *in-sample*
period returns: one column per configuration tried, one row per period.

PBO > 0.5 means the selection procedure is counterproductive. A single noise
draw is noisy (~0.1–0.65); do not over-read a boundary number.
"""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PSA_MATRIX_RELPATH = "artifacts/psa_returns_matrix.csv"
PBO_RELPATH = "artifacts/pbo.json"


def _sharpe_cols(block: np.ndarray) -> np.ndarray:
    sd = block.std(axis=0, ddof=1)
    mu = block.mean(axis=0)
    return np.where(sd > 0, mu / np.where(sd > 0, sd, 1.0), -np.inf)


def cscv(matrix: np.ndarray, splits: int = 16, max_combos: int = 20_000) -> dict[str, Any]:
    matrix = np.asarray(matrix, dtype=float)
    t_len, n_cfg = matrix.shape
    if n_cfg < 2:
        raise ValueError("need at least 2 configurations (columns)")
    if splits % 2:
        raise ValueError("splits must be even")
    if t_len < splits * 2:
        raise ValueError(f"need at least {splits * 2} rows for {splits} splits, got {t_len}")

    blocks = np.array_split(np.arange(t_len), splits)
    half = splits // 2
    combos = list(itertools.combinations(range(splits), half))
    if len(combos) > max_combos:
        step = len(combos) / max_combos
        combos = [combos[int(i * step)] for i in range(max_combos)]

    logits, ranks, oos_of_winner = [], [], []
    for pick in combos:
        is_idx = np.concatenate([blocks[i] for i in pick])
        oos_idx = np.concatenate([blocks[i] for i in range(splits) if i not in pick])
        is_perf = _sharpe_cols(matrix[is_idx])
        oos_perf = _sharpe_cols(matrix[oos_idx])
        best = int(np.argmax(is_perf))
        order = np.argsort(np.argsort(oos_perf))
        omega = (order[best] + 1.0) / (n_cfg + 1.0)
        logits.append(math.log(omega / (1.0 - omega)))
        ranks.append(omega)
        oos_of_winner.append(float(oos_perf[best]))

    logits_a = np.asarray(logits, dtype=float)
    pbo = float((logits_a <= 0).mean())
    return {
        "method": "bailey_cscv_pbo",
        "pbo": pbo,
        "n_combos": len(combos),
        "n_configs": int(n_cfg),
        "n_periods": int(t_len),
        "splits": int(splits),
        "median_logit": float(np.median(logits_a)),
        "median_rank": float(np.median(ranks)),
        "mean_oos_sharpe_of_winner": float(np.mean(oos_of_winner)),
        "note": (
            "PBO is the fraction of CSCV partitions where the IS winner ranks "
            "below the OOS median. It validates the selection procedure, not the strategy. "
            "Single-matrix PBO on pure noise is noisy."
        ),
    }


def persist_psa_returns_matrix(run_root: Path, frame: pd.DataFrame) -> Path:
    """Write configuration-column IS returns. Index = period, columns = configs."""
    path = Path(run_root) / PSA_MATRIX_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    out.to_csv(path)
    return path


def load_psa_returns_matrix(run_root: Path) -> pd.DataFrame | None:
    path = Path(run_root) / PSA_MATRIX_RELPATH
    if not path.is_file():
        return None
    df = pd.read_csv(path, index_col=0)
    num = df.select_dtypes("number")
    return num if num.shape[1] >= 2 and num.shape[0] >= 4 else None


def run_pbo_from_matrix(
    frame: pd.DataFrame,
    *,
    splits: int | None = None,
) -> dict[str, Any]:
    arr = frame.to_numpy(dtype=float)
    t_len = arr.shape[0]
    if splits is None:
        splits = 10 if t_len >= 40 else 8
        if t_len < splits * 2:
            splits = max(2, (t_len // 4) * 2)
        if splits % 2:
            splits -= 1
        splits = max(2, splits)
    return cscv(arr, splits=splits)


def maybe_run_pbo(run_root: Path) -> dict[str, Any] | None:
    frame = load_psa_returns_matrix(run_root)
    if frame is None:
        return None
    try:
        result = run_pbo_from_matrix(frame)
    except ValueError as exc:
        result = {"method": "bailey_cscv_pbo", "error": str(exc), "pbo": None}
    path = Path(run_root) / PBO_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    return result
