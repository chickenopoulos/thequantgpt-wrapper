#!/usr/bin/env python3
"""Sweep hourly-native triangle discovery vs daily-static baseline."""

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
from src.triangles import Triangle

OOS = pd.Timestamp(OOS_START, tz="UTC")
LOAD_START = pd.Timestamp("2023-01-01", tz="UTC")
PROF_H = profile("1h")

# Discovery grid (IS window before OOS × OLS window in hourly bars).
DISCOVERY_LOOKBACK_DAYS = [90, 180, 365]
DISCOVERY_WINDOWS = [720, 1440]
ADF_MAX = 0.05
N_TRIANGLES = 10

# Backtest grid on hourly bars.
BT_WINDOWS = [720, 1440]
ENTRY_Z = [2.5, 3.0]
EXIT_Z = 0.75
WEIGHT_CAP = 0.15


def load_daily_static_triangles(n: int = 10) -> list[Triangle]:
    ranked = pd.read_csv(RESULTS_DIR / "triangle_discovery.csv").sort_values("score", ascending=False)
    ranked = ranked[ranked["adf_p"] < ADF_MAX].head(n)
    return [Triangle(r.target, r.leg1, r.leg2) for r in ranked.itertuples()]


def backtest_on_hourly(
    close_h: pd.DataFrame,
    triangles: list[Triangle],
    *,
    window: int,
    entry_z: float,
) -> dict:
    assets = sorted({a for t in triangles for a in (t.target, t.leg1, t.leg2)})
    panel = close_h[[c for c in assets if c in close_h.columns]]
    if panel.shape[1] < 3:
        return {"daily_comp_oos": float("nan"), "daily_comp_sharpe": float("nan"), "max_dd": float("nan")}
    r = backtest_triangles(
        panel,
        triangles,
        window=window,
        min_periods=window // 2,
        entry_z=entry_z,
        exit_z=EXIT_Z,
        weight_cap=WEIGHT_CAP,
    )
    daily = resample_to_daily(r.daily_returns)
    m = compute_metrics(daily, OOS, ann_factor=365)
    return {
        "daily_comp_sharpe": m["Sharpe"],
        "daily_comp_oos": m["out_of_sample"]["Sharpe"],
        "daily_comp_oos_cagr": m["out_of_sample"]["CAGR"],
        "daily_comp_oos_dd": m["out_of_sample"]["MaxDD"],
        "max_dd": m["MaxDD"],
        "n_bars": len(r.daily_returns),
    }


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    t0 = time.time()

    close_h = load_close_panel(interval="1h", start=LOAD_START)
    print(f"Loaded hourly panel: {close_h.shape} ({time.time()-t0:.0f}s)")

    rows: list[dict] = []

    # --- Baseline: daily-selected triangles on hourly bars ---
    daily_tris = load_daily_static_triangles(N_TRIANGLES)
    print(f"Baseline daily-static triangles: {len(daily_tris)}")
    for bt_w, entry_z in itertools.product(BT_WINDOWS, ENTRY_Z):
        m = backtest_on_hourly(close_h, daily_tris, window=bt_w, entry_z=entry_z)
        rows.append({
            "source": "daily_static",
            "disc_lookback_days": None,
            "disc_window": None,
            "bt_window": bt_w,
            "entry_z": entry_z,
            "n_triangles": len(daily_tris),
            "top_triangle": daily_tris[0].key if daily_tris else None,
            **m,
        })

    # --- Hourly-native discovery sweep ---
    discovery_cache: dict[tuple[int, int], pd.DataFrame] = {}
    for lookback, disc_w in itertools.product(DISCOVERY_LOOKBACK_DAYS, DISCOVERY_WINDOWS):
        disc_start = OOS - pd.Timedelta(days=lookback)
        key = (lookback, disc_w)
        print(f"\nDiscovering hourly-native: lookback={lookback}d window={disc_w}...")
        t1 = time.time()
        ranked = discover_triangles(
            close_h,
            oos_start=OOS,
            discovery_start=disc_start,
            discovery_end=OOS,
            liquid_top_n=PROF_H["liquid_top_n"],
            window=disc_w,
            min_periods=max(disc_w // 2, 360),
            half_life_cap=60 * 24,
            half_life_norm=120 * 24,
            progress_every=50,
        )
        discovery_cache[key] = ranked
        tag = f"lb{lookback}_w{disc_w}"
        ranked.to_csv(RESULTS_DIR / f"triangle_discovery_hourly_{tag}.csv", index=False)
        print(f"  done in {time.time()-t1:.0f}s, top={ranked.iloc[0]['triangle'] if len(ranked) else 'n/a'}")

        triangles = select_triangles(ranked, N_TRIANGLES, adf_max=ADF_MAX)
        if not triangles:
            print("  no triangles passed ADF filter")
            continue

        for bt_w, entry_z in itertools.product(BT_WINDOWS, ENTRY_Z):
            m = backtest_on_hourly(close_h, triangles, window=bt_w, entry_z=entry_z)
            rows.append({
                "source": "hourly_native",
                "disc_lookback_days": lookback,
                "disc_window": disc_w,
                "bt_window": bt_w,
                "entry_z": entry_z,
                "n_triangles": len(triangles),
                "top_triangle": triangles[0].key,
                **m,
            })

    df = pd.DataFrame(rows).sort_values("daily_comp_oos", ascending=False, na_position="last")
    df.to_csv(RESULTS_DIR / "hourly_native_sweep.csv", index=False)

    best = df.iloc[0].to_dict() if not df.empty else {}
    baseline_best = df[df["source"] == "daily_static"].sort_values("daily_comp_oos", ascending=False).iloc[0]
    native_best = df[df["source"] == "hourly_native"].sort_values("daily_comp_oos", ascending=False)
    native_best_row = native_best.iloc[0].to_dict() if not native_best.empty else {}

    summary = {
        "baseline_daily_static_best": baseline_best.to_dict(),
        "hourly_native_best": native_best_row,
        "top10": df.head(10).to_dict(orient="records"),
        "discovery_configs": len(DISCOVERY_LOOKBACK_DAYS) * len(DISCOVERY_WINDOWS),
        "total_runs": len(df),
        "elapsed_sec": time.time() - t0,
    }
    (RESULTS_DIR / "hourly_native_summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print("\n=== Hourly-native discovery sweep ===")
    print(f"Baseline daily-static best OOS: {baseline_best['daily_comp_oos']:.3f}")
    if native_best_row:
        print(
            f"Hourly-native best OOS:         {native_best_row.get('daily_comp_oos', float('nan')):.3f}  "
            f"(lookback={native_best_row.get('disc_lookback_days')}d "
            f"disc_w={native_best_row.get('disc_window')} "
            f"bt_w={native_best_row.get('bt_window')} "
            f"entry={native_best_row.get('entry_z')})"
        )
    print(f"\nTop 8 configs:")
    print(
        df.head(8)[
            ["source", "disc_lookback_days", "disc_window", "bt_window", "entry_z",
             "daily_comp_oos", "max_dd", "top_triangle"]
        ].to_string(index=False)
    )
    print(f"\nWrote {RESULTS_DIR / 'hourly_native_sweep.csv'}")


if __name__ == "__main__":
    main()
