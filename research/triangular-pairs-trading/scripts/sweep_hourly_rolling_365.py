#!/usr/bin/env python3
"""Sweep 365d lookback × {180d, 365d} refresh on hourly-native strategy."""

from __future__ import annotations

import itertools
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backtest import backtest_triangles, compute_metrics
from src.config import ANCHORS, OOS_START, RESULTS_DIR, profile
from src.data import load_close_panel, resample_to_daily
from src.discovery import discover_triangles, select_triangles
from src.rolling_refresh import backtest_rolling_refresh, build_rolling_schedule, save_schedule
from src.triangles import Triangle

OOS = pd.Timestamp(OOS_START, tz="UTC")
LOAD_START = pd.Timestamp("2023-01-01", tz="UTC")

# Best hourly-native params (frozen baseline).
DISC_LOOKBACK_DAYS = 365
DISC_WINDOW = 720
BT_WINDOW = 1440
ENTRY_Z = 2.5
EXIT_Z = 0.75
WEIGHT_CAP = 0.15
N_TRIANGLES = 10
ADF_MAX = 0.05


def metrics_daily(hourly_returns: pd.Series) -> dict:
    daily = resample_to_daily(hourly_returns)
    return compute_metrics(daily, OOS, ann_factor=365)


def frozen_baseline(close_h: pd.DataFrame) -> dict:
    disc_start = OOS - pd.Timedelta(days=DISC_LOOKBACK_DAYS)
    ranked = discover_triangles(
        close_h,
        oos_start=OOS,
        discovery_start=disc_start,
        discovery_end=OOS,
        liquid_top_n=profile("1h")["liquid_top_n"],
        window=DISC_WINDOW,
        min_periods=max(DISC_WINDOW // 2, 360),
        half_life_cap=60 * 24,
        half_life_norm=120 * 24,
        progress_every=50,
    )
    triangles = select_triangles(ranked, N_TRIANGLES, adf_max=ADF_MAX)
    assets = sorted({a for t in triangles for a in (t.target, t.leg1, t.leg2)})
    r = backtest_triangles(
        close_h[assets],
        triangles,
        window=BT_WINDOW,
        min_periods=BT_WINDOW // 2,
        entry_z=ENTRY_Z,
        exit_z=EXIT_Z,
        weight_cap=WEIGHT_CAP,
    )
    m = metrics_daily(r.daily_returns)
    return {
        "variant": "frozen_365d",
        "refresh_freq": None,
        "sticky": None,
        "n_refreshes": 0,
        "triangles": [t.key for t in triangles],
        **{f"m_{k}": v for k, v in _flat_metrics(m).items()},
    }


def _flat_metrics(m: dict) -> dict:
    return {
        "full_sharpe": m["Sharpe"],
        "full_cagr": m["CAGR"],
        "full_max_dd": m["MaxDD"],
        "is_sharpe": m["in_sample"]["Sharpe"],
        "oos_sharpe": m["out_of_sample"]["Sharpe"],
        "oos_cagr": m["out_of_sample"]["CAGR"],
        "oos_max_dd": m["out_of_sample"]["MaxDD"],
    }


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    t0 = time.time()

    print("Loading hourly panel...")
    close_h = load_close_panel(interval="1h", start=LOAD_START)
    print(f"  shape {close_h.shape}")

    rows: list[dict] = []

    print("\n=== Frozen baseline (365d discovery, no refresh) ===")
    base = frozen_baseline(close_h)
    rows.append(base)
    print(f"  OOS Sharpe {base['m_oos_sharpe']:.3f}  Full Sharpe {base['m_full_sharpe']:.3f}")

    for refresh_freq, sticky in itertools.product(["180D", "365D"], [True, False]):
        label = f"refresh_{refresh_freq}_sticky_{sticky}"
        print(f"\n=== {label} (lookback={DISC_LOOKBACK_DAYS}d) ===")
        t1 = time.time()
        sched = build_rolling_schedule(
            close_h,
            ANCHORS,
            interval="1h",
            refresh_freq=refresh_freq,
            lookback_days=DISC_LOOKBACK_DAYS,
            n_triangles=N_TRIANGLES,
            adf_max=ADF_MAX,
            sticky=sticky,
            discovery_window=DISC_WINDOW,
            discovery_min_periods=max(DISC_WINDOW // 2, 360),
        )
        print(f"  schedule: {len(sched)} refresh points ({time.time()-t1:.0f}s)")

        save_schedule(sched, RESULTS_DIR / f"schedule_{label}.json")

        r = backtest_rolling_refresh(
            close_h,
            sched,
            interval="1h",
            entry_z=ENTRY_Z,
            exit_z=EXIT_Z,
            weight_cap=WEIGHT_CAP,
            bt_window=BT_WINDOW,
            bt_min_periods=BT_WINDOW // 2,
        )
        m = metrics_daily(r.daily_returns)
        row = {
            "variant": label,
            "refresh_freq": refresh_freq,
            "sticky": sticky,
            "n_refreshes": len(sched),
            **{f"m_{k}": v for k, v in _flat_metrics(m).items()},
        }
        rows.append(row)
        print(
            f"  OOS Sharpe {row['m_oos_sharpe']:.3f}  "
            f"Full Sharpe {row['m_full_sharpe']:.3f}  "
            f"MaxDD {row['m_full_max_dd']:.1%}"
        )

    df = pd.DataFrame(rows).sort_values("m_oos_sharpe", ascending=False)
    df.to_csv(RESULTS_DIR / "hourly_rolling_365_sweep.csv", index=False)

    summary = {
        "params": {
            "disc_lookback_days": DISC_LOOKBACK_DAYS,
            "disc_window": DISC_WINDOW,
            "bt_window": BT_WINDOW,
            "entry_z": ENTRY_Z,
            "exit_z": EXIT_Z,
        },
        "results": rows,
        "best_oos": df.iloc[0].to_dict(),
        "elapsed_sec": time.time() - t0,
    }
    (RESULTS_DIR / "hourly_rolling_365_summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print("\n=== Results (sorted by OOS Sharpe) ===")
    print(
        df[
            ["variant", "refresh_freq", "sticky", "n_refreshes",
             "m_full_sharpe", "m_oos_sharpe", "m_full_max_dd", "m_oos_max_dd"]
        ].to_string(index=False)
    )
    print(f"\nWrote {RESULTS_DIR / 'hourly_rolling_365_sweep.csv'}")


if __name__ == "__main__":
    main()
