"""Sharpe sampling error, MinBTL/MinTRL, subperiods, break-even cost, timing luck.

Lo (2002) SE and Bailey et al. MinBTL. DSR itself lives in selection.py.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

EULER_GAMMA = 0.5772156649015329


def _norm_ppf(p: float) -> float:
    from tqg_client.selection import _norm_ppf as ppf

    return float(ppf(p))


def sharpe_se_lo(sr_period: float, n: int, skew: float = 0.0, kurtosis: float = 3.0) -> float:
    """SE of a *per-period* Sharpe (Lo 2002). kurtosis is Pearson (3 = normal)."""
    n = int(n)
    if n < 3:
        return float("nan")
    inside = 1.0 - float(skew) * float(sr_period) + 0.25 * (float(kurtosis) - 1.0) * float(sr_period) ** 2
    var = inside / (n - 1)
    return float(math.sqrt(max(var, 0.0)))


def expected_max_sharpe_unit_var(n_trials: int) -> float:
    """E[max SR] treating trials as unit-variance (Bailey MinBTL convention)."""
    n = int(n_trials)
    if n < 2:
        return 0.0
    z1 = _norm_ppf(1.0 - 1.0 / n)
    z2 = _norm_ppf(1.0 - 1.0 / (n * math.e))
    return float((1.0 - EULER_GAMMA) * z1 + EULER_GAMMA * z2)


def min_backtest_length_years(n_trials: int, sr_annual: float = 1.0) -> float:
    """Years of data before an annualised IS Sharpe of ``sr_annual`` is expected from noise."""
    if sr_annual <= 0:
        return float("inf")
    return float((expected_max_sharpe_unit_var(n_trials) / sr_annual) ** 2)


def max_trials_for_years(years: float, sr_annual: float = 1.0, hi: int = 10_000_000) -> int:
    lo, best = 2, 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if min_backtest_length_years(mid, sr_annual) <= years:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return best


def min_track_record_length(
    sr_period: float,
    sr_benchmark: float = 0.0,
    confidence: float = 0.95,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Observations needed before SR is distinguishable from the benchmark."""
    if sr_period <= sr_benchmark:
        return float("inf")
    z = _norm_ppf(confidence)
    inside = 1.0 - skew * sr_period + 0.25 * (kurtosis - 1.0) * sr_period**2
    return float(1.0 + inside * (z / (sr_period - sr_benchmark)) ** 2)


def breakeven_round_trip_bps(mean_ann: float, turnover_ann_one_way: float) -> float:
    """Round-trip cost in bps that would wipe the annual mean."""
    if turnover_ann_one_way <= 0:
        return float("inf")
    return float(mean_ann / (2.0 * turnover_ann_one_way) * 10_000.0)


def turnover_annual_one_way(position: pd.Series, periods_per_year: float) -> float:
    pos = pd.Series(position).astype(float).dropna()
    if len(pos) < 3:
        return float("nan")
    n = len(pos)
    return float(pos.diff().abs().sum() / 2.0 * (float(periods_per_year) / n))


def diagnose_returns(
    returns: pd.Series,
    *,
    annualization: float,
    n_trials: int = 1,
    turnover_ann_one_way: float | None = None,
) -> dict[str, Any]:
    r = pd.Series(returns).dropna().astype(float)
    n = int(len(r))
    ppy = float(annualization) if annualization and annualization > 0 else 1.0
    if n < 4:
        return {"error": "too_few_returns", "n_obs": n}
    mu = float(r.mean())
    sd = float(r.std(ddof=1))
    sr_p = mu / sd if sd > 0 else float("nan")
    skew = float(r.skew()) if n >= 3 else 0.0
    kurt = float(r.kurtosis()) + 3.0 if n >= 4 else 3.0
    se_p = sharpe_se_lo(sr_p, n, skew, kurt)
    sr_ann = sr_p * math.sqrt(ppy) if np.isfinite(sr_p) else float("nan")
    se_ann = se_p * math.sqrt(ppy) if np.isfinite(se_p) else float("nan")
    ar1 = float(r.autocorr(lag=1)) if n > 3 else float("nan")
    years = n / ppy if ppy else float("nan")
    min_btl = min_backtest_length_years(max(int(n_trials), 1), sr_annual=1.0)
    min_trl = min_track_record_length(sr_p, 0.0, 0.95, skew, kurt)
    entitled = max_trials_for_years(years, sr_annual=1.0) if np.isfinite(years) else None

    blocks = 4
    bounds = np.linspace(0, n, blocks + 1).astype(int)
    sub = []
    for i in range(blocks):
        seg = r.iloc[bounds[i] : bounds[i + 1]]
        if len(seg) > 3:
            ssd = float(seg.std(ddof=1))
            ssr = float(seg.mean() / ssd * math.sqrt(ppy)) if ssd > 0 else float("nan")
            sub.append({"block": i + 1, "n": int(len(seg)), "sharpe_ann": ssr})

    out: dict[str, Any] = {
        "n_obs": n,
        "years": years,
        "sharpe_ann": sr_ann,
        "sharpe_se_lo_ann": se_ann,
        "sharpe_ci95": (
            [sr_ann - 1.96 * se_ann, sr_ann + 1.96 * se_ann]
            if np.isfinite(sr_ann) and np.isfinite(se_ann)
            else None
        ),
        "t_stat": sr_p / se_p if se_p and se_p > 0 else float("nan"),
        "skew": skew,
        "kurtosis_pearson": kurt,
        "ar1": ar1,
        "ar1_inflates_ann_sharpe": bool(np.isfinite(ar1) and abs(ar1) > 0.15),
        "min_btl_years_sr1": min_btl,
        "min_trl_obs": min_trl if np.isfinite(min_trl) else None,
        "entitled_independent_trials_sr1": entitled,
        "n_trials_assumed": int(n_trials),
        "subperiod_sharpe_ann": sub,
        "note": (
            "Report the Sharpe interval, not the point. MinBTL is years of data needed "
            "before an IS Sharpe of 1 is expected from N independent noise trials."
        ),
    }
    if turnover_ann_one_way is not None and np.isfinite(turnover_ann_one_way) and turnover_ann_one_way > 0:
        mean_ann = mu * ppy
        be = breakeven_round_trip_bps(mean_ann, float(turnover_ann_one_way))
        out["turnover_ann_one_way"] = float(turnover_ann_one_way)
        out["mean_ann"] = mean_ann
        out["breakeven_round_trip_bps"] = be
        out["breakeven_is_latency_business"] = bool(be < 15.0)
    return out
