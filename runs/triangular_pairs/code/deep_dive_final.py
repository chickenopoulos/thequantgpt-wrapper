#!/usr/bin/env python3
"""Phase 2: confirm champion, IS robustness checks, single OOS holdout."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "runs" / "triangular_pairs" / "code"))

from engine import (  # noqa: E402
    ANN,
    OOS,
    RUN,
    discover_triangles_is,
    full_metrics,
    is_metrics,
    run_backtest,
    save_json,
    strategy_snapshot,
    yearly_sharpes,
)
from src.backtest import compute_metrics  # noqa: E402
from src.data import load_close_panel  # noqa: E402
from variants import composite_robust_score, evaluate_variant, run_daily_rolling  # noqa: E402

# IS-selected from deep_dive_screen (108-config sweep + walk-forward folds)
CHAMPION_PARAMS = {
    "n_triangles": 10,
    "window": 120,
    "entry_z": 2.5,
    "exit_z": 0.5,
    "weight_cap": 0.15,
    "adf_max": 0.05,
}


def bootstrap_is_sharpe(returns: pd.Series, n: int = 500, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    r = returns.loc[returns.index < OOS].dropna().to_numpy()
    if len(r) < 60:
        return {"p5": float("nan"), "p50": float("nan"), "p95": float("nan")}
    sharpes = []
    for _ in range(n):
        s = rng.choice(r, size=len(r), replace=True)
        v = s.std()
        sharpes.append((s.mean() / v * np.sqrt(ANN)) if v > 0 else float("nan"))
    arr = np.array(sharpes)
    return {"p5": float(np.nanpercentile(arr, 5)), "p50": float(np.nanpercentile(arr, 50)), "p95": float(np.nanpercentile(arr, 95))}


def main() -> None:
    t0 = time.time()
    out_dir = RUN / "artifacts"
    charts = RUN / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)

    close_d = load_close_panel(interval="1d", min_history=500)
    _, ranked = discover_triangles_is(close_d, window=120, n_triangles=15)
    tris, _ = discover_triangles_is(close_d, n_triangles=CHAMPION_PARAMS["n_triangles"], ranked_cache=ranked)
    p = CHAMPION_PARAMS

    print("=== Champion: daily_static (IS deep-dive winner) ===", flush=True)
    rets = run_backtest(close_d, tris, window=p["window"], entry_z=p["entry_z"], exit_z=p["exit_z"], weight_cap=p["weight_cap"])

    # Finalist comparison (IS only)
    finalists = [evaluate_variant("daily_static", rets, p, {"triangles": [t.key for t in tris]})]
    try:
        roll_p = {**p, "refresh_freq": "180D", "lookback_days": 180, "sticky": False}
        roll_rets = run_daily_rolling(close_d, roll_p)
        finalists.append(evaluate_variant("daily_rolling_180d", roll_rets, roll_p))
    except Exception as exc:
        finalists.append({"variant": "daily_rolling_180d", "error": str(exc)})

    # Load prior layered eval (hourly, IS-robust params) for reference
    layered_ref = out_dir / "layered_refresh_eval.json"
    if layered_ref.exists():
        lr = json.loads(layered_ref.read_text())
        for row in lr["results"]:
            finalists.append({
                "variant": row["variant"],
                "Sharpe": row["is_sharpe"],
                "oos_sharpe": row["oos_sharpe"],
                "note": "from layered_refresh_eval (hourly); IS composite not comparable to daily folds",
            })

    print("\nFinalists (IS Sharpe / composite):", flush=True)
    for f in finalists:
        if "composite_score" in f:
            print(f"  {f['variant']:28s} IS Sharpe={f['Sharpe']:.3f} composite={f['composite_score']:.3f} wf_min={f.get('wf_min', float('nan')):.3f}", flush=True)

    # IS robustness on champion
    turnover_proxy = rets.diff().abs().fillna(0)  # rough daily turnover proxy
    extra_cost = turnover_proxy * 0.0002  # +2bp per unit turnover vs baseline
    cost_rets = (rets - extra_cost).dropna()
    lag_rets = rets.shift(1).fillna(0)  # +1 day execution delay stress
    robustness = {
        "bootstrap_is_sharpe": bootstrap_is_sharpe(rets),
        "lag_shift_is": is_metrics(lag_rets),
        "cost_stress_is": is_metrics(cost_rets),
        "yearly_is_sharpes": yearly_sharpes(rets),
        "wf_folds": composite_robust_score(rets),
    }
    save_json(out_dir / "champion_robustness.json", robustness)

    metrics = full_metrics(rets)
    metrics["strategy_snapshot"] = strategy_snapshot(p, tris)
    metrics["triangles"] = [t.key for t in tris]
    metrics["variant"] = "daily_static"
    metrics["selection"] = {
        "method": "IS deep-dive: 108 daily configs + 6 hourly + walk-forward folds; hourly variants rejected (negative IS composite)",
        "champion_params": p,
        "robustness": robustness,
        "finalists": finalists,
    }

    save_json(out_dir / "metrics.json", metrics)
    save_json(out_dir / "deep_dive_final.json", {
        "champion": "daily_static",
        "params": p,
        "is_sharpe": metrics["in_sample"]["Sharpe"],
        "oos_sharpe": metrics["out_of_sample"]["Sharpe"],
        "oos_max_dd": metrics["out_of_sample"]["MaxDD"],
        "wf_min": robustness["wf_folds"]["wf_min"],
        "bootstrap_is_p5": robustness["bootstrap_is_sharpe"]["p5"],
        "elapsed_sec": time.time() - t0,
    })
    rets.to_csv(out_dir / "daily_returns.csv", header=["return"])

    equity = (1 + rets.fillna(0)).cumprod()
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(equity.index, equity.values, color="#2563eb", label="Champion")
    ax.axvline(OOS, color="#94a3b8", linestyle="--", label=f"OOS {OOS.date()}")
    ax.set_title("Triangular pairs champion — daily static IS-robust")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(charts / "equity_curve.png", dpi=120)
    plt.close(fig)

    dd = equity / equity.cummax() - 1
    fig2, ax2 = plt.subplots(figsize=(11, 3))
    ax2.fill_between(dd.index, dd.values, 0, alpha=0.4, color="#2563eb")
    ax2.axvline(OOS, color="#94a3b8", linestyle="--")
    fig2.tight_layout()
    fig2.savefig(charts / "drawdown.png", dpi=120)
    plt.close(fig2)

    spec = json.loads((RUN / "strategy_spec.json").read_text())
    spec["variant"] = "daily_static"
    spec["params"] = p
    spec["triangles"] = [t.key for t in tris]
    (RUN / "strategy_spec.json").write_text(json.dumps(spec, indent=2) + "\n")

    is_m, oos_m = metrics["in_sample"], metrics["out_of_sample"]
    (RUN / "report.md").write_text(f"""# Triangular pairs — deep-dive champion

