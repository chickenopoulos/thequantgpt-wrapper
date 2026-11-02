#!/usr/bin/env python3
"""SMA / close cross: does a lagged close-versus-SMA sign have an edge?

Pre-declared before looking at results (not a search over the winner):

- Signal at the close of bar t: close_t ? SMA(n) ending at t-1.
  SMA is ``close.rolling(n).mean().shift(1)``. The book earns the next bar
  (weights are shifted one more bar). That is the lab lag rule.
- Windows: 20, 50, 100, 200. Primary window is 200 (textbook trend filter).
  The other three are a correlated sensitivity grid, counted in N.
- Books:
  - long_flat: equal weight among names with close > SMA, otherwise cash.
  - long_short: sign(close - SMA), weights scaled to gross 1.
- OOS cut: 2025-01-01. Windows and books are not chosen on OOS.
- Venues: Dukascopy FX daily, Binance USDT-M perps daily, Alpaca shortable
  US names daily, EODHD S&P point-in-time daily (adjusted close).

Primary books used for the verdict (still inside N):
- FX and Binance perps: long_short, SMA 200 (both sides are tradable).
- Alpaca and EODHD: long_flat, SMA 200 (classic price-versus-average filter).
  long_short is reported on both equity venues. EODHD has no borrow file,
  so that long_short book assumes a free short.

Costs are one-way on the sum of absolute weight changes:
- FX 1.5 bps, Binance perps 5 bps, equities 9.5 bps (4.5 fee + 5 slip).

N per venue = 4 windows x 2 books = 8. DSR uses that N and is advisory:
the windows share one return panel, so trials are not independent.
k = 1 (one signal, not a stack). PBO is not computable (no PSA matrix).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tqg_client.factor_attribution import ols_hac
from tqg_client.return_inference import build_inference_payload
from tqg_client.selection import deflated_sharpe
from tqg_client.sharpe_diagnostics import diagnose_returns

DATA = REPO / "data"
OUT = REPO / "runs" / "sma_close_cross_battery"
OOS_START = pd.Timestamp("2025-01-01", tz="UTC")
WINDOWS = (20, 50, 100, 200)
PRIMARY_N = 200
NULL_SHIFTS = 200
NULL_SEED = 7

STABLE_BASES = {
    "USDC",
    "BUSD",
    "FDUSD",
    "TUSD",
    "USDP",
    "DAI",
    "USDE",
    "USD1",
    "UST",
    "EUR",
    "AEUR",
}


def _utc(s: pd.Series | pd.DatetimeIndex) -> pd.DatetimeIndex:
    t = pd.to_datetime(s, utc=True)
    if isinstance(t, pd.Series):
        return pd.DatetimeIndex(t)
    return t


def sharpe(rets: pd.Series, ann: float) -> float:
    r = rets.dropna()
    if len(r) < 30:
        return float("nan")
    vol = float(r.std(ddof=1))
    if vol <= 0:
        return float("nan")
    return float(np.sqrt(ann) * r.mean() / vol)


def max_dd(rets: pd.Series) -> float:
    r = rets.dropna()
    if r.empty:
        return float("nan")
    cum = (1.0 + r).cumprod()
    return float((cum / cum.cummax() - 1.0).min())


def cagr(rets: pd.Series, ann: float) -> float:
    r = rets.dropna()
    if len(r) < 30:
        return float("nan")
    wealth = float((1.0 + r).prod())
    if wealth <= 0:
        return float("nan")
    return float(wealth ** (ann / len(r)) - 1.0)


def slice_stats(rets: pd.Series, exp: pd.Series, ann: float, start, end) -> dict[str, Any]:
    m = (rets.index >= start) & (rets.index <= end)
    r = rets.loc[m]
    e = exp.reindex(r.index)
    return {
        "sharpe": sharpe(r, ann),
        "cagr": cagr(r, ann),
        "max_dd": max_dd(r),
        "exposure": float(e.mean()) if len(e) else float("nan"),
        "n_obs": int(r.dropna().shape[0]),
        "mean_daily": float(r.dropna().mean()) if r.dropna().shape[0] else float("nan"),
    }


def sma_sign(close: pd.DataFrame, n: int) -> pd.DataFrame:
    sma = close.rolling(n, min_periods=n).mean().shift(1)
    sig = np.sign(close - sma)
    sig = sig.where(close.notna() & sma.notna(), 0.0)
    return sig.replace([np.inf, -np.inf], 0.0).fillna(0.0)


def weights_from_sign(sig: pd.DataFrame, mode: str) -> pd.DataFrame:
    if mode == "long_flat":
        active = (sig > 0).astype(float)
        denom = active.sum(axis=1).replace(0, np.nan)
        return active.div(denom, axis=0).fillna(0.0)
    if mode == "long_short":
        gross = sig.abs().sum(axis=1).replace(0, np.nan)
        return sig.div(gross, axis=0).fillna(0.0)
    raise ValueError(mode)


def benchmark_weights(close: pd.DataFrame) -> pd.DataFrame:
    valid = close.notna() & close.shift(1).notna()
    active = valid.astype(float)
    denom = active.sum(axis=1).replace(0, np.nan)
    return active.div(denom, axis=0).fillna(0.0)


def net_from_weights(weights: pd.DataFrame, rets: pd.DataFrame, cost: float) -> tuple[pd.Series, pd.Series]:
    """Decision weights at close t earn rets[t+1]. ``rets[t]`` is close[t]/close[t-1]-1."""
    w_exec = weights.shift(1).fillna(0.0)
    aligned = rets.reindex(index=w_exec.index, columns=w_exec.columns)
    gross = (w_exec * aligned).sum(axis=1, min_count=1)
    turnover = w_exec.diff().abs().sum(axis=1)
    net = (gross - turnover * cost).rename("net")
    exposure = w_exec.abs().sum(axis=1).rename("exposure")
    return net, exposure


def summarize_book(
    name: str,
    weights: pd.DataFrame,
    rets: pd.DataFrame,
    close: pd.DataFrame,
    *,
    ann: float,
    cost: float,
    mode: str,
    window: int,
) -> dict[str, Any]:
    net, exp = net_from_weights(weights, rets, cost)
    gross, _ = net_from_weights(weights, rets, 0.0)
    # Drop the SMA warmup and the execution lag.
    start = close.index[min(window + 2, len(close) - 1)]
    net = net.loc[start:]
    gross = gross.loc[start:]
    exp = exp.loc[start:]
    is_end = OOS_START - pd.Timedelta(nanoseconds=1)
    out: dict[str, Any] = {
        "name": name,
        "mode": mode,
        "window": window,
        "ann": ann,
        "cost_one_way": cost,
        "full": slice_stats(net, exp, ann, net.index.min(), net.index.max()),
        "is": slice_stats(net, exp, ann, net.index.min(), is_end),
        "oos": slice_stats(net, exp, ann, OOS_START, net.index.max()),
        "gross_is_sharpe": sharpe(gross.loc[gross.index < OOS_START], ann),
        "gross_oos_sharpe": sharpe(gross.loc[gross.index >= OOS_START], ann),
    }
    # Breadth: each name at full notional on its own sign, same lag and cost.
    sig = np.sign(weights).replace(0, np.nan)
    # weights are already scaled; recover the sign from the pre-scale rule via sign of weights.
    pos = np.sign(weights).shift(1).fillna(0.0)
    name_rets = pos * rets.reindex(index=pos.index, columns=pos.columns) - pos.diff().abs() * cost
    name_rets = name_rets.loc[start:]
    is_names = name_rets.loc[name_rets.index < OOS_START]
    sharpes = []
    for col in is_names.columns:
        s = is_names[col].dropna()
        # Require a real sample, not a column of zeros from names that never traded.
        if int((s != 0).sum()) < 100:
            continue
        sharpes.append(sharpe(s, ann))
    sharpes = [x for x in sharpes if np.isfinite(x)]
    if sharpes:
        arr = np.asarray(sharpes, dtype=float)
        out["names"] = {
            "n": int(len(arr)),
            "median_is_sharpe": float(np.median(arr)),
            "p25_is_sharpe": float(np.percentile(arr, 25)),
            "p75_is_sharpe": float(np.percentile(arr, 75)),
            "frac_is_sharpe_pos": float(np.mean(arr > 0)),
        }
    else:
        out["names"] = {"n": 0}
    out["_net"] = net
    out["_exp"] = exp
    out["_weights"] = weights
    return out


def market_regression(net: pd.Series, bench: pd.Series, ann: float) -> dict[str, Any]:
    df = pd.concat([net.rename("y"), bench.rename("x")], axis=1, sort=True).dropna()
    df = df.loc[df.index < OOS_START]
    if len(df) < 60 or float(df["x"].std()) == 0:
        return {"error": "too_few"}
    y = df["y"].to_numpy()
    x_mkt = df["x"].to_numpy()
    x = np.column_stack([np.ones(len(df)), x_mkt])
    fit = ols_hac(y, x)
    beta = float(fit["beta"][1])
    # Keep the intercept in the hedged series. OLS residuals are mean-zero by construction.
    hedged = pd.Series(y - beta * x_mkt, index=df.index)
    return {
        "sample": "in_sample",
        "n_obs": int(len(df)),
        "alpha_per_period": float(fit["beta"][0]),
        "alpha_ann": float(fit["beta"][0] * ann),
        "alpha_hac_t": float(fit["t"][0]),
        "alpha_hac_p": float(fit["p"][0]),
        "beta": beta,
        "beta_hac_t": float(fit["t"][1]),
        "r2": float(fit["r2"]),
        "hedged_sharpe": sharpe(hedged, ann),
    }


def shift_null(
    weights: pd.DataFrame,
    rets: pd.DataFrame,
    cost: float,
    ann: float,
    window: int,
    strategy_is: float,
) -> dict[str, Any]:
    """Circular time-shifts of the decision weights. Keeps turnover, breaks timing."""
    w = weights.to_numpy(dtype=float)
    r = rets.reindex(index=weights.index, columns=weights.columns).to_numpy(dtype=float)
    n, k = w.shape
    rng = np.random.default_rng(NULL_SEED)
    lo = max(window + 5, n // 20)
    hi = max(lo + 1, n // 2)
    shifts = rng.integers(lo, hi, size=NULL_SHIFTS)
    is_mask = np.asarray(weights.index < OOS_START)
    sharpes = np.empty(NULL_SHIFTS, dtype=float)
    for i, kshift in enumerate(shifts):
        rolled = np.roll(w, int(kshift), axis=0)
        w_exec = np.vstack([np.zeros((1, k)), rolled[:-1]])
        contrib = w_exec * np.nan_to_num(r, nan=0.0)
        all_nan = np.all(np.isnan(r), axis=1)
        gross = np.where(all_nan, np.nan, contrib.sum(axis=1))
        prev = np.vstack([np.zeros((1, k)), w_exec[:-1]])
        turn = np.abs(w_exec - prev).sum(axis=1)
        net = gross - turn * cost
        sample = net[is_mask]
        sample = sample[np.isfinite(sample)]
        if len(sample) < 30 or float(np.std(sample, ddof=1)) <= 0:
            sharpes[i] = np.nan
        else:
            sharpes[i] = float(np.sqrt(ann) * sample.mean() / sample.std(ddof=1))
    valid = sharpes[np.isfinite(sharpes)]
    pct = None
    if len(valid) and np.isfinite(strategy_is):
        pct = float(np.mean(valid < strategy_is))
    return {
        "n_shifts": int(len(valid)),
        "null_is_mean": float(np.mean(valid)) if len(valid) else None,
        "null_is_p95": float(np.percentile(valid, 95)) if len(valid) else None,
        "null_is_p50": float(np.percentile(valid, 50)) if len(valid) else None,
        "strategy_percentile": pct,
    }


def attach_primary_stats(row: dict[str, Any], bench_net: pd.Series, n_trials: int) -> dict[str, Any]:
    net: pd.Series = row["_net"]
    is_net = net.loc[net.index < OOS_START].dropna()
    ann = float(row["ann"])
    w_exec = row["_weights"].shift(1).fillna(0.0)
    daily_turn = w_exec.diff().abs().sum(axis=1).reindex(is_net.index).fillna(0.0)
    turn_ann = float(daily_turn.mean() * ann) if len(daily_turn) else float("nan")
    diag = diagnose_returns(
        is_net,
        annualization=ann,
        n_trials=n_trials,
        turnover_ann_one_way=turn_ann,
    )
    # One-way turnover from the executed weight changes, annualized.
    exp = row["_exp"].reindex(is_net.index)
    # Recover turnover from gross-net gap when cost > 0.
    dsr = deflated_sharpe(is_net, n_trials=n_trials, annualization=ann)
    infer = build_inference_payload(is_net, annualization=ann, n_boot=800, seed=11)
    reg = market_regression(net, bench_net, ann)
    is_sh = float(row["is"]["sharpe"])
    null = shift_null(
        row["_weights"],
        row["_panel_rets"],
        row["cost_one_way"],
        ann,
        int(row["window"]),
        is_sh,
    )
    row["sharpe_diagnostics_is"] = diag
    row["dsr"] = dsr
    row["inference_is"] = infer
    row["vs_ew_benchmark_is"] = reg
    row["shift_null_is"] = null
    row["null_percentile_is"] = null.get("strategy_percentile")
    row["beats_null_p95"] = bool(
        null.get("null_is_p95") is not None and np.isfinite(is_sh) and is_sh > null["null_is_p95"]
    )
    row["n_trials"] = n_trials
    row["k"] = 1
    _ = exp
    return row


def load_fx() -> tuple[pd.DataFrame, float, float, dict[str, Any]]:
    frames = []
    for fp in sorted((DATA / "dukascopy" / "fx").glob("*_1d.parquet")):
        if "dukascopy_g7" in fp.name:
            continue
        df = pd.read_parquet(fp, columns=["time", "close"])
        sym = fp.stem.replace("_1d", "")
        s = df.assign(time=_utc(df["time"])).set_index("time")["close"].astype(float)
        s = s[~s.index.duplicated(keep="last")].sort_index().rename(sym)
        frames.append(s)
    close = pd.concat(frames, axis=1, sort=True).sort_index()
    close = close.loc["2005-01-01":]
    meta = {
        "venue": "dukascopy_fx",
        "asset_class": "fx",
        "n_names": int(close.shape[1]),
        "names": list(close.columns),
        "start": str(close.index.min()),
        "end": str(close.index.max()),
        "price": "close (bid/mid as stored)",
        "annualization": 365,
        "cost_one_way": 0.00015,
        "note": "All local Dukascopy daily pairs. Bars are 7-day (median gap 24h), so annualization is 365. Portfolio is equal-weight of pair quote returns.",
    }
    return close, 365.0, 0.00015, meta


def _drop_crazy(close: pd.DataFrame, limit: float = 1.5) -> tuple[pd.DataFrame, list[str]]:
    r = close.pct_change(fill_method=None)
    bad = [c for c in close.columns if float(r[c].abs().max(skipna=True) or 0) > limit]
    return close.drop(columns=bad, errors="ignore"), bad


def load_binance(top_n: int = 40) -> tuple[pd.DataFrame, float, float, dict[str, Any]]:
    path = DATA / "binance" / "binance_futures_ohlcv_1d.parquet"
    df = pd.read_parquet(path, columns=["time", "asset", "close", "volume"])
    df["time"] = _utc(df["time"])
    df["asset"] = df["asset"].astype(str).str.upper()
    df = df[df["asset"].str.endswith("USDT")]
    base = df["asset"].str.replace("USDT", "", regex=False)
    df = df[~base.isin(STABLE_BASES)]
    df["dv"] = df["close"].astype(float) * df["volume"].astype(float)
    wide_c = df.pivot_table(index="time", columns="asset", values="close", aggfunc="last").sort_index()
    wide_dv = df.pivot_table(index="time", columns="asset", values="dv", aggfunc="last").sort_index()
    # Eligibility uses pre-OOS history only, so a 2025 listing cannot qualify on later bars.
    pre_counts = wide_c.loc[wide_c.index < OOS_START].notna().sum()
    keep = pre_counts[pre_counts >= 400].index
    pre = wide_dv.loc[wide_dv.index < OOS_START, keep]
    med = pre.median().sort_values(ascending=False)
    names = list(med.head(top_n).index)
    close = wide_c[names].astype(float)
    meta = {
        "venue": "binance_usdt_m_perps",
        "asset_class": "crypto",
        "n_names": int(close.shape[1]),
        "names": list(close.columns),
        "start": str(close.index.min()),
        "end": str(close.index.max()),
        "price": "close",
        "annualization": 365,
        "cost_one_way": 0.0005,
        "liquidity": (
            f"top {top_n} by median close*volume before 2025-01-01, "
            "at least 400 pre-OOS daily bars, USDT-margined perps, stablecoin bases removed"
        ),
    }
    return close, 365.0, 0.0005, meta


def load_eodhd(top_n: int = 80) -> tuple[pd.DataFrame, float, float, dict[str, Any]]:
    path = DATA / "equities" / "eodhd" / "sp500_pit_ohlcv_1d.parquet"
    df = pd.read_parquet(path, columns=["time", "asset", "close", "adjusted_close", "volume"])
    df["time"] = _utc(df["time"])
    df["asset"] = df["asset"].astype(str).str.upper()
    px = df["adjusted_close"].astype(float).where(df["adjusted_close"].notna(), df["close"].astype(float))
    df["px"] = px
    df["dv"] = df["close"].astype(float) * df["volume"].astype(float)
    wide = df.pivot_table(index="time", columns="asset", values="px", aggfunc="last").sort_index()
    dv = df.pivot_table(index="time", columns="asset", values="dv", aggfunc="last").sort_index()
    counts = wide.loc[wide.index < OOS_START].notna().sum()
    keep = counts[counts >= 756].index
    pre = dv.loc[dv.index < OOS_START, keep]
    med = pre.median().sort_values(ascending=False)
    names = list(med.head(top_n).index)
    close = wide[names].astype(float)
    close, bad = _drop_crazy(close, 1.0)
    meta = {
        "venue": "eodhd_sp500_pit",
        "asset_class": "equity",
        "n_names": int(close.shape[1]),
        "names": list(close.columns),
        "start": str(close.index.min()),
        "end": str(close.index.max()),
        "price": "adjusted_close (split and dividend adjusted)",
        "annualization": 252,
        "cost_one_way": 0.00095,
        "liquidity": f"top {top_n} by median unadjusted dollar volume before 2025-01-01, min 756 pre-OOS bars",
        "dropped_abs_ret_gt_100pct": bad,
        "borrow": "long_short assumes a free short; the file is index membership, not a borrow list",
    }
    return close, 252.0, 0.00095, meta


def load_alpaca(top_n: int = 80) -> tuple[pd.DataFrame, float, float, dict[str, Any]]:
    bars_dir = DATA / "equities" / "alpaca_shortable_equity_1d" / "bars"
    files = sorted(bars_dir.glob("*.parquet"), key=lambda p: p.stat().st_size, reverse=True)[:400]
    rows = []
    for fp in files:
        df = pd.read_parquet(fp, columns=["time", "close", "volume"])
        if df.empty:
            continue
        df = df.copy()
        df["time"] = _utc(df["time"])
        df["asset"] = fp.stem.upper()
        rows.append(df)
    raw = pd.concat(rows, ignore_index=True)
    raw["dv"] = raw["close"].astype(float) * raw["volume"].astype(float)
    wide = raw.pivot_table(index="time", columns="asset", values="close", aggfunc="last").sort_index()
    dv = raw.pivot_table(index="time", columns="asset", values="dv", aggfunc="last").sort_index()
    counts = wide.loc[wide.index < OOS_START].notna().sum()
    keep = counts[counts >= 756].index
    pre = dv.loc[dv.index < OOS_START, keep]
    med = pre.median().sort_values(ascending=False)
    names = list(med.head(top_n).dropna().index)
    close = wide[names].astype(float)
    close, bad = _drop_crazy(close, 1.0)
    meta = {
        "venue": "alpaca_shortable",
        "asset_class": "equity",
        "n_names": int(close.shape[1]),
        "names": list(close.columns),
        "start": str(close.index.min()),
        "end": str(close.index.max()),
        "price": "close (Alpaca daily; AAPL 2020 split is already on a split-adjusted scale)",
        "annualization": 252,
        "cost_one_way": 0.00095,
        "liquidity": (
            f"largest 400 bar files, then top {top_n} by median dollar volume before 2025-01-01, "
            "min 756 pre-OOS bars. Universe file is entirely shortable and easy-to-borrow as of the fetch."
        ),
        "dropped_abs_ret_gt_100pct": bad,
    }
    return close, 252.0, 0.00095, meta


def run_venue(close: pd.DataFrame, ann: float, cost: float, meta: dict[str, Any]) -> dict[str, Any]:
    rets = close.pct_change(fill_method=None)
    bench_w = benchmark_weights(close)
    bench_net, _ = net_from_weights(bench_w, rets, cost)
    books = []
    n_trials = len(WINDOWS) * 2
    for n in WINDOWS:
        sig = sma_sign(close, n)
        for mode in ("long_flat", "long_short"):
            w = weights_from_sign(sig, mode)
            row = summarize_book(
                f"sma{n}_{mode}",
                w,
                rets,
                close,
                ann=ann,
                cost=cost,
                mode=mode,
                window=n,
            )
            row["_panel_rets"] = rets
            primary_mode = "long_short" if meta["asset_class"] in {"fx", "crypto"} else "long_flat"
            if n == PRIMARY_N and mode == primary_mode:
                attach_primary_stats(row, bench_net, n_trials)
                row["role"] = "primary"
            elif n == PRIMARY_N:
                attach_primary_stats(row, bench_net, n_trials)
                row["role"] = "primary_window_other_book"
            else:
                row["role"] = "window_grid"
            books.append(row)
    # Benchmark stats for the report.
    b_exp = bench_w.shift(1).abs().sum(axis=1)
    bench_summary = {
        "is": slice_stats(bench_net, b_exp, ann, bench_net.index.min(), OOS_START - pd.Timedelta(nanoseconds=1)),
        "oos": slice_stats(bench_net, b_exp, ann, OOS_START, bench_net.index.max()),
    }
    return {
        "meta": meta,
        "n_trials_venue": n_trials,
        "k": 1,
        "benchmark_ew": bench_summary,
        "books": books,
        "_bench_net": bench_net,
    }


def _public_book(row: dict[str, Any]) -> dict[str, Any]:
    skip = {"_net", "_exp", "_weights", "_panel_rets"}
    return {k: v for k, v in row.items() if k not in skip}


def verdict_lines(row: dict[str, Any]) -> list[str]:
    """Pre-declared pass rule. Failure on any line is no incremental edge."""
    ci = (row.get("sharpe_diagnostics_is") or {}).get("sharpe_ci95") or [float("nan"), float("nan")]
    hac_p = (row.get("inference_is") or {}).get("mean_net_return", {}).get("hac_p_two_sided")
    reg = row.get("vs_ew_benchmark_is") or {}
    fails = []
    if not (isinstance(ci[0], float) and ci[0] > 0):
        fails.append("IS Sharpe 95% interval includes zero or below")
    if not (isinstance(hac_p, float) and hac_p < 0.05 and row["is"]["sharpe"] > 0):
        fails.append("HAC test does not reject a zero IS mean at 5%")
    if not (isinstance(row["oos"]["sharpe"], float) and row["oos"]["sharpe"] > 0):
        fails.append("OOS Sharpe is not positive")
    alpha = reg.get("alpha_ann")
    alpha_p = reg.get("alpha_hac_p")
    if not (isinstance(alpha, float) and alpha > 0 and isinstance(alpha_p, float) and alpha_p < 0.05):
        fails.append("no positive HAC alpha versus the equal-weight hold")
    if not row.get("beats_null_p95"):
        fails.append("IS Sharpe does not clear the time-shift null 95th percentile")
    dsr_v = (row.get("dsr") or {}).get("dsr")
    if not (isinstance(dsr_v, float) and dsr_v >= 0.95):
        fails.append("DSR below 0.95 under N=8 (advisory, windows are correlated)")
    if fails:
        return ["Verdict: no edge. " + "; ".join(fails) + "."]
    return ["Verdict: the pre-declared book clears the pass rule on this venue."]


def render_report(payload: dict[str, Any]) -> str:
    lines = [
        "# SMA / close cross",
        "",
        "Rule, fixed before the run: at the close, compare price with the SMA whose window ended the prior bar, then earn the next bar. Primary length is 200. Lengths 20, 50, and 100 are a sensitivity grid. OOS starts 2025-01-01 and was not used to pick the length or the book.",
        "",
        "Long/flat is equal weight of names above the SMA, otherwise cash. Long/short is the sign, scaled to gross exposure 1. FX and perp verdicts use long/short. Equity verdicts use long/flat. The other book is reported at the same length.",
        "",
        "N per venue is 8 (4 lengths × 2 books). k = 1. DSR is advisory: the lengths are nested on one panel, so they are not eight independent trials. PBO is not computable (no PSA return matrix).",
        "",
    ]
    for venue in payload["venues"]:
        meta = venue["meta"]
        lines.append(f"## {meta['venue']}")
        lines.append("")
        lines.append(
            f"{meta['n_names']} names, {meta['start'][:10]} → {meta['end'][:10]}, "
            f"ann {meta['annualization']}, one-way cost {meta['cost_one_way'] * 1e4:.1f} bps. "
            f"{meta.get('liquidity') or meta.get('note')}"
        )
        lines.append("")
        b = venue["benchmark_ew"]
        lines.append(
            f"Equal-weight buy-and-hold, same cost: IS Sharpe {b['is']['sharpe']:.2f}, "
            f"OOS Sharpe {b['oos']['sharpe']:.2f}."
        )
        lines.append("")
        lines.append("| Book | IS Sharpe | OOS Sharpe | IS CAGR | IS MaxDD | Gross IS Sharpe | Names median IS | Names %>0 |")
        lines.append("|------|-----------|------------|---------|----------|-----------------|-----------------|-----------|")
        for row in venue["books"]:
            nm = row.get("names") or {}
            med = nm.get("median_is_sharpe")
            frac = nm.get("frac_is_sharpe_pos")
            med_s = f"{med:.2f}" if isinstance(med, float) else "—"
            frac_s = f"{frac:.0%}" if isinstance(frac, float) else "—"
            lines.append(
                f"| {row['name']} | {row['is']['sharpe']:.2f} | {row['oos']['sharpe']:.2f} | "
                f"{row['is']['cagr']:.1%} | {row['is']['max_dd']:.1%} | {row['gross_is_sharpe']:.2f} | "
                f"{med_s} | {frac_s} |"
            )
        lines.append("")
        for row in venue["books"]:
            if "dsr" not in row:
                continue
            d = row["sharpe_diagnostics_is"]
            ci = d.get("sharpe_ci95") or [float("nan"), float("nan")]
            hac = row["inference_is"]["mean_net_return"]
            boot = row["inference_is"]["bootstrap"].get("sharpe_annualized") or {}
            reg = row["vs_ew_benchmark_is"]
            null = row["shift_null_is"]
            p95 = null.get("null_is_p95")
            p95_s = f"{p95:.2f}" if isinstance(p95, float) else "n/a"
            pct = row.get("null_percentile_is")
            pct_s = f"{pct:.2f}" if isinstance(pct, float) else "n/a"
            dsr_v = row["dsr"].get("dsr")
            dsr_s = f"{dsr_v:.3f}" if isinstance(dsr_v, float) else "n/a"
            se = d.get("sharpe_se_lo_ann")
            se_s = f"{se:.2f}" if isinstance(se, float) else "n/a"
            lines.append(f"### {row['name']} ({row['role']})")
            lines.append("")
            lines.extend(verdict_lines(row))
            lines.append("")
            lines.append(
                f"IS Sharpe {row['is']['sharpe']:.2f} (Lo SE {se_s}, "
                f"95% CI [{ci[0]:.2f}, {ci[1]:.2f}]), OOS Sharpe {row['oos']['sharpe']:.2f}, "
                f"N {row['n_trials']} / family {row['n_trials']}, k {row['k']}, "
                f"DSR {dsr_s} (advisory_only). "
                f"Null IS p95 {p95_s}, strategy percentile {pct_s}."
            )
            lines.append("")
            lines.append(
                f"HAC mean-return t {hac.get('hac_t'):.2f}, two-sided p {hac.get('hac_p_two_sided'):.3f}. "
                f"Block-bootstrap IS Sharpe 95% CI {boot.get('ci95')}."
            )
            if "error" not in reg:
                lines.append("")
                lines.append(
                    f"Versus equal-weight hold, IS beta {reg['beta']:.2f}, "
                    f"HAC alpha {reg['alpha_ann']:.1%} per year (t {reg['alpha_hac_t']:.2f}, "
                    f"p {reg['alpha_hac_p']:.3f}), beta-hedged Sharpe {reg['hedged_sharpe']:.2f}, "
                    f"R² {reg['r2']:.2f}."
                )
            turn = d.get("turnover_ann_one_way")
            mean_ann = d.get("mean_ann")
            if isinstance(turn, float) and turn > 0 and isinstance(mean_ann, float):
                wipe = mean_ann / turn * 1e4
                lines.append("")
                lines.append(
                    f"IS mean {mean_ann:.1%} per year. The book trades {turn:.2f}× NAV one-way per year. "
                    f"A one-way cost of {wipe:.0f} bps would zero that IS mean. "
                    f"The test uses {row['cost_one_way'] * 1e4:.1f} bps."
                )
            lines.append("")
    lines.append("## How to read an edge")
    lines.append("")
    lines.append(
        "A venue has an edge on the pre-declared book only when the IS Sharpe interval sits above zero, "
        "the HAC mean-return test agrees, OOS Sharpe is positive, and (for long/flat) the HAC alpha versus "
        "the equal-weight hold is positive. DSR below 0.95 means the IS Sharpe is inside what this N can manufacture. "
        "The shift-null percentile is a timing check: a high Sharpe that sits inside the null is a level effect, not a cross."
    )
    lines.append("")
    return "\n".join(lines)


def plot_primary(venues: list[dict[str, Any]], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for venue in venues:
        meta = venue["meta"]
        primary_mode = "long_short" if meta["asset_class"] in {"fx", "crypto"} else "long_flat"
        row = next(b for b in venue["books"] if b["window"] == PRIMARY_N and b["mode"] == primary_mode)
        r = row["_net"].dropna()
        wealth = (1.0 + r).cumprod()
        ax.plot(wealth.index, wealth.values, label=f"{meta['venue']} {primary_mode} SMA200", lw=1.2)
    ax.axvline(OOS_START, color="black", ls="--", lw=0.8, label="OOS 2025-01-01")
    ax.set_yscale("log")
    ax.set_title("SMA200 / close cross, net of the pre-declared cost")
    ax.set_ylabel("Growth of $1 (log)")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    loaders = [
        ("fx", load_fx),
        ("binance", load_binance),
        ("alpaca", load_alpaca),
        ("eodhd", load_eodhd),
    ]
    only = set(sys.argv[1:])
    venues = []
    curves = {}
    for key, loader in loaders:
        if only and key not in only:
            continue
        print(f"loading {key}", flush=True)
        close, ann, cost, meta = loader()
        print(f"  {meta['n_names']} names {meta['start'][:10]} → {meta['end'][:10]}", flush=True)
        venue = run_venue(close, ann, cost, meta)
        for row in venue["books"]:
            if row.get("role") == "primary":
                curves[meta["venue"]] = row["_net"]
                (OUT / f"returns_{meta['venue']}_primary.csv").write_text(
                    row["_net"].dropna().to_csv(header=["net"])
                )
        venues.append(venue)
        print(
            "  primary",
            next(b["name"] for b in venue["books"] if b.get("role") == "primary"),
            "IS",
            f"{next(b['is']['sharpe'] for b in venue['books'] if b.get('role') == 'primary'):.2f}",
            flush=True,
        )

    plot_primary(venues, OUT / "equity_primary.png")
    public = []
    for venue in venues:
        public.append(
            {
                "meta": venue["meta"],
                "n_trials_venue": venue["n_trials_venue"],
                "k": 1,
                "benchmark_ew": venue["benchmark_ew"],
                "books": [_public_book(b) for b in venue["books"]],
            }
        )
    payload = {
        "oos_start": str(OOS_START),
        "windows": list(WINDOWS),
        "primary_window": PRIMARY_N,
        "venues": public,
        "pbo": None,
        "pbo_note": "not computable (no psa_returns_matrix)",
        "trial_accounting": {
            "n_per_venue": 8,
            "k": 1,
            "dsr_status": "advisory_only",
            "selection_bias_warnings": [
                "dsr_not_clean_correction",
                "correlated_sma_windows",
                "battery_not_harness_ledger",
                "family_n_is_within_venue_grid_only",
            ],
        },
    }
    (OUT / "battery_results.json").write_text(json.dumps(payload, indent=2, default=str))
    # selection.json quotes the four primary books together.
    selection = {
        "schema": "sma_close_cross_battery",
        "oos_start_ts": str(OOS_START),
        "k": 1,
        "pbo": None,
        "pbo_note": "not computable (no psa_returns_matrix)",
        "trial_accounting": payload["trial_accounting"],
        "books": [],
    }
    inference = {"books": {}}
    for venue in public:
        for row in venue["books"]:
            if "dsr" not in row:
                continue
            selection["books"].append(
                {
                    "venue": venue["meta"]["venue"],
                    "name": row["name"],
                    "role": row["role"],
                    "n": row["n_trials"],
                    "family_n": row["n_trials"],
                    "k": 1,
                    "is_sharpe": row["is"]["sharpe"],
                    "oos_sharpe": row["oos"]["sharpe"],
                    "sharpe_diagnostics_is": row["sharpe_diagnostics_is"],
                    "dsr": row["dsr"],
                    "dsr_status": "advisory_only",
                    "shift_null_is": row["shift_null_is"],
                    "null_percentile_is": row.get("null_percentile_is"),
                    "vs_ew_benchmark_is": row["vs_ew_benchmark_is"],
                }
            )
            inference["books"][f"{venue['meta']['venue']}|{row['name']}"] = row["inference_is"]
    (OUT / "artifacts").mkdir(exist_ok=True)
    (OUT / "artifacts" / "selection.json").write_text(json.dumps(selection, indent=2, default=str))
    (OUT / "artifacts" / "inference.json").write_text(json.dumps(inference, indent=2, default=str))
    # Report needs private series only for the plot; public payload is enough for the text.
    text_payload = {"venues": public}
    report = render_report(text_payload)
    (OUT / "REPORT.md").write_text(report)
    print(report)
    print(f"Wrote {OUT / 'REPORT.md'}")


if __name__ == "__main__":
    main()
