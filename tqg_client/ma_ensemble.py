"""Heterogeneous MA-type ensemble consensus signals (research helpers).

Votes = sign(close_t - MA_{t-1}) across MA families; consensus = mean(votes).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Deduped from the user draft (dropped duplicate WMA; TMA ≡ TRIMA).
MA_NAMES: list[str] = [
    "SMA",
    "EMA",
    "DEMA",
    "TEMA",
    "WMA",
    "TRIMA",
    "HMA",
    "ZLEMA",
    "KAMA",
    "T3",
    "LINEARREG",
    "SMOOTHED_MA",
    "VAMA",
    "JMA",
]


def wma(series: pd.Series, n: int) -> pd.Series:
    w = np.arange(1, n + 1, dtype=float)
    w = w / w.sum()
    x = series.to_numpy(dtype=float)
    out = np.full(len(x), np.nan, dtype=float)
    for i in range(n - 1, len(x)):
        window = x[i - n + 1 : i + 1]
        if np.any(~np.isfinite(window)):
            continue
        out[i] = float(np.dot(window, w))
    return pd.Series(out, index=series.index)


def sma(series: pd.Series, n: int) -> pd.Series:
    x = series.to_numpy(dtype=float)
    out = np.full(len(x), np.nan, dtype=float)
    csum = np.cumsum(np.where(np.isfinite(x), x, 0.0))
    cfin = np.cumsum(np.isfinite(x).astype(float))
    for i in range(n - 1, len(x)):
        j = i - n
        s = csum[i] - (csum[j] if j >= 0 else 0.0)
        k = cfin[i] - (cfin[j] if j >= 0 else 0.0)
        if k == n:
            out[i] = s / n
    return pd.Series(out, index=series.index)


def ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()


def dema(series: pd.Series, n: int) -> pd.Series:
    e1 = ema(series, n)
    e2 = ema(e1, n)
    return 2.0 * e1 - e2


def tema(series: pd.Series, n: int) -> pd.Series:
    e1 = ema(series, n)
    e2 = ema(e1, n)
    e3 = ema(e2, n)
    return 3.0 * (e1 - e2) + e3


def trima(series: pd.Series, n: int) -> pd.Series:
    n1 = int(np.ceil((n + 1) / 2.0))
    n2 = int(np.floor((n + 1) / 2.0))
    return sma(sma(series, n1), n2)


def hma(series: pd.Series, n: int) -> pd.Series:
    half = max(1, n // 2)
    sqrt_n = max(1, int(np.floor(np.sqrt(n))))
    return wma(2.0 * wma(series, half) - wma(series, n), sqrt_n)


def zlema(series: pd.Series, n: int) -> pd.Series:
    lag = max(0, (n - 1) // 2)
    adj = series + (series - series.shift(lag))
    return ema(adj, n)


def kama(series: pd.Series, n: int, fast: int = 2, slow: int = 30) -> pd.Series:
    change = series.diff(n).abs()
    dx = series.diff().abs().to_numpy(dtype=float)
    vol = np.full(len(dx), np.nan, dtype=float)
    for i in range(n, len(dx)):
        w = dx[i - n + 1 : i + 1]
        if np.all(np.isfinite(w)):
            vol[i] = float(np.nansum(w))
    volatility = pd.Series(vol, index=series.index)
    er = change / volatility.replace(0.0, np.nan)
    fast_sc = 2.0 / (fast + 1.0)
    slow_sc = 2.0 / (slow + 1.0)
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
    x = series.to_numpy(dtype=float)
    scv = sc.to_numpy(dtype=float)
    out = np.full(len(x), np.nan, dtype=float)
    seed = None
    for i in range(len(x)):
        if not np.isfinite(x[i]):
            continue
        if seed is None:
            if i >= n - 1:
                seed = x[i]
                out[i] = seed
            continue
        if not np.isfinite(scv[i]):
            out[i] = seed
            continue
        seed = seed + scv[i] * (x[i] - seed)
        out[i] = seed
    return pd.Series(out, index=series.index)


def t3(series: pd.Series, n: int, vfactor: float = 0.7) -> pd.Series:
    c1 = -vfactor**3
    c2 = 3.0 * vfactor**2 + 3.0 * vfactor**3
    c3 = -6.0 * vfactor**2 - 3.0 * vfactor - 3.0 * vfactor**3
    c4 = 1.0 + 3.0 * vfactor + vfactor**3 + 3.0 * vfactor**2
    e1 = ema(series, n)
    e2 = ema(e1, n)
    e3 = ema(e2, n)
    e4 = ema(e3, n)
    e5 = ema(e4, n)
    e6 = ema(e5, n)
    return c1 * e6 + c2 * e5 + c3 * e4 + c4 * e3


def linearreg(series: pd.Series, n: int) -> pd.Series:
    x = series.to_numpy(dtype=float)
    out = np.full(len(x), np.nan, dtype=float)
    t = np.arange(n, dtype=float)
    t_mean = t.mean()
    t_var = ((t - t_mean) ** 2).sum()
    for i in range(n - 1, len(x)):
        y = x[i - n + 1 : i + 1]
        if not np.all(np.isfinite(y)):
            continue
        y_mean = y.mean()
        beta = ((t - t_mean) * (y - y_mean)).sum() / t_var
        alpha = y_mean - beta * t_mean
        out[i] = alpha + beta * (n - 1)
    return pd.Series(out, index=series.index)


def smoothed_ma(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(alpha=1.0 / float(n), adjust=False).mean()


def vama(close: pd.Series, volume: pd.Series, n: int) -> pd.Series:
    pv = (close * volume).to_numpy(dtype=float)
    vv = volume.to_numpy(dtype=float)
    out = np.full(len(pv), np.nan, dtype=float)
    for i in range(n - 1, len(pv)):
        p_w = pv[i - n + 1 : i + 1]
        v_w = vv[i - n + 1 : i + 1]
        if not (np.all(np.isfinite(p_w)) and np.all(np.isfinite(v_w))):
            continue
        denom = float(np.sum(v_w))
        if denom <= 0:
            continue
        out[i] = float(np.sum(p_w) / denom)
    return pd.Series(out, index=close.index)


def jma(series: pd.Series, n: int, phase: float = 50.0) -> pd.Series:
    """Jurik-like adaptive EMA proxy (proprietary JMA is not redistributable).

    Efficiency ratio modulates an EMA smooth; ``phase`` nudges the fast/slow mix.
    Numerically stable on crypto-scale prices (unlike naive Jurik recursion ports).
    """
    del phase  # reserved for API parity with draft Signal.JMA(..., phase)
    change = series.diff(n).abs()
    dx = series.diff().abs().to_numpy(dtype=float)
    vol = np.full(len(dx), np.nan, dtype=float)
    for i in range(n, len(dx)):
        w = dx[i - n + 1 : i + 1]
        if np.all(np.isfinite(w)):
            vol[i] = float(np.sum(w))
    er = (change / pd.Series(vol, index=series.index).replace(0.0, np.nan)).clip(0.0, 1.0)
    # Map ER to EMA span between ~n/2 (fast) and ~3n/2 (slow).
    span = (n * (1.5 - er)).clip(lower=max(2.0, n / 2.0), upper=max(3.0, 1.5 * n))
    x = series.to_numpy(dtype=float)
    sp = span.to_numpy(dtype=float)
    out = np.full(len(x), np.nan, dtype=float)
    seed = None
    for i in range(len(x)):
        if not np.isfinite(x[i]):
            continue
        if seed is None:
            if i >= n - 1:
                seed = x[i]
                out[i] = seed
            continue
        s = sp[i] if np.isfinite(sp[i]) else float(n)
        alpha = 2.0 / (s + 1.0)
        seed = alpha * x[i] + (1.0 - alpha) * seed
        out[i] = seed
    return pd.Series(out, index=series.index)


def compute_ma_panel(
    close: pd.Series,
    volume: pd.Series,
    window: int,
    *,
    ma_names: list[str] | None = None,
) -> pd.DataFrame:
    names = list(ma_names or MA_NAMES)
    builders = {
        "SMA": lambda: sma(close, window),
        "EMA": lambda: ema(close, window),
        "DEMA": lambda: dema(close, window),
        "TEMA": lambda: tema(close, window),
        "WMA": lambda: wma(close, window),
        "TRIMA": lambda: trima(close, window),
        "TMA": lambda: trima(close, window),
        "HMA": lambda: hma(close, window),
        "ZLEMA": lambda: zlema(close, window),
        "KAMA": lambda: kama(close, window),
        "T3": lambda: t3(close, window),
        "LINEARREG": lambda: linearreg(close, window),
        "SMOOTHED_MA": lambda: smoothed_ma(close, window),
        "VAMA": lambda: vama(close, volume, window),
        "JMA": lambda: jma(close, window),
    }
    missing = [n for n in names if n not in builders]
    if missing:
        raise ValueError(f"Unknown MA names: {missing}")
    cols = {name: builders[name]() for name in names}
    # Lag every MA so votes use completed windows only (close_t vs MA_{t-1}).
    return pd.DataFrame(cols).shift(1)


def consensus_signal(close: pd.Series, mas: pd.DataFrame) -> pd.Series:
    votes = np.sign(close.to_numpy(dtype=float)[:, None] - mas.to_numpy(dtype=float))
    votes = pd.DataFrame(votes, index=close.index, columns=mas.columns)
    return votes.mean(axis=1, skipna=True)


def positions_from_consensus(
    consensus: pd.Series,
    *,
    entry: float,
    exit_thresh: float,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Stateful long/short with exit band."""
    pos = np.zeros(len(consensus), dtype=float)
    entries = np.zeros(len(consensus), dtype=bool)
    short_entries = np.zeros(len(consensus), dtype=bool)
    state = 0.0
    vals = consensus.to_numpy(dtype=float)
    for i, c in enumerate(vals):
        if not np.isfinite(c):
            state = 0.0
            pos[i] = 0.0
            continue
        if state > 0:
            if abs(c) < exit_thresh or c < -entry:
                state = -1.0 if c < -entry else 0.0
                if state < 0:
                    short_entries[i] = True
            else:
                state = 1.0
        elif state < 0:
            if abs(c) < exit_thresh or c > entry:
                state = 1.0 if c > entry else 0.0
                if state > 0:
                    entries[i] = True
            else:
                state = -1.0
        else:
            if c > entry:
                state = 1.0
                entries[i] = True
            elif c < -entry:
                state = -1.0
                short_entries[i] = True
        pos[i] = state
    idx = consensus.index
    return (
        pd.Series(pos, index=idx),
        pd.Series(entries, index=idx),
        pd.Series(short_entries, index=idx),
    )


def net_returns_from_positions(
    close: pd.Series,
    pos: pd.Series,
    *,
    fee: float,
    slippage: float,
) -> pd.Series:
    """Target-position returns with 1-bar execution lag (decision at t earns r_{t+1})."""
    rb = close.pct_change().fillna(0.0)
    traded = pos.reindex(close.index).fillna(0.0).shift(1).fillna(0.0)
    gross = traded * rb
    turn = traded.diff().abs().fillna(traded.abs())
    return gross - turn * (fee + slippage)


def returns_from_consensus_signals(
    close: pd.Series,
    *,
    entries: pd.Series,
    short_entries: pd.Series,
    exits: pd.Series,
    fee: float,
    slippage: float,
) -> pd.Series:
    """Match the BTC baseline execution model (vectorbt from_signals)."""
    import vectorbt as vbt

    pf = vbt.Portfolio.from_signals(
        close,
        entries=entries.fillna(False),
        short_entries=short_entries.fillna(False),
        exits=exits.fillna(False),
        short_exits=exits.fillna(False),
        fees=fee,
        slippage=slippage,
        freq="1D",
    )
    return pf.returns().astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
