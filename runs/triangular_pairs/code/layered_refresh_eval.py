#!/usr/bin/env python3
"""TQG-compliant layered refresh eval: IS-robust params, compare vs WF-frozen hourly."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
RESEARCH = REPO / "research" / "triangular-pairs-trading"
sys.path.insert(0, str(RESEARCH))
sys.path.insert(0, str(REPO / "runs" / "triangular_pairs" / "code"))

from src.config import OOS_START  # noqa: E402
from src.data import load_close_panel, resample_to_daily  # noqa: E402
from src.layered_refresh import DEFAULT_PARAMS, deploy_date, walk_forward  # noqa: E402

RUN = REPO / "runs" / "triangular_pairs"
OOS = pd.Timestamp(OOS_START, tz="UTC")
LOAD_START = pd.Timestamp("2023-01-01", tz="UTC")

# Hourly equivalents: keep discovery hourly-native; backtest params from IS-robust daily pick.
IS_ROBUST_BT = {
    "entry_z": 2.5,
    "exit_z": 0.5,       # IS-robust daily (was 0.75 in research DEFAULT_PARAMS)
    "weight_cap": 0.15,
    "n_triangles": 10,
    "adf_max": 0.05,
}


def flat_metrics(m: dict) -> dict:
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


def main() -> None:
    t0 = time.time()
    params = {**DEFAULT_PARAMS, **IS_ROBUST_BT}
    out_dir = RUN / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading hourly panel...")
    close = load_close_panel(interval="1h", start=LOAD_START)
    deploy = deploy_date(close, "1h", params["disc_lookback_days"])
    print(f"  shape {close.shape}  deploy={deploy}")

    rows: list[dict] = []

    print("\n=== WF frozen (hourly, IS-robust exit/weight) ===")
    frozen = walk_forward(close, oos_start=OOS, params=params, enable_refresh=False)
    row = {
        "variant": "hourly_wf_frozen",
        "deploy": str(deploy),
        "n_refreshes": 0,
        **flat_metrics(frozen.metrics),
    }
    rows.append(row)
    print(f"  IS {row['is_sharpe']:.3f}  OOS {row['oos_sharpe']:.3f}  Full MaxDD {row['full_max_dd']:.2%}")

    print("\n=== Layered refresh (2-of-3 triggers) ===")
    layered = walk_forward(close, oos_start=OOS, params=params, enable_refresh=True)
    row = {
        "variant": "hourly_layered_refresh",
        "deploy": str(deploy),
        "n_refreshes": len(layered.refresh_events),
        **flat_metrics(layered.metrics),
    }
    rows.append(row)
    print(f"  IS {row['is_sharpe']:.3f}  OOS {row['oos_sharpe']:.3f}  Full MaxDD {row['full_max_dd']:.2%}  refreshes={row['n_refreshes']}")
    for ev in layered.refresh_events:
        fired = [k for k, v in ev.triggers.items() if v]
        print(f"    {ev.date.date()}  {fired}  +{ev.n_added}/-{ev.n_dropped}")

    # Load daily IS-robust baseline for side-by-side
    daily_m = json.loads((RUN / "artifacts" / "metrics.json").read_text())
    rows.append({
        "variant": "daily_is_robust_static",
        "deploy": "2020+",
        "n_refreshes": 0,
        "full_sharpe": daily_m["full"]["Sharpe"],
        "full_cagr": daily_m["full"]["CAGR"],
        "full_max_dd": daily_m["full"]["MaxDD"],
        "is_sharpe": daily_m["in_sample"]["Sharpe"],
        "oos_sharpe": daily_m["out_of_sample"]["Sharpe"],
        "oos_cagr": daily_m["out_of_sample"]["CAGR"],
        "oos_max_dd": daily_m["out_of_sample"]["MaxDD"],
        "n_days": daily_m["full"]["n_days"],
    })

    summary = {
        "params": params,
        "deploy": deploy.isoformat(),
        "oos_start": OOS.isoformat(),
        "selection_note": "Backtest params from IS-robust daily sweep; layered rules not re-tuned on OOS",
        "results": rows,
        "refresh_events": [asdict(ev) for ev in layered.refresh_events],
        "elapsed_sec": time.time() - t0,
    }
    (out_dir / "layered_refresh_eval.json").write_text(json.dumps(summary, indent=2, default=str))
    layered.daily_returns.to_csv(out_dir / "returns_layered_refresh_isrobust_daily.csv", header=["return"])
    frozen.daily_returns.to_csv(out_dir / "returns_wf_frozen_isrobust_daily.csv", header=["return"])

    print("\n=== Comparison ===")
    for r in rows:
        print(
            f"  {r['variant']:28s}  IS {r['is_sharpe']:.3f}  OOS {r['oos_sharpe']:.3f}  "
            f"FullDD {r['full_max_dd']:.2%}  OOSDD {r['oos_max_dd']:.2%}"
        )
    print(f"\nWrote {out_dir / 'layered_refresh_eval.json'}")


if __name__ == "__main__":
    main()
