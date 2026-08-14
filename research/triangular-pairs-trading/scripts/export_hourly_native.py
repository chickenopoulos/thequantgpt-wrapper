#!/usr/bin/env python3
"""Export equity curve + robustness for best hourly-native system."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_best_hourly_native import BEST
from src.backtest import backtest_triangles, compute_metrics
from src.config import OOS_START, RESULTS_DIR, profile
from src.data import load_close_panel, resample_to_daily
from src.discovery import discover_triangles, select_triangles
from src.triangles import Triangle


def bootstrap_sharpe(returns: pd.Series, ann_factor: int, n: int = 500, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    r = returns.dropna().to_numpy()
    if len(r) < 30:
        return {"p5": np.nan, "p50": np.nan, "p95": np.nan}
    sharpes = []
    for _ in range(n):
        sample = rng.choice(r, size=len(r), replace=True)
        vol = sample.std()
        sharpes.append((sample.mean() / vol * np.sqrt(ann_factor)) if vol > 0 else np.nan)
    arr = np.array(sharpes)
    return {
        "p5": float(np.nanpercentile(arr, 5)),
        "p50": float(np.nanpercentile(arr, 50)),
        "p95": float(np.nanpercentile(arr, 95)),
    }


def load_or_discover_triangles(close: pd.DataFrame, oos: pd.Timestamp) -> list[Triangle]:
    for name in (
        "triangle_discovery_hourly_best.csv",
        "triangle_discovery_hourly_lb365_w720.csv",
    ):
        cache = RESULTS_DIR / name
        if cache.exists():
            ranked = pd.read_csv(cache).sort_values("score", ascending=False)
            filt = ranked[ranked["adf_p"] < BEST["adf_max"]].head(BEST["n_triangles"])
            return [Triangle(r.target, r.leg1, r.leg2) for r in filt.itertuples()]

    prof = profile("1h")
    disc_start = oos - pd.Timedelta(days=BEST["disc_lookback_days"])
    ranked = discover_triangles(
        close,
        oos_start=oos,
        discovery_start=disc_start,
        discovery_end=oos,
        liquid_top_n=prof["liquid_top_n"],
        window=BEST["disc_window"],
        min_periods=max(BEST["disc_window"] // 2, 360),
        half_life_cap=60 * 24,
        half_life_norm=120 * 24,
        progress_every=50,
    )
    out = RESULTS_DIR / "triangle_discovery_hourly_best.csv"
    ranked.to_csv(out, index=False)
    filt = ranked[ranked["adf_p"] < BEST["adf_max"]].head(BEST["n_triangles"])
    return [Triangle(r.target, r.leg1, r.leg2) for r in filt.itertuples()]


def run_variant(
    close: pd.DataFrame,
    triangles: list[Triangle],
    *,
    bt_window: int,
    entry_z: float,
    exit_z: float,
    weight_cap: float,
) -> pd.Series:
    assets = sorted({a for t in triangles for a in (t.target, t.leg1, t.leg2)})
    r = backtest_triangles(
        close[assets],
        triangles,
        window=bt_window,
        min_periods=bt_window // 2,
        entry_z=entry_z,
        exit_z=exit_z,
        weight_cap=weight_cap,
    )
    return r.daily_returns


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    oos = pd.Timestamp(OOS_START, tz="UTC")
    prof = profile("1h")
    load_start = pd.Timestamp(BEST["load_start"], tz="UTC")

    close = load_close_panel(interval="1h", start=load_start)
    triangles = load_or_discover_triangles(close, oos)
    assets = sorted({a for t in triangles for a in (t.target, t.leg1, t.leg2)})

    base = backtest_triangles(
        close[assets],
        triangles,
        window=BEST["bt_window"],
        min_periods=BEST["bt_window"] // 2,
        entry_z=BEST["entry_z"],
        exit_z=BEST["exit_z"],
        weight_cap=BEST["weight_cap"],
    )
    hourly_ret = base.daily_returns
    daily_ret = resample_to_daily(hourly_ret)
    hourly_eq = (1 + hourly_ret).cumprod()
    daily_eq = (1 + daily_ret).cumprod()

    # --- Export equity curves ---
    hourly_eq.to_csv(RESULTS_DIR / "equity_curve_hourly_native_hourly.csv", header=["equity"])
    hourly_ret.to_csv(RESULTS_DIR / "returns_hourly_native_hourly.csv", header=["return"])
    daily_eq.to_csv(RESULTS_DIR / "equity_curve_hourly_native_daily.csv", header=["equity"])
    daily_ret.to_csv(RESULTS_DIR / "returns_hourly_native_daily.csv", header=["return"])

    m_daily = compute_metrics(daily_ret, oos, ann_factor=365)
    m_hourly = compute_metrics(hourly_ret, oos, ann_factor=prof["ann_factor"])

    from scripts.plot_equity_hourly_native import plot_equity

    plot_equity(
        daily_eq,
        RESULTS_DIR / "equity_curve_hourly_native_daily.png",
        oos_start=oos,
        sharpe=m_daily["Sharpe"],
        max_dd=m_daily["MaxDD"],
    )

    findings: dict = {
        "config": BEST,
        "triangles": [t.key for t in triangles],
        "baseline_daily_compounded": m_daily,
        "baseline_hourly": m_hourly,
        "lag_shift_hourly": compute_metrics(hourly_ret.shift(1).fillna(0), oos, ann_factor=prof["ann_factor"]),
        "lag_shift_daily": compute_metrics(daily_ret.shift(1).fillna(0), oos, ann_factor=365),
        "bootstrap_oos_daily": bootstrap_sharpe(daily_ret[daily_ret.index >= oos], 365),
        "bootstrap_oos_hourly": bootstrap_sharpe(hourly_ret[hourly_ret.index >= oos], prof["ann_factor"]),
        "bootstrap_full_daily": bootstrap_sharpe(daily_ret, 365),
    }

    # Yearly (daily-compounded — matches quoted 1.97 Sharpe)
    yearly = []
    for year, grp in daily_ret.groupby(daily_ret.index.year):
        m = compute_metrics(grp, pd.Timestamp(f"{year}-01-01", tz="UTC"), ann_factor=365)
        yearly.append({
            "year": int(year),
            "sharpe": m["Sharpe"],
            "cagr": m["CAGR"],
            "max_dd": m["MaxDD"],
            "n_days": m["n_days"],
        })
    findings["yearly_daily_compounded"] = yearly

    # Parameter sensitivity
    sens = []
    for bt_w, entry_z in [
        (BEST["bt_window"], BEST["entry_z"]),
        (1200, 2.5),
        (1680, 2.5),
        (1440, 2.0),
        (1440, 3.0),
        (1440, 3.5),
    ]:
        ret = run_variant(close, triangles, bt_window=bt_w, entry_z=entry_z, exit_z=BEST["exit_z"], weight_cap=BEST["weight_cap"])
        d = resample_to_daily(ret)
        m = compute_metrics(d, oos, ann_factor=365)
        sens.append({
            "bt_window": bt_w,
            "entry_z": entry_z,
            "full_sharpe": m["Sharpe"],
            "oos_sharpe": m["out_of_sample"]["Sharpe"],
            "max_dd": m["MaxDD"],
        })
    findings["parameter_sensitivity"] = sens

    # Half-sample stability (2023 vs 2024 IS, 2025+ OOS already split)
    half = []
    for label, mask in [
        ("2023", (daily_ret.index.year == 2023)),
        ("2024", (daily_ret.index.year == 2024)),
        ("2025_plus", (daily_ret.index.year >= 2025)),
    ]:
        grp = daily_ret[mask]
        if len(grp) < 20:
            continue
        m = compute_metrics(grp, pd.Timestamp("2099-01-01", tz="UTC"), ann_factor=365)
        half.append({"period": label, "sharpe": m["Sharpe"], "cagr": m["CAGR"], "max_dd": m["MaxDD"], "n_days": m["n_days"]})
    findings["subperiods"] = half

    (RESULTS_DIR / "robustness_hourly_native.json").write_text(json.dumps(findings, indent=2))

    print("=== Equity curves exported ===")
    print(f"  {RESULTS_DIR / 'equity_curve_hourly_native_daily.csv'}  (Sharpe {m_daily['Sharpe']:.3f})")
    print(f"  {RESULTS_DIR / 'equity_curve_hourly_native_daily.png'}")
    print(f"  {RESULTS_DIR / 'equity_curve_hourly_native_hourly.csv'}")
    print("\n=== Robustness (daily-compounded, Sharpe 1.97 variant) ===")
    print(f"Full Sharpe: {m_daily['Sharpe']:.3f}  OOS: {m_daily['out_of_sample']['Sharpe']:.3f}  MaxDD: {m_daily['MaxDD']:.2%}")
    b = findings["bootstrap_oos_daily"]
    print(f"Bootstrap OOS Sharpe: p5={b['p5']:.2f}  median={b['p50']:.2f}  p95={b['p95']:.2f}")
    print("Yearly:")
    for y in yearly:
        print(f"  {y['year']}: Sharpe={y['sharpe']:.2f}  CAGR={y['cagr']:.1%}  MaxDD={y['max_dd']:.1%}")
    print("Parameter sensitivity (OOS Sharpe):")
    for s in sens:
        print(f"  w={s['bt_window']} entry={s['entry_z']}: full={s['full_sharpe']:.2f} oos={s['oos_sharpe']:.2f}")


if __name__ == "__main__":
    main()
