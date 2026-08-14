#!/usr/bin/env python3
"""Walk-forward backtest: layered refresh rules vs frozen baselines."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backtest import backtest_triangles, compute_metrics
from src.config import OOS_START, RESULTS_DIR
from src.data import load_close_panel, resample_to_daily
from src.discovery import discover_triangles, select_triangles
from src.layered_refresh import DEFAULT_PARAMS, deploy_date, walk_forward
from src.triangles import Triangle

OOS = pd.Timestamp(OOS_START, tz="UTC")
LOAD_START = pd.Timestamp("2023-01-01", tz="UTC")

RESEARCH_FROZEN_KEYS = [
    "SFPUSDT|BTCUSDT|ETHUSDT",
    "SFPUSDT|SOLUSDT|BNBUSDT",
    "SFPUSDT|SOLUSDT|ETHUSDT",
    "SFPUSDT|SOLUSDT|BTCUSDT",
    "SFPUSDT|BTCUSDT|BNBUSDT",
    "ARPAUSDT|SOLUSDT|BNBUSDT",
    "ARPAUSDT|BTCUSDT|ETHUSDT",
    "SFPUSDT|ETHUSDT|BNBUSDT",
    "SPELLUSDT|ETHUSDT|BNBUSDT",
    "ALICEUSDT|ETHUSDT|BNBUSDT",
]
RESEARCH_FROZEN = [Triangle(*k.split("|")) for k in RESEARCH_FROZEN_KEYS]


def _flat_metrics(m: dict) -> dict:
    return {
        "full_sharpe": m["Sharpe"],
        "full_cagr": m["CAGR"],
        "full_max_dd": m["MaxDD"],
        "is_sharpe": m["in_sample"]["Sharpe"],
        "oos_sharpe": m["out_of_sample"]["Sharpe"],
        "oos_cagr": m["out_of_sample"]["CAGR"],
        "oos_max_dd": m["out_of_sample"]["MaxDD"],
        "n_days": m["n_days"],
    }


def research_frozen_at_oos(close: pd.DataFrame, params: dict) -> tuple[list[Triangle], pd.Timestamp]:
    """OOS-calibrated list (365d discovery ending at OOS) — research reference."""
    disc_start = OOS - pd.Timedelta(days=params["disc_lookback_days"])
    ranked = discover_triangles(
        close,
        oos_start=OOS,
        discovery_start=disc_start,
        discovery_end=OOS,
        liquid_top_n=params["liquid_top_n"],
        window=params["disc_window"],
        min_periods=max(params["disc_window"] // 2, 360),
        half_life_cap=60 * 24,
        half_life_norm=120 * 24,
        progress_every=0,
    )
    triangles = select_triangles(ranked, params["n_triangles"], adf_max=params["adf_max"])
    return triangles, OOS


def run_research_frozen_full_panel(close: pd.DataFrame, params: dict) -> dict:
    """Research frozen list on full panel from 2023 (includes pre-selection period)."""
    triangles, _ = research_frozen_at_oos(close, params)
    assets = sorted({a for t in triangles for a in (t.target, t.leg1, t.leg2)})
    res = backtest_triangles(
        close[assets],
        triangles,
        window=params["bt_window"],
        min_periods=params["bt_window"] // 2,
        entry_z=params["entry_z"],
        exit_z=params["exit_z"],
        weight_cap=params["weight_cap"],
    )
    daily = resample_to_daily(res.daily_returns)
    m = compute_metrics(daily, OOS)
    return {
        "variant": "research_frozen_full",
        "deploy": str(LOAD_START),
        "n_refreshes": 0,
        "triangles": [t.key for t in triangles],
        **_flat_metrics(m),
    }


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    t0 = time.time()
    params = dict(DEFAULT_PARAMS)

    print("Loading hourly panel...")
    close = load_close_panel(interval="1h", start=LOAD_START)
    deploy = deploy_date(close, "1h", params["disc_lookback_days"])
    print(f"  shape {close.shape}  deploy={deploy}")

    rows: list[dict] = []

    # 1) Walk-forward frozen: filtered discovery at deploy, never refresh.
    print("\n=== WF frozen (filtered discovery at deploy, no refresh) ===")
    wf_frozen = walk_forward(close, oos_start=OOS, params=params, enable_refresh=False)
    row = {
        "variant": "wf_frozen",
        "deploy": str(deploy),
        "n_refreshes": 0,
        "triangles": [t.key for t in wf_frozen.schedule[0]["triangles"]],
        **_flat_metrics(wf_frozen.metrics),
    }
    rows.append(row)
    print(f"  OOS Sharpe {row['oos_sharpe']:.3f}  Full {row['full_sharpe']:.3f}")

    # 2) Layered refresh walk-forward.
    print("\n=== Layered refresh (2-of-3 triggers, partial update) ===")
    layered = walk_forward(close, oos_start=OOS, params=params, enable_refresh=True)
    row = {
        "variant": "layered_refresh",
        "deploy": str(deploy),
        "n_refreshes": len(layered.refresh_events),
        "triangles": [t.key for t in layered.schedule[-1]["triangles"]],
        **_flat_metrics(layered.metrics),
    }
    rows.append(row)
    print(f"  OOS Sharpe {row['oos_sharpe']:.3f}  Full {row['full_sharpe']:.3f}  Refreshes {row['n_refreshes']}")
    for ev in layered.refresh_events:
        fired = [k for k, v in ev.triggers.items() if v]
        print(f"    {ev.date.date()}  triggers={fired}  +{ev.n_added}/-{ev.n_dropped}")

    # 3) Research frozen (OOS-calibrated, full panel — prior best).
    print("\n=== Research frozen (OOS-calibrated SFP list, full panel) ===")
    research = run_research_frozen_full_panel(close, params)
    rows.append(research)
    print(f"  OOS Sharpe {research['oos_sharpe']:.3f}  Full {research['full_sharpe']:.3f}")

    # 4) Research frozen but only traded from OOS (no pre-selection lookahead).
    print("\n=== Research frozen from OOS only ===")
    research_tris, oos_deploy = research_frozen_at_oos(close, params)
    oos_only = walk_forward(
        close,
        oos_start=OOS,
        params=params,
        enable_refresh=False,
        fixed_triangles=research_tris,
        trade_start=OOS,
    )
    row = {
        "variant": "research_frozen_oos_only",
        "deploy": str(oos_deploy),
        "n_refreshes": 0,
        "triangles": [t.key for t in research_tris],
        **_flat_metrics(oos_only.metrics),
    }
    rows.append(row)
    print(f"  OOS Sharpe {row['oos_sharpe']:.3f}  Full {row['full_sharpe']:.3f}")

    df = pd.DataFrame(rows).sort_values("oos_sharpe", ascending=False)
    df.to_csv(RESULTS_DIR / "layered_refresh_walkforward.csv", index=False)

    layered.daily_returns.to_csv(RESULTS_DIR / "returns_layered_refresh_daily.csv", header=["return"])
    wf_frozen.daily_returns.to_csv(RESULTS_DIR / "returns_wf_frozen_daily.csv", header=["return"])

    events_payload = [
        {
            "date": ev.date.isoformat(),
            "triggers": ev.triggers,
            "n_kept": ev.n_kept,
            "n_added": ev.n_added,
            "n_dropped": ev.n_dropped,
            "before": ev.triangles_before,
            "after": ev.triangles_after,
        }
        for ev in layered.refresh_events
    ]
    summary = {
        "params": params,
        "deploy": deploy.isoformat(),
        "oos_start": OOS.isoformat(),
        "results": rows,
        "refresh_events": events_payload,
        "layered_schedule": [
            {
                "start": e["start"].isoformat(),
                "triangles": [t.key for t in e["triangles"]],
            }
            for e in layered.schedule
        ],
        "elapsed_sec": time.time() - t0,
    }
    (RESULTS_DIR / "layered_refresh_walkforward.json").write_text(json.dumps(summary, indent=2, default=str))

    print("\n=== Results (sorted by OOS Sharpe) ===")
    print(
        df[["variant", "deploy", "n_refreshes", "full_sharpe", "oos_sharpe", "full_max_dd", "oos_max_dd"]].to_string(
            index=False
        )
    )
    print(f"\nWrote {RESULTS_DIR / 'layered_refresh_walkforward.csv'}")


if __name__ == "__main__":
    main()
