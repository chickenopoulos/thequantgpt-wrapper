#!/usr/bin/env python3
"""In-sample PSA for normalized IBS + RSI across assets.

2D grid: RSI oversold threshold x normalized IBS threshold.
Fixed: RSI window=3, IBS window=2, exit=close > prior day high.
Sample: in-sample only (before OOS 2025-01-01).
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import vectorbt as vbt

from tqg_client.market_data import default_annualization, load_market_data

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs" / "pullback_mr_jul2026"
DATA = REPO / "data"

OOS = pd.Timestamp("2025-01-01", tz="UTC")
FEE = 0.00045
SLIPPAGE = 0.0005
POSITION_SIZE = 1.0

RSI_WINDOW = 3
IBS_WINDOW = 2
BASE_OVERSOLD = 10.0
BASE_IBS_THR = 0.45

OVERSOLD_GRID = [5.0, 8.0, 10.0, 12.0, 15.0, 18.0, 20.0]
IBS_THR_GRID = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55]

ASSETS: list[dict[str, str]] = [
    {"symbol": "QQQ", "asset_class": "equity", "label": "QQQ"},
    {"symbol": "SPY", "asset_class": "equity", "label": "SPY"},
    {"symbol": "IWM", "asset_class": "equity", "label": "IWM"},
    {"symbol": "GLD", "asset_class": "equity", "label": "GLD"},
    {"symbol": "BTCUSDT", "asset_class": "crypto", "label": "BTC"},
    {"symbol": "ETHUSDT", "asset_class": "crypto", "label": "ETH"},
]

MIN_TRADES_EQUITY = 50
MIN_TRADES_CRYPTO = 25
STABLE_PF_FLOOR = 1.2
SHARPE_TOLERANCE = 0.05
MIN_STABLE_CELLS = 5

for sub in ("code", "artifacts", "charts", "logs"):
    (RUN / sub).mkdir(parents=True, exist_ok=True)


def _ibs(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    span = (high - low).replace(0, np.nan)
    return ((close - low) / span).clip(0, 1)


def _signals(
    df: pd.DataFrame,
    *,
    oversold: float,
    ibs_thr: float,
) -> tuple[pd.Series, pd.Series]:
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    rsi = vbt.RSI.run(close, window=RSI_WINDOW).rsi
    norm_ibs = _ibs(high, low, close).rolling(IBS_WINDOW).mean()
    entries = ((rsi < oversold) & (norm_ibs < ibs_thr)).fillna(False).astype(bool)
    exits = (close > high.shift(1)).fillna(False).astype(bool)
    return entries, exits


def _is_metrics(
    close: pd.Series,
    entries: pd.Series,
    exits: pd.Series,
    ann: int,
) -> dict[str, float]:
    pf = vbt.Portfolio.from_signals(
        close,
        entries=entries,
        exits=exits,
        size=POSITION_SIZE,
        size_type="percent",
        fees=FEE,
        slippage=SLIPPAGE,
        freq="1D",
    )
    rets = pf.returns().loc[pf.returns().index < OOS]
    r = rets.dropna()
    if r.empty:
        return {
            "Sharpe": 0.0,
            "CAGR": 0.0,
            "MaxDD": 0.0,
            "num_trades": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
        }

    cum = (1 + r).cumprod()
    dd = cum / cum.cummax() - 1
    vol = r.std()
    sharpe = float(np.sqrt(ann) * r.mean() / vol) if vol > 0 else 0.0
    cagr = float((cum.iloc[-1]) ** (ann / len(r)) - 1) if len(r) > 0 else 0.0

    trades = pf.trades.records_readable.copy()
    if not trades.empty:
        entry_ts = pd.to_datetime(trades["Entry Timestamp"], utc=True)
        trades = trades.loc[entry_ts < OOS]
    if trades.empty:
        return {
            "Sharpe": sharpe,
            "CAGR": cagr,
            "MaxDD": float(dd.min()),
            "num_trades": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
        }

    pnls = trades["Return"].astype(float)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_profit = wins.sum() if not wins.empty else 0.0
    gross_loss = abs(losses.sum()) if not losses.empty else 0.0
    pf_val = float(gross_profit / gross_loss) if gross_loss > 0 else 0.0

    return {
        "Sharpe": sharpe,
        "CAGR": cagr,
        "MaxDD": float(dd.min()),
        "num_trades": float(len(trades)),
        "win_rate": float((pnls > 0).mean()),
        "profit_factor": pf_val,
    }


def _analyze_asset(asset: dict[str, str]) -> dict:
    symbol = asset["symbol"]
    min_trades = MIN_TRADES_CRYPTO if asset["asset_class"] == "crypto" else MIN_TRADES_EQUITY

    df, data_source = load_market_data(symbol, data_dir=DATA, interval="1d")
    ann = default_annualization(symbol, asset_class=asset["asset_class"])
    close = df["close"].astype(float)

    rows: list[dict] = []
    for oversold in OVERSOLD_GRID:
        for ibs_thr in IBS_THR_GRID:
            entries, exits = _signals(df, oversold=oversold, ibs_thr=ibs_thr)
            m = _is_metrics(close, entries, exits, ann)
            rows.append(
                {
                    "oversold": oversold,
                    "ibs_thr": ibs_thr,
                    "rsi_window": float(RSI_WINDOW),
                    "ibs_window": float(IBS_WINDOW),
                    **m,
                }
            )

    results = pd.DataFrame(rows)
    baseline_row = results[
        (results["oversold"] == BASE_OVERSOLD) & (results["ibs_thr"] == BASE_IBS_THR)
    ]
    if baseline_row.empty:
        baseline_row = results.iloc[[0]]
    baseline_row = baseline_row.iloc[0]

    best_sharpe = results.loc[results["Sharpe"].idxmax()]
    best_pf = results.loc[results["profit_factor"].idxmax()]

    sharpe_floor = float(baseline_row["Sharpe"]) - SHARPE_TOLERANCE
    stable = results[
        (results["Sharpe"] >= sharpe_floor)
        & (results["profit_factor"] >= STABLE_PF_FLOOR)
        & (results["num_trades"] >= min_trades)
    ].copy()

    stable_center = pd.DataFrame()
    if not stable.empty:
        stable_center = (
            stable.assign(score=stable["Sharpe"] + 0.25 * stable["profit_factor"])
            .sort_values("score", ascending=False)
            .head(1)
        )

    baseline_in_stable = False
    if not stable.empty:
        baseline_in_stable = bool(
            (
                (stable["oversold"] == BASE_OVERSOLD)
                & (stable["ibs_thr"] == BASE_IBS_THR)
            ).any()
        )

    has_representative = (
        len(stable) >= MIN_STABLE_CELLS
        and not stable_center.empty
        and float(stable_center.iloc[0]["Sharpe"]) > 0
    )

    sharpe_grid = results.pivot(index="oversold", columns="ibs_thr", values="Sharpe")
    pf_grid = results.pivot(index="oversold", columns="ibs_thr", values="profit_factor")

    return {
        "symbol": symbol,
        "label": asset["label"],
        "asset_class": asset["asset_class"],
        "data_source": data_source,
        "annualization": ann,
        "min_trades": min_trades,
        "baseline": {
            "oversold": BASE_OVERSOLD,
            "ibs_thr": BASE_IBS_THR,
            "metrics": {
                "Sharpe": float(baseline_row["Sharpe"]),
                "profit_factor": float(baseline_row["profit_factor"]),
                "win_rate": float(baseline_row["win_rate"]),
                "num_trades": float(baseline_row["num_trades"]),
                "CAGR": float(baseline_row["CAGR"]),
                "MaxDD": float(baseline_row["MaxDD"]),
            },
            "in_stable_region": baseline_in_stable,
        },
        "best_sharpe": {
            "oversold": float(best_sharpe["oversold"]),
            "ibs_thr": float(best_sharpe["ibs_thr"]),
            "Sharpe": float(best_sharpe["Sharpe"]),
            "profit_factor": float(best_sharpe["profit_factor"]),
            "num_trades": float(best_sharpe["num_trades"]),
        },
        "best_profit_factor": {
            "oversold": float(best_pf["oversold"]),
            "ibs_thr": float(best_pf["ibs_thr"]),
            "Sharpe": float(best_pf["Sharpe"]),
            "profit_factor": float(best_pf["profit_factor"]),
            "num_trades": float(best_pf["num_trades"]),
        },
        "stable_region": {
            "criteria": (
                f"Sharpe >= baseline - {SHARPE_TOLERANCE}, PF >= {STABLE_PF_FLOOR}, "
                f"trades >= {min_trades}"
            ),
            "num_cells": int(len(stable)),
            "recommended_center": (
                {
                    "oversold": float(stable_center.iloc[0]["oversold"]),
                    "ibs_thr": float(stable_center.iloc[0]["ibs_thr"]),
                    "Sharpe": float(stable_center.iloc[0]["Sharpe"]),
                    "profit_factor": float(stable_center.iloc[0]["profit_factor"]),
                    "num_trades": float(stable_center.iloc[0]["num_trades"]),
                }
                if not stable_center.empty
                else None
            ),
        },
        "has_stable_representative": has_representative,
        "results": rows,
        "sharpe_grid": sharpe_grid,
        "pf_grid": pf_grid,
        "close": close,
    }


asset_results: list[dict] = []
for asset in ASSETS:
    print(f"PSA grid for {asset['symbol']}...")
    asset_results.append(_analyze_asset(asset))

# Combined heatmap figure (Sharpe)
n = len(asset_results)
ncols = 3
nrows = int(np.ceil(n / ncols))
fig, axes = plt.subplots(nrows, ncols, figsize=(4.5 * ncols, 3.8 * nrows))
axes_flat = np.atleast_1d(axes).flatten()
for i, res in enumerate(asset_results):
    ax = axes_flat[i]
    grid = res["sharpe_grid"]
    im = ax.imshow(
        grid.values,
        aspect="auto",
        origin="lower",
        cmap="RdYlGn",
        vmin=max(-0.5, np.nanmin(grid.values)),
        vmax=max(0.5, np.nanmax(grid.values)),
    )
    ax.set_title(
        f"{res['label']} IS Sharpe"
        + (" ✓" if res["has_stable_representative"] else " ✗"),
        fontsize=10,
    )
    ax.set_xticks(range(len(IBS_THR_GRID)))
    ax.set_xticklabels([f"{x:.2f}" for x in IBS_THR_GRID], rotation=45, fontsize=7)
    ax.set_yticks(range(len(OVERSOLD_GRID)))
    ax.set_yticklabels([f"{int(x)}" for x in OVERSOLD_GRID], fontsize=7)
    ax.set_xlabel("ibs_thr")
    ax.set_ylabel("oversold")
    if BASE_OVERSOLD in OVERSOLD_GRID and BASE_IBS_THR in IBS_THR_GRID:
        bx = IBS_THR_GRID.index(BASE_IBS_THR)
        by = OVERSOLD_GRID.index(BASE_OVERSOLD)
        ax.scatter([bx], [by], s=80, edgecolors="black", facecolors="none", linewidths=1.5)
    plt.colorbar(im, ax=ax, fraction=0.046)

for j in range(len(asset_results), len(axes_flat)):
    axes_flat[j].axis("off")

fig.suptitle("Normalized IBS + RSI PSA — in-sample Sharpe by asset", fontsize=12)
fig.tight_layout()
fig.savefig(RUN / "charts" / "psa_ibs_heatmap.png", dpi=120)
plt.close(fig)

# Per-asset PF heatmaps
for res in asset_results:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, grid, title in [
        (axes[0], res["sharpe_grid"], "Sharpe"),
        (axes[1], res["pf_grid"], "Profit factor"),
    ]:
        vals = grid.values
        im = ax.imshow(
            vals,
            aspect="auto",
            origin="lower",
            cmap="RdYlGn",
            vmin=np.nanmin(vals) if title == "Sharpe" else 0.0,
            vmax=np.nanmax(vals),
        )
        ax.set_title(title)
        ax.set_xticks(range(len(IBS_THR_GRID)))
        ax.set_xticklabels([f"{x:.2f}" for x in IBS_THR_GRID], rotation=45)
        ax.set_yticks(range(len(OVERSOLD_GRID)))
        ax.set_yticklabels([f"{int(x)}" for x in OVERSOLD_GRID])
        ax.set_xlabel("ibs_thr")
        ax.set_ylabel("oversold")
        plt.colorbar(im, ax=ax, fraction=0.046)
        if BASE_OVERSOLD in OVERSOLD_GRID and BASE_IBS_THR in IBS_THR_GRID:
            bx = IBS_THR_GRID.index(BASE_IBS_THR)
            by = OVERSOLD_GRID.index(BASE_OVERSOLD)
            ax.scatter([bx], [by], s=100, edgecolors="black", facecolors="none", linewidths=2)
    sym = res["symbol"].lower()
    fig.suptitle(f"{res['label']} PSA (in-sample)")
    fig.tight_layout()
    fig.savefig(RUN / "charts" / f"psa_ibs_{sym}_heatmap.png", dpi=120)
    plt.close(fig)

summary_assets = []
for res in asset_results:
    summary_assets.append(
        {
            k: v
            for k, v in res.items()
            if k not in {"results", "sharpe_grid", "pf_grid", "close"}
        }
    )

summary = {
    "test": "parameter_sensitivity",
    "sample": "in_sample",
    "oos_start_ts": str(OOS),
    "strategy": "normalized_ibs_rsi",
    "fixed_params": {
        "rsi_window": RSI_WINDOW,
        "ibs_window": IBS_WINDOW,
        "exit": "close > prior day high",
        "position_size": POSITION_SIZE,
    },
    "grid": {"oversold": OVERSOLD_GRID, "ibs_thr": IBS_THR_GRID},
    "rank_metric": "Sharpe",
    "baseline_params": {"oversold": BASE_OVERSOLD, "ibs_thr": BASE_IBS_THR},
    "assets": summary_assets,
    "stable_count": sum(1 for a in summary_assets if a["has_stable_representative"]),
}
(RUN / "artifacts" / "psa_ibs_summary.json").write_text(
    json.dumps(
        {
            **summary,
            "grid_results": {a["symbol"]: a["results"] for a in asset_results},
        },
        indent=2,
        default=str,
    )
    + "\n",
    encoding="utf-8",
)

# Validator expects top-level pf from baseline QQQ params
qqq_df, _ = load_market_data("QQQ", data_dir=DATA, interval="1d")
entries, exits = _signals(qqq_df, oversold=BASE_OVERSOLD, ibs_thr=BASE_IBS_THR)
pf = vbt.Portfolio.from_signals(
    qqq_df["close"].astype(float),
    entries=entries,
    exits=exits,
    size=POSITION_SIZE,
    size_type="percent",
    fees=FEE,
    slippage=SLIPPAGE,
    freq="1D",
)

report_lines = [
    "# PSA — normalized IBS + RSI (cross-asset)",
    "",
    f"**Run:** pullback_mr_jul2026  ",
    f"**Sample:** in-sample only (before {OOS.date()})  ",
    f"**Grid:** oversold {OVERSOLD_GRID} × ibs_thr {IBS_THR_GRID}  ",
    f"**Stability:** Sharpe ≥ baseline−{SHARPE_TOLERANCE}, PF ≥ {STABLE_PF_FLOOR}, "
    f"≥{MIN_TRADES_EQUITY} equity / ≥{MIN_TRADES_CRYPTO} crypto trades, ≥{MIN_STABLE_CELLS} plateau cells",
    "",
    "## Stable representative per asset",
    "",
    "| Asset | Stable? | Baseline in plateau? | Plateau cells | Rec. oversold | Rec. IBS | Rec. Sharpe | Rec. PF |",
    "|-------|---------|----------------------|---------------|---------------|----------|-------------|---------|",
]
for a in summary_assets:
    rec = a["stable_region"]["recommended_center"]
    rec_os = f"{rec['oversold']:.0f}" if rec else "—"
    rec_ibs = f"{rec['ibs_thr']:.2f}" if rec else "—"
    rec_sh = f"{rec['Sharpe']:.2f}" if rec else "—"
    rec_pf = f"{rec['profit_factor']:.2f}" if rec else "—"
    report_lines.append(
        f"| {a['label']} | {'Yes' if a['has_stable_representative'] else 'No'} | "
        f"{'Yes' if a['baseline']['in_stable_region'] else 'No'} | {a['stable_region']['num_cells']} | "
        f"{rec_os} | {rec_ibs} | {rec_sh} | {rec_pf} |"
    )

report_lines.extend(
    [
        "",
        "## Baseline params (oversold=10, ibs_thr=0.45) in-sample",
        "",
        "| Asset | Sharpe | PF | Trades | Win% | CAGR |",
        "|-------|--------|-----|--------|------|------|",
    ]
)
for a in summary_assets:
    m = a["baseline"]["metrics"]
    report_lines.append(
        f"| {a['label']} | {m['Sharpe']:.2f} | {m['profit_factor']:.2f} | "
        f"{m['num_trades']:.0f} | {m['win_rate']*100:.0f}% | {m['CAGR']*100:.1f}% |"
    )

report_lines.extend(
    [
        "",
        "Charts: `charts/psa_ibs_heatmap.png`, `charts/psa_ibs_<symbol>_heatmap.png`",
        "",
    ]
)
(RUN / "report_psa_ibs.md").write_text("\n".join(report_lines), encoding="utf-8")

print(f"PSA complete: {summary['stable_count']}/{len(ASSETS)} assets with stable representative")
for a in summary_assets:
    flag = "STABLE" if a["has_stable_representative"] else "UNSTABLE"
    print(
        f"  {a['label']}: {flag} — plateau={a['stable_region']['num_cells']} cells, "
        f"baseline Sharpe={a['baseline']['metrics']['Sharpe']:.2f}"
    )
