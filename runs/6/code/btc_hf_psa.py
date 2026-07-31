#!/usr/bin/env python3
"""In-sample PSA for run 6 locked HF ensemble (4 sleeves).

Sample: pre-2025-01-01 only. Reuses baseline signal logic; varies named params only.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs" / "6"
sys.path.insert(0, str(REPO / "runs" / "6" / "code"))
sys.path.insert(0, str(REPO / "runs" / "5" / "code"))

from btc_all_providers_data import load_all_features  # noqa: E402
from btc_all_providers_ensemble import BUILDERS, returns_from_position  # noqa: E402
from btc_hf_data import build_all_features  # noqa: E402
from btc_hf_ensemble import OOS, ANN_MAP, eval_r, lag, trail_lo  # noqa: E402
from tqg_client.strategy_sweep_core import LAG  # noqa: E402

ANN = 365
SHARPE_TOL = 0.05
MIN_STABLE_CELLS = 3


@dataclass
class SleevePSA:
    id: str
    name: str
    family: str
    baseline_params: dict
    grid: dict[str, list]
    min_trades: int = 5


SLEEVES: list[SleevePSA] = [
    SleevePSA(
        "daily_S1",
        "Binance net flow quantile + 200DMA gate",
        "exchange_flow",
        {"key": "talos_FlowNetBNBUSD", "q_ent": 0.05, "q_ex": 0.85, "gate": True},
        {"q_ent": [0.03, 0.05, 0.07, 0.10, 0.15], "q_ex": [0.75, 0.80, 0.85, 0.90, 0.95]},
        min_trades=20,
    ),
    SleevePSA(
        "daily_S4",
        "Short liquidation spike fade",
        "liquidation_fade",
        {"key": "cg_short_liq", "q": 0.97, "hold": 5},
        {"q": [0.90, 0.93, 0.95, 0.97, 0.99], "hold": [3, 5, 7, 10, 14]},
        min_trades=8,
    ),
    SleevePSA(
        "rsi_lo_8h_20_0.08",
        "RSI LO trail (8h)",
        "rsi_lo",
        {"rw": 20, "ent": 32, "tma": 100, "trail": 0.08},
        {"ent": [28, 30, 32, 35, 38], "trail": [0.04, 0.05, 0.06, 0.08, 0.10]},
        min_trades=3,
    ),
    SleevePSA(
        "vspike_8h_96",
        "Volume spike fade (8h)",
        "vol_spike",
        {"vw": 96, "hold": 8, "drop": 0.025, "vr_thr": 2.0},
        {"vw": [48, 72, 96, 120, 144], "hold": [4, 6, 8, 10, 12]},
        min_trades=15,
    ),
]


def is_metrics_daily(close: pd.Series, pos: pd.Series) -> dict:
    rets = returns_from_position(close, pos)
    r = rets.loc[rets.index < OOS].dropna()
    if len(r) < 20 or r.std() == 0:
        return {"Sharpe": 0.0, "MaxDD": 0.0, "num_trades": 0}
    sh = float(np.sqrt(ANN) * r.mean() / r.std())
    cum = (1 + r).cumprod()
    dd = float((cum / cum.cummax() - 1).min())
    is_pos = pos.loc[pos.index < OOS]
    trades = int(is_pos.diff().abs().fillna(0).gt(0).sum())
    return {"Sharpe": sh, "MaxDD": dd, "num_trades": trades}


def build_rsi_lo_8h(f: dict, close: np.ndarray, params: dict) -> np.ndarray:
    c = np.roll(close, LAG)
    c[:LAG] = np.nan
    rsi = f[f"rsi{params['rw']}"].to_numpy()
    ma = f[f"ma{params['tma']}"].to_numpy()
    e = lag((c > ma) & (rsi < params["ent"]))
    return trail_lo(close, e, params["trail"])


def build_vspike_8h(f: dict, close: np.ndarray, vol: np.ndarray, params: dict) -> np.ndarray:
    vw = int(params["vw"])
    hold = int(params["hold"])
    vol_s = pd.Series(vol)
    vr = (vol_s / vol_s.rolling(vw).mean().replace(0, np.nan)).shift(LAG).to_numpy()
    ret = np.zeros(len(close))
    ret[1:] = close[1:] / close[:-1] - 1
    rl = np.roll(ret, LAG)
    rl[:LAG] = 0
    e = lag((vr > params.get("vr_thr", 2.0)) & (rl < -params.get("drop", 0.025)))
    pos = np.zeros(len(close))
    hl = 0
    for i in range(len(close)):
        if hl > 0:
            hl -= 1
            pos[i] = 1.0
        elif e[i]:
            pos[i] = 1.0
            hl = hold - 1
    return pos


def is_metrics_hf(close: np.ndarray, idx: pd.DatetimeIndex, pos: np.ndarray, ann: int) -> dict:
    m = eval_r(close, pos, idx, ann)
    r = m["returns"]
    is_r = r.loc[r.index < OOS]
    if len(is_r) < 20 or is_r.std() == 0:
        return {"Sharpe": 0.0, "MaxDD": 0.0, "num_trades": 0}
    sh = float(np.sqrt(ann) * is_r.mean() / is_r.std())
    cum = (1 + is_r).cumprod()
    dd = float((cum / cum.cummax() - 1).min())
    pos_s = pd.Series(pos, index=idx)
    trades = int(pos_s.loc[pos_s.index < OOS].diff().abs().fillna(0).gt(0).sum())
    return {"Sharpe": sh, "MaxDD": dd, "num_trades": trades}


def run_grid(spec: SleevePSA, metrics_fn, build_fn) -> dict:
    keys = list(spec.grid.keys())
    baseline = dict(spec.baseline_params)
    rows: list[dict] = []

    for v0 in spec.grid[keys[0]]:
        for v1 in spec.grid[keys[1]]:
            params = dict(baseline)
            params[keys[0]] = v0
            params[keys[1]] = v1
            m = build_fn(params)
            rows.append({keys[0]: v0, keys[1]: v1, **m})

    baseline_row = next(
        (r for r in rows if r[keys[0]] == baseline[keys[0]] and r[keys[1]] == baseline[keys[1]]),
        rows[0],
    )
    b_sh = baseline_row["Sharpe"]
    stable = [r for r in rows if r["Sharpe"] >= b_sh - SHARPE_TOL and r["num_trades"] >= spec.min_trades]
    rep = max(stable, key=lambda r: r["Sharpe"]) if stable else None

    sharpe_mat = pd.DataFrame(index=spec.grid[keys[0]], columns=spec.grid[keys[1]], dtype=float)
    for r in rows:
        sharpe_mat.loc[r[keys[0]], r[keys[1]]] = r["Sharpe"]

    return {
        "id": spec.id,
        "family": spec.family,
        "name": spec.name,
        "baseline_params": {k: baseline[k] for k in keys},
        "baseline_is": {k: baseline_row[k] for k in ("Sharpe", "MaxDD", "num_trades")},
        "grid_axes": spec.grid,
        "grid_cells": len(rows),
        "stable_cells": len(stable),
        "stable_status": "STABLE" if len(stable) >= MIN_STABLE_CELLS else "NO_STABLE",
        "representative_params": (
            {keys[0]: rep[keys[0]], keys[1]: rep[keys[1]], "Sharpe": rep["Sharpe"], "MaxDD": rep["MaxDD"]}
            if rep
            else None
        ),
        "sharpe_tolerance": SHARPE_TOL,
        "min_trades": spec.min_trades,
        "results": rows,
        "sharpe_matrix": sharpe_mat,
        "x_key": keys[1],
        "y_key": keys[0],
    }


def plot_heatmap(psa: dict, path: Path) -> None:
    mat = psa["sharpe_matrix"]
    fig, ax = plt.subplots(figsize=(6, 5))
    vals = mat.values.astype(float)
    im = ax.imshow(
        vals,
        aspect="auto",
        origin="lower",
        cmap="RdYlGn",
        vmin=max(-0.5, np.nanmin(vals)),
        vmax=max(0.5, np.nanmax(vals)),
    )
    ax.set_title(f"{psa['id']} IS Sharpe PSA\n{psa['name'][:50]}")
    ax.set_xticks(range(len(mat.columns)))
    ax.set_xticklabels([str(c) for c in mat.columns], rotation=45)
    ax.set_yticks(range(len(mat.index)))
    ax.set_yticklabels([str(i) for i in mat.index])
    ax.set_xlabel(psa["x_key"])
    ax.set_ylabel(psa["y_key"])
    plt.colorbar(im, ax=ax, fraction=0.046)
    bp = psa["baseline_params"]
    try:
        xi = list(mat.columns).index(bp[psa["x_key"]])
        yi = list(mat.index).index(bp[psa["y_key"]])
        ax.scatter([xi], [yi], s=120, edgecolors="black", facecolors="none", linewidths=2)
    except ValueError:
        pass
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main() -> None:
    for sub in ("artifacts", "charts", "logs"):
        (RUN / sub).mkdir(parents=True, exist_ok=True)

    # Daily sleeves
    _, f_daily, meta = load_all_features()
    close_d = f_daily["close"]

    # 8h HF context
    df8, f8, _ = build_all_features("8h")
    close8 = df8["close"].to_numpy()
    vol8 = df8["volume"].to_numpy()
    idx8 = df8.index
    ann8 = ANN_MAP["8h"]

    results: list[dict] = []
    psa_objs: list[dict] = []

    for spec in SLEEVES:
        if spec.id == "daily_S1":
            def build(p):
                pos = BUILDERS["exchange_flow"](close_d, f_daily, p)
                return is_metrics_daily(close_d, pos)

            psa = run_grid(spec, None, build)
        elif spec.id == "daily_S4":
            def build(p):
                pos = BUILDERS["liquidation_fade"](close_d, f_daily, p)
                return is_metrics_daily(close_d, pos)

            psa = run_grid(spec, None, build)
        elif spec.id == "rsi_lo_8h_20_0.08":
            def build(p):
                pos = build_rsi_lo_8h(f8, close8, p)
                return is_metrics_hf(close8, idx8, pos, ann8)

            psa = run_grid(spec, None, build)
        elif spec.id == "vspike_8h_96":
            def build(p):
                pos = build_vspike_8h(f8, close8, vol8, p)
                return is_metrics_hf(close8, idx8, pos, ann8)

            psa = run_grid(spec, None, build)
        else:
            continue

        plot_heatmap(psa, RUN / "charts" / f"psa_{spec.id}_heatmap.png")
        psa_objs.append(psa)
        results.append({k: v for k, v in psa.items() if k != "sharpe_matrix"})

    n_stable = sum(1 for s in results if s["stable_status"] == "STABLE")
    summary = {
        "test": "parameter_sensitivity",
        "sample": "in_sample",
        "oos_start_ts": str(OOS),
        "symbol": "BTCUSDT",
        "ensemble_version": "hf_lowcorr_v2_is_only",
        "sharpe_tolerance": SHARPE_TOL,
        "min_stable_cells": MIN_STABLE_CELLS,
        "sleeves_stable": n_stable,
        "sleeves_total": len(results),
        "strategies": results,
    }
    (RUN / "artifacts" / "psa_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")

    fig, axes = plt.subplots(2, 2, figsize=(11, 9))
    for ax, psa in zip(axes.flatten(), psa_objs):
        mat = psa["sharpe_matrix"]
        im = ax.imshow(mat.values, aspect="auto", origin="lower", cmap="RdYlGn", vmin=-0.5, vmax=2.0)
        ax.set_title(f"{psa['id']} ({psa['stable_status']})")
        plt.colorbar(im, ax=ax, fraction=0.046)
    fig.suptitle("Run 6 HF Ensemble PSA — In-Sample Sharpe Grids")
    fig.tight_layout()
    fig.savefig(RUN / "charts" / "psa_heatmap.png", dpi=120)
    plt.close(fig)

    run_state = json.loads((RUN / "run.json").read_text())
    run_state["last_scope"] = "psa_in_sample"
    completed = run_state.get("completed_steps", [])
    if "psa_in_sample" not in completed:
        completed.append("psa_in_sample")
    run_state["completed_steps"] = completed
    (RUN / "run.json").write_text(json.dumps(run_state, indent=2) + "\n")

    print("=== Run 6 HF Ensemble PSA (in-sample) ===")
    for s in results:
        bp = s["baseline_is"]
        rep = s["representative_params"]
        print(
            f"{s['id']} [{s['stable_status']}] baseline IS Sharpe={bp['Sharpe']:.3f} "
            f"stable_cells={s['stable_cells']}/{s['grid_cells']}"
        )
        if rep:
            print(f"  rep: {s['x_key']}={rep[s['x_key']]}, {s['y_key']}={rep[s['y_key']]} -> Sharpe={rep['Sharpe']:.3f}")
    print(f"\nStable sleeves: {n_stable}/{len(results)}")


if __name__ == "__main__":
    main()
