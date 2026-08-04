#!/usr/bin/env python3
"""Baseline backtest: IS-selected robust params, OOS reported once as holdout."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "runs" / "triangular_pairs" / "code"))

from engine import (  # noqa: E402
    OOS,
    RUN,
    discover_triangles_is,
    full_metrics,
    run_backtest,
    save_json,
    strategy_snapshot,
    yearly_sharpes,
)

# Populated by is_param_sweep.py; fallback to conservative daily defaults.
DEFAULT_PARAMS = {
    "n_triangles": 10,
    "window": 120,
    "entry_z": 2.5,
    "exit_z": 0.75,
    "weight_cap": 0.20,
    "adf_max": 0.05,
}


def load_best_params() -> dict:
    path = RUN / "artifacts" / "is_best_params.json"
    if path.exists():
        data = json.loads(path.read_text())
        best = data.get("best", {})
        return {
            "n_triangles": int(best.get("n_triangles", DEFAULT_PARAMS["n_triangles"])),
            "window": int(best.get("window", DEFAULT_PARAMS["window"])),
            "entry_z": float(best.get("entry_z", DEFAULT_PARAMS["entry_z"])),
            "exit_z": float(best.get("exit_z", DEFAULT_PARAMS["exit_z"])),
            "weight_cap": float(best.get("weight_cap", DEFAULT_PARAMS["weight_cap"])),
            "adf_max": DEFAULT_PARAMS["adf_max"],
        }
    return DEFAULT_PARAMS.copy()


def main() -> None:
    for sub in ("artifacts", "charts", "logs"):
        (RUN / sub).mkdir(parents=True, exist_ok=True)

    params = load_best_params()
    from engine import load_close_panel  # noqa: WPS433

    close = load_close_panel(interval="1d", min_history=500)
    triangles, ranked = discover_triangles_is(
        close,
        oos_start=OOS,
        adf_max=params["adf_max"],
        n_triangles=params["n_triangles"],
        window=params["window"],
    )
    if not triangles:
        raise RuntimeError("No triangles passed IS discovery")

    rets = run_backtest(
        close,
        triangles,
        window=params["window"],
        entry_z=params["entry_z"],
        exit_z=params["exit_z"],
        weight_cap=params["weight_cap"],
    )
    metrics = full_metrics(rets)
    yearly = yearly_sharpes(rets)

    snap = strategy_snapshot(params, triangles)
    metrics["strategy_snapshot"] = snap
    metrics["yearly_sharpes_is"] = yearly
    metrics["triangles"] = [t.key for t in triangles]
    metrics["selection_method"] = "IS-only robust_score (see artifacts/is_best_params.json)"

    save_json(RUN / "artifacts" / "metrics.json", metrics)
    rets.to_csv(RUN / "artifacts" / "daily_returns.csv", header=["return"])

    equity = (1 + rets.fillna(0)).cumprod()
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(equity.index, equity.values, label="Triangular pairs", color="#2563eb")
    ax.axvline(OOS, color="#94a3b8", linestyle="--", linewidth=1, label=f"OOS ({OOS.date()})")
    ax.set_title("Triangular pairs — IS-selected robust config")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(RUN / "charts" / "equity_curve.png", dpi=120)
    plt.close(fig)

    dd = equity / equity.cummax() - 1
    fig2, ax2 = plt.subplots(figsize=(11, 3))
    ax2.fill_between(dd.index, dd.values, 0, alpha=0.4, color="#2563eb")
    ax2.axvline(OOS, color="#94a3b8", linestyle="--", linewidth=1)
    ax2.set_title("Drawdown")
    ax2.grid(alpha=0.3)
    fig2.tight_layout()
    fig2.savefig(RUN / "charts" / "drawdown.png", dpi=120)
    plt.close(fig2)

    spec = json.loads((RUN / "strategy_spec.json").read_text())
    spec["params"] = params
    spec["triangles"] = [t.key for t in triangles]
    (RUN / "strategy_spec.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")

    is_m = metrics["in_sample"]
    oos_m = metrics["out_of_sample"]
    full_m = metrics["full"]
    report = f"""# Triangular pairs — baseline (IS-selected robust config)

## Selection
- Triangle universe: IS discovery only (pre-{OOS.date()})
- Parameters: IS grid search ranked by **robust_score** (Sharpe + yearly stability + drawdown penalty)
- OOS segment: single holdout, **not used for tuning**

## Parameters
```json
{json.dumps(params, indent=2)}
```

## Triangles ({len(triangles)})
{chr(10).join(f'- {t.key}' for t in triangles)}

## Metrics

| Segment | Sharpe | CAGR | MaxDD | Days |
|---------|--------|------|-------|------|
| Full | {full_m['Sharpe']:.3f} | {full_m['CAGR']:.2%} | {full_m['MaxDD']:.2%} | {full_m['n_days']} |
| In-sample | {is_m['Sharpe']:.3f} | {is_m['CAGR']:.2%} | {is_m['MaxDD']:.2%} | {is_m['n_days']} |
| **Out-of-sample** | **{oos_m['Sharpe']:.3f}** | **{oos_m['CAGR']:.2%}** | **{oos_m['MaxDD']:.2%}** | {oos_m['n_days']} |

## IS yearly Sharpe
{chr(10).join(f'- {y}: {s:.2f}' for y, s in sorted(yearly.items()))}

## Caveats
- Multi-leg basket; ~0.29% round-trip cost at default assumptions
- Research only — not live trading advice
"""
    (RUN / "report.md").write_text(report, encoding="utf-8")

    _strategy_snapshot = snap  # noqa: F841 — MCP validation hook

    print("=== Triangular pairs baseline ===")
    print(f"IS  Sharpe: {is_m['Sharpe']:.3f}  MaxDD: {is_m['MaxDD']:.2%}")
    print(f"OOS Sharpe: {oos_m['Sharpe']:.3f}  MaxDD: {oos_m['MaxDD']:.2%}")
    print(f"Triangles: {len(triangles)}")
    print(f"Wrote {RUN / 'artifacts' / 'metrics.json'}")


if __name__ == "__main__":
    main()