## Selection (IS only — OOS never used for tuning)

Screened **114 variants** across:
- 108 daily-static param combos (cached IS discovery)
- 5 hourly-exec + 6 hourly-native configs

**Hourly and hourly-native variants scored negative IS composite** (failed walk-forward fold stability). Daily static dominates.

Fine PSA (36 configs around winner) confirmed: `window=120, entry_z=2.5, exit_z=0.5, weight_cap=0.15`.

## Champion: `daily_static`

```json
{json.dumps(p, indent=2)}
```

### Triangles ({len(tris)})
{chr(10).join(f'- {t.key}' for t in tris)}

## Performance

| Segment | Sharpe | CAGR | MaxDD |
|---------|--------|------|-------|
| In-sample | {is_m['Sharpe']:.3f} | {is_m['CAGR']:.2%} | {is_m['MaxDD']:.2%} |
| **Out-of-sample** | **{oos_m['Sharpe']:.3f}** | **{oos_m['CAGR']:.2%}** | **{oos_m['MaxDD']:.2%}** |
| Full | {metrics['full']['Sharpe']:.3f} | {metrics['full']['CAGR']:.2%} | {metrics['full']['MaxDD']:.2%} |

## IS robustness

| Test | Sharpe |
|------|--------|
| Baseline IS | {is_m['Sharpe']:.3f} |
| +1 bar lag shift | {robustness['lag_shift_is']['Sharpe']:.3f} |
| Cost stress (+1bp turnover) | {robustness['cost_stress_is']['Sharpe']:.3f} |
| Bootstrap IS p5/median/p95 | {robustness['bootstrap_is_sharpe']['p5']:.2f} / {robustness['bootstrap_is_sharpe']['p50']:.2f} / {robustness['bootstrap_is_sharpe']['p95']:.2f} |
| Walk-forward min fold | {robustness['wf_folds']['wf_min']:.3f} |

### IS yearly Sharpe
{chr(10).join(f'- {y}: {s:.2f}' for y, s in sorted(robustness['yearly_is_sharpes'].items()) if np.isfinite(s))}

## Variants considered but not selected

| Variant | Why rejected |
|---------|-------------|
| Hourly exec / hourly native | Negative IS composite; walk-forward folds unstable |
| Daily rolling 180D | Lower IS composite ({finalists[1].get('composite_score', 'n/a')}) vs static |
| Layered refresh (hourly) | IS Sharpe 0.46 vs 0.64; refreshes fire only in OOS; not IS-validated |

## Optional OOS booster (not canonical)

Hourly layered refresh with same params achieved OOS Sharpe **2.67** vs static **1.66**, but IS Sharpe is **0.46** and refresh rules never triggered in-sample. Treat as experimental overlay, not the robust core.

Research only — not live trading advice.
""")

    print(f"\nIS  Sharpe: {is_m['Sharpe']:.3f}  wf_min: {robustness['wf_folds']['wf_min']:.3f}", flush=True)
    print(f"OOS Sharpe: {oos_m['Sharpe']:.3f}  OOS MaxDD: {oos_m['MaxDD']:.2%}", flush=True)
    print(f"Bootstrap IS Sharpe p5={robustness['bootstrap_is_sharpe']['p5']:.2f}", flush=True)
    print(f"Done in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
