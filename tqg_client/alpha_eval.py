"""Score a lagged formulaic signal against a forward-return panel."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .cs_shuffle import _sharpe


def _tz_ts(value: str | pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def split_is_oos(
    frame: pd.DataFrame,
    oos_start: str | pd.Timestamp | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if oos_start is None:
        return frame, frame.iloc[0:0]
    ts = _tz_ts(oos_start)
    idx = frame.index
    if isinstance(idx, pd.DatetimeIndex) and idx.tz is None:
        frame = frame.copy()
        frame.index = idx.tz_localize("UTC")
    return frame.loc[frame.index < ts], frame.loc[frame.index >= ts]


def lag_signal(signal: pd.DataFrame, bars: int = 1) -> pd.DataFrame:
    return signal.shift(int(bars))


def forward_returns(close: pd.DataFrame) -> pd.DataFrame:
    """Return realized at t is close_t / close_{t-1} - 1."""
    return close.pct_change()


def _row_corr(a: pd.DataFrame, b: pd.DataFrame, *, rank: bool) -> pd.Series:
    left = a.rank(axis=1, pct=True) if rank else a
    right = b.rank(axis=1, pct=True) if rank else b
    aligned_l, aligned_r = left.align(right, join="inner")
    l = aligned_l.sub(aligned_l.mean(axis=1), axis=0)
    r = aligned_r.sub(aligned_r.mean(axis=1), axis=0)
    num = (l * r).sum(axis=1)
    den = (l.pow(2).sum(axis=1) * r.pow(2).sum(axis=1)).pow(0.5)
    valid = aligned_l.notna() & aligned_r.notna()
    n = valid.sum(axis=1)
    ic = num / den.replace(0.0, np.nan)
    return ic.where(n >= 10)


def mean_ic(signal: pd.DataFrame, fwd: pd.DataFrame, *, rank: bool) -> dict[str, float]:
    series = _row_corr(signal, fwd, rank=rank).replace([np.inf, -np.inf], np.nan).dropna()
    if series.empty:
        return {"mean": float("nan"), "n_days": 0.0, "std": float("nan")}
    return {
        "mean": float(series.mean()),
        "n_days": float(len(series)),
        "std": float(series.std(ddof=1)) if len(series) > 1 else float("nan"),
    }


def book_turnover(weights: pd.DataFrame) -> float:
    delta = weights.fillna(0.0).diff().abs().sum(axis=1) * 0.5
    delta = delta.replace([np.inf, -np.inf], np.nan).dropna()
    if delta.empty:
        return float("nan")
    return float(delta.mean())


def rank_ls_weights(signal: pd.DataFrame) -> pd.DataFrame:
    sig = signal.rank(axis=1, pct=True)
    weights = sig.sub(sig.mean(axis=1), axis=0)
    denom = weights.abs().sum(axis=1).replace(0.0, np.nan)
    return weights.div(denom, axis=0)


def panel_mean_corr(a: pd.DataFrame, b: pd.DataFrame) -> float:
    series = _row_corr(a, b, rank=True).replace([np.inf, -np.inf], np.nan).dropna()
    if series.empty:
        return float("nan")
    return float(series.mean())


def _finite(value: float) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return float(value)


def score_signal(
    signal: pd.DataFrame,
    close: pd.DataFrame,
    *,
    oos_start: str | None,
    annualization: float,
    lag: int = 1,
    momentum: pd.DataFrame | None = None,
    include_oos: bool = False,
) -> dict[str, Any]:
    lagged = lag_signal(signal, lag)
    fwd = forward_returns(close)
    lagged, fwd = lagged.align(fwd, join="inner")
    is_sig, oos_sig = split_is_oos(lagged, oos_start)
    is_fwd, oos_fwd = split_is_oos(fwd, oos_start)

    def _block(sig: pd.DataFrame, ret: pd.DataFrame) -> dict[str, Any]:
        if sig.empty or ret.empty:
            return {
                "rank_ic": None,
                "ic": None,
                "n_days": 0,
                "turnover": None,
                "sharpe": None,
            }
        rank = mean_ic(sig, ret, rank=True)
        pearson = mean_ic(sig, ret, rank=False)
        weights = rank_ls_weights(sig)
        aligned_w = weights.reindex(index=ret.index, columns=ret.columns).fillna(0.0)
        book = (aligned_w * ret).sum(axis=1)
        return {
            "rank_ic": _finite(rank["mean"]),
            "ic": _finite(pearson["mean"]),
            "n_days": int(rank["n_days"]),
            "turnover": _finite(book_turnover(weights)),
            "sharpe": _finite(_sharpe(book, annualization)),
        }

    out: dict[str, Any] = {
        "lag_bars": int(lag),
        "is": _block(is_sig, is_fwd),
        "oos": _block(oos_sig, oos_fwd) if include_oos else None,
        "corr_momentum": None,
        "flags": [],
    }
    if momentum is not None:
        mom_lag, sig_lag = lag_signal(momentum, lag).align(lagged, join="inner")
        mom_is, _ = split_is_oos(mom_lag, oos_start)
        sig_is, _ = split_is_oos(sig_lag, oos_start)
        corr = panel_mean_corr(sig_is, mom_is)
        out["corr_momentum"] = _finite(corr)
        if out["corr_momentum"] is not None and abs(out["corr_momentum"]) >= 0.70:
            out["flags"] = ["momentum_like"]
    return out


def combine_signals(signals: list[pd.DataFrame]) -> pd.DataFrame:
    ranked = [s.rank(axis=1, pct=True) for s in signals]
    stacked = None
    for frame in ranked:
        stacked = frame if stacked is None else stacked.add(frame, fill_value=np.nan)
    if stacked is None:
        raise ValueError("No signals to combine")
    return stacked / float(len(ranked))


def book_returns(signal: pd.DataFrame, close: pd.DataFrame, *, lag: int = 1) -> pd.Series:
    lagged = lag_signal(signal, lag)
    fwd = forward_returns(close)
    lagged, fwd = lagged.align(fwd, join="inner")
    weights = rank_ls_weights(lagged)
    aligned_w = weights.reindex(index=fwd.index, columns=fwd.columns).fillna(0.0)
    return (aligned_w * fwd).sum(axis=1)
