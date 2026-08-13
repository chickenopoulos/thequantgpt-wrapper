#!/usr/bin/env python3
"""Export equity curves for PSA representative sleeves + ensemble on one chart."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
CODE = REPO / "runs" / "5" / "code"
sys.path.insert(0, str(CODE))

from btc_all_providers_data import load_all_features  # noqa: E402
from btc_all_providers_ensemble import (  # noqa: E402
    BUILDERS,
    OPT_WEIGHTS,
    SELECTED,
    returns_from_position,
)
from btc_all_providers_search import OOS, eval_pos  # noqa: E402

RUN = REPO / "runs" / "5"


def _rep_params_from_psa() -> dict[str, dict]:
    psa = json.loads((RUN / "artifacts" / "psa_summary.json").read_text())
    out: dict[str, dict] = {}
    for s in psa["strategies"]:
        spec = next(x for x in SELECTED if x.id == s["id"])
        params = dict(spec.params)
        rep = s["representative_params"]
        if rep is None:
            continue
        for k, v in rep.items():
            if k not in ("Sharpe", "MaxDD"):
                params[k] = v
        out[s["id"]] = params
    return out


def main() -> None:
    for sub in ("artifacts", "charts", "logs"):
        (RUN / sub).mkdir(parents=True, exist_ok=True)

    rep_params = _rep_params_from_psa()
    _, f, meta = load_all_features()
    close = f["close"]

    equities: dict[str, pd.Series] = {}
    metrics: dict[str, dict] = {}
    positions: dict[str, pd.Series] = {}

    for spec in SELECTED:
        params = rep_params.get(spec.id, spec.params)
        pos = BUILDERS[spec.family](close, f, params)
        rets = returns_from_position(close, pos)
        eq = (1 + rets.fillna(0)).cumprod()
        equities[spec.id] = eq
        positions[spec.id] = pos
        m = eval_pos(close, pos)
        metrics[spec.id] = {
            "params": params,
            "sharpe_full": m["sharpe"],
            "max_dd": m["max_dd"],
            "sharpe_is": m["sharpe_is"],
            "sharpe_oos": m["sharpe_oos"],
            "trades": m["trades"],
        }

    ens_eq = pd.DataFrame(positions).mean(axis=1).clip(-1, 1)
    ens_rets = returns_from_position(close, ens_eq)
    equities["ensemble_eq"] = (1 + ens_rets.fillna(0)).cumprod()
    metrics["ensemble_eq"] = dict(eval_pos(close, ens_eq), params={"method": "equal_weight"})

    ens_opt = sum(positions[k] * OPT_WEIGHTS[k] for k in OPT_WEIGHTS).clip(-1, 1)
    ens_opt_rets = returns_from_position(close, ens_opt)
    equities["ensemble_opt"] = (1 + ens_opt_rets.fillna(0)).cumprod()
    metrics["ensemble_opt"] = dict(eval_pos(close, ens_opt), params={"method": "optimized", "weights": OPT_WEIGHTS})

    bh = close / close.iloc[0]
    equities["buy_hold"] = bh

    export = pd.DataFrame({"time": close.index})
    for label, eq in equities.items():
        export[label] = eq.reindex(close.index).values
    export["sample"] = ["out_of_sample" if t >= OOS else "in_sample" for t in close.index]

    csv_path = RUN / "artifacts" / "ensemble_component_equity_curves.csv"
    export.to_csv(csv_path, index=False)

    # Combined chart — components + equal-weight ensemble
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = plt.cm.tab10(np.linspace(0, 1, 5))
    for i, spec in enumerate(SELECTED):
        eq = equities[spec.id]
        m = metrics[spec.id]
        ax.plot(
            eq.index,
            eq.values,
            color=colors[i],
            alpha=0.75,
            linewidth=1.2,
            label=f"{spec.id} [{spec.provider}] Sharpe={m['sharpe_full']:.2f}",
        )

    ax.plot(
        equities["ensemble_eq"].index,
        equities["ensemble_eq"].values,
        color="black",
        linewidth=2.5,
        label=f"Ensemble (eq) Sharpe={metrics['ensemble_eq']['sharpe']:.2f}",
    )
    ax.plot(
        equities["ensemble_opt"].index,
        equities["ensemble_opt"].values,
        color="black",
        linewidth=2.0,
        linestyle="--",
        alpha=0.7,
        label=f"Ensemble (opt) Sharpe={metrics['ensemble_opt']['sharpe']:.2f}",
    )
    ax.plot(bh.index, bh.values, color="gray", alpha=0.35, linewidth=1.0, label="Buy & hold")
    ax.axvline(OOS, color="red", linestyle="--", alpha=0.6, label="OOS start")
    ax.set_title("BTC Five-Strategy Ensemble — PSA Representative Sleeves + Ensemble")
    ax.set_ylabel("Growth of $1")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    chart_path = RUN / "charts" / "ensemble_component_equity_curves.png"
    fig.savefig(chart_path, dpi=140)
    plt.close(fig)

    # Log-scale variant for readability
    fig2, ax2 = plt.subplots(figsize=(12, 6))
    for i, spec in enumerate(SELECTED):
        ax2.plot(equities[spec.id].index, equities[spec.id].values, color=colors[i], alpha=0.75, linewidth=1.2, label=spec.id)
    ax2.plot(equities["ensemble_eq"].index, equities["ensemble_eq"].values, color="black", linewidth=2.5, label="Ensemble (eq)")
    ax2.set_yscale("log")
    ax2.axvline(OOS, color="red", linestyle="--", alpha=0.6)
    ax2.set_title("BTC Ensemble Components (log scale)")
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(True, alpha=0.25)
    fig2.tight_layout()
    fig2.savefig(RUN / "charts" / "ensemble_component_equity_curves_log.png", dpi=140)
    plt.close(fig2)

    meta_out = {
        "symbol": "BTCUSDT",
        "data_source": meta["source"],
        "oos_start_ts": str(OOS),
        "param_source": "psa_representative",
        "csv": str(csv_path),
        "chart": str(chart_path),
        "components": {
            sid: {
                "name": next(s.name for s in SELECTED if s.id == sid),
                **metrics[sid],
            }
            for sid in [s.id for s in SELECTED]
        },
        "ensemble_equal_weight": metrics["ensemble_eq"],
        "ensemble_optimized": metrics["ensemble_opt"],
    }
    (RUN / "artifacts" / "ensemble_component_equity_meta.json").write_text(
        json.dumps(meta_out, indent=2, default=str) + "\n", encoding="utf-8"
    )

    print("Exported equity curves (PSA representative params):")
    for spec in SELECTED:
        m = metrics[spec.id]
        print(f"  {spec.id} Sharpe={m['sharpe_full']:.2f} DD={m['max_dd']:.1%} params={m['params']}")
    print(f"  ensemble_eq Sharpe={metrics['ensemble_eq']['sharpe']:.2f} DD={metrics['ensemble_eq']['max_dd']:.1%}")
    print(f"  ensemble_opt Sharpe={metrics['ensemble_opt']['sharpe']:.2f} DD={metrics['ensemble_opt']['max_dd']:.1%}")
    print(f"CSV: {csv_path}")
    print(f"Chart: {chart_path}")


if __name__ == "__main__":
    main()
