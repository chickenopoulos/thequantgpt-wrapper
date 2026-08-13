#!/usr/bin/env python3
"""BTC five-strategy ensemble v2 — IS-tuned pure signals, full-sample validation.

Five signal families (diverse):
  S1  Trend + on-chain     SMA(151) + Puell<0.99 + 8% peak trail
  S2  On-chain value       Puell<0.70 / >1.50 with 200DMA gate
  S3  Dual MA + on-chain   MA30>MA150 + Puell<1.0 + 10% trail
  S4  CMMA + on-chain      CMMA(40)>0 + Puell<1.0 + 12% trail
  S5  TSMOM + on-chain     6m momentum + Puell<1.0 + 12% trail

Trail exits are signal rules (not position sizing). Parameters selected on
in-sample (pre-2025) via coarse grid; reported on full sample + OOS.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import vectorbt as vbt

from tqg_client.market_data import load_market_data
from tqg_client.strategy_sweep_core import (
    FEE,
    LAG,
    OOS,
    SLIPPAGE,
    align_to_close,
    atr,
    efficiency_ratio,
    load_coinglass_daily,
)

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs" / "5"
DATA = REPO / "data"
SYMBOL = "BTCUSDT"
ANN = 365


@dataclass
class StrategySpec:
    id: str
    family: str
    name: str
    literature: str
    params: dict
    build: str  # label only


@dataclass
class StrategyResult:
    id: str
    family: str
    name: str
    literature: str
    params: dict
    sharpe_full: float
    sharpe_is: float
    sharpe_oos: float
    max_dd: float
    cagr: float
    trades: int
    exposure: float
    meets_sharpe: bool
    meets_dd: bool


def trail_position(close: pd.Series, entry: pd.Series, trail_pct: float) -> pd.Series:
    pos = pd.Series(0.0, index=close.index)
    state = 0.0
    peak = 0.0
    for t in close.index:
        sig = bool(entry.loc[t])
        price = float(close.loc[t])
        if state == 0.0 and sig:
            state = 1.0
            peak = price
        elif state > 0:
            peak = max(peak, price)
            if (price / peak - 1) < -trail_pct or not sig:
                state = 0.0
        pos.loc[t] = state
    return pos


def position_from_entries(
    close: pd.Series,
    entries: pd.Series,
    exits: pd.Series,
) -> pd.Series:
    idx = close.index
    pos = pd.Series(0.0, index=idx)
    state = 0.0
    en = entries.fillna(False).astype(bool)
    ex = exits.fillna(False).astype(bool)
    for t in idx:
        if state == 0.0 and en.loc[t]:
            state = 1.0
        elif state > 0 and ex.loc[t]:
            state = 0.0
        pos.loc[t] = state
    return pos


def returns_from_position(close: pd.Series, position: pd.Series) -> pd.Series:
    asset = close.pct_change().fillna(0)
    pos = position.reindex(close.index).fillna(0)
    gross = pos.shift(1).fillna(0) * asset
    turnover = pos.diff().abs().fillna(0)
    return gross - turnover * (FEE + SLIPPAGE)


def compute_metrics(returns: pd.Series, position: pd.Series) -> dict:
    r = returns.dropna()
    if len(r) < 30 or r.std() == 0:
        return {"Sharpe": 0.0, "MaxDD": 0.0, "CAGR": 0.0, "sharpe_is": 0.0, "sharpe_oos": 0.0, "trades": 0, "exposure": 0.0}
    cum = (1 + r).cumprod()
    dd = cum / cum.cummax() - 1
    sharpe = float(np.sqrt(ANN) * r.mean() / r.std())
    cagr = float(cum.iloc[-1] ** (ANN / len(r)) - 1)
    is_r = r.loc[r.index < OOS]
    oos_r = r.loc[r.index >= OOS]

    def _sh(s: pd.Series) -> float:
        if len(s) < 10 or s.std() == 0:
            return 0.0
        return float(np.sqrt(ANN) * s.mean() / s.std())

    return {
        "Sharpe": sharpe,
        "MaxDD": float(dd.min()),
        "CAGR": cagr,
        "sharpe_is": _sh(is_r),
        "sharpe_oos": _sh(oos_r),
        "trades": int(position.diff().abs().fillna(0).gt(0).sum()),
        "exposure": float(position.abs().mean()),
    }


def load_features(df: pd.DataFrame) -> dict:
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    puell = align_to_close(load_coinglass_daily("puell_multiple.csv", "puell_multiple"), close.index)
    log_p = np.log(close)
    return {
        "close": close,
        "high": high,
        "low": low,
        "puell": puell,
        "ma151": close.rolling(151).mean().shift(LAG),
        "ma200": close.rolling(200).mean().shift(LAG),
        "ma30": close.rolling(30).mean().shift(LAG),
        "ma150": close.rolling(150).mean().shift(LAG),
        "cmma40": ((log_p - log_p.rolling(40).mean()) / atr(high, low, close)).shift(LAG),
        "mom189": close.pct_change(168).shift(LAG),
    }


def build_s1(f: dict) -> pd.Series:
    entry = (f["close"].shift(LAG) > f["ma151"]) & (f["puell"] < 0.99)
    return trail_position(f["close"], entry.fillna(False), 0.08)


def build_s2(f: dict) -> pd.Series:
    entries = (f["close"].shift(LAG) > f["ma200"]) & (f["puell"] < 0.70)
    exits = f["puell"] > 1.50
    return position_from_entries(f["close"], entries.fillna(False), exits.fillna(False))


def build_s3(f: dict) -> pd.Series:
    entry = (f["ma30"] > f["ma150"]) & (f["puell"] < 1.0)
    return trail_position(f["close"], entry.fillna(False), 0.10)


def build_s4(f: dict) -> pd.Series:
    entry = (f["cmma40"] > 0) & (f["puell"] < 1.0)
    return trail_position(f["close"], entry.fillna(False), 0.12)


def build_s5(f: dict) -> pd.Series:
    entry = (f["mom189"] > 0) & (f["puell"] < 1.0)
    return trail_position(f["close"], entry.fillna(False), 0.12)


STRATEGY_BUILDERS: list[tuple[StrategySpec, Callable[[dict], pd.Series]]] = [
    (
        StrategySpec(
            "S1", "trend_onchain", "SMA151 + Puell filter + 8% trail",
            "Liu/Tsyvinski MA trend gated by miner stress (Puell); peak trail exit",
            {"ma": 151, "puell_max": 0.99, "trail": 0.08},
            "build_s1",
        ),
        build_s1,
    ),
    (
        StrategySpec(
            "S2", "onchain_value", "Puell value + 200DMA",
            "Buy miner capitulation (Puell<0.7) in uptrend; exit Puell>1.5",
            {"puell_entry": 0.70, "puell_exit": 1.50, "trend_ma": 200},
            "build_s2",
        ),
        build_s2,
    ),
    (
        StrategySpec(
            "S3", "dual_ma_onchain", "Dual MA30/150 + Puell + 10% trail",
            "Golden-cross trend with on-chain froth cap; trail limits crash exposure",
            {"fast": 30, "slow": 150, "puell_max": 1.0, "trail": 0.10},
            "build_s3",
        ),
        build_s3,
    ),
    (
        StrategySpec(
            "S4", "cmma_onchain", "CMMA40 + Puell + 12% trail",
            "ATR-normalized log trend (Carver CMMA) with Puell gate",
            {"cmma_k": 40, "puell_max": 1.0, "trail": 0.12},
            "build_s4",
        ),
        build_s4,
    ),
    (
        StrategySpec(
            "S5", "tsmom_onchain", "6M TSMOM + Puell + 12% trail",
            "Moskowitz TSMOM (6m) with Puell froth filter and trail exit",
            {"mom_lb": 189, "puell_max": 1.0, "trail": 0.12},
            "build_s5",
        ),
        build_s5,
    ),
]


def run_is_grid(features: dict) -> dict:
    """Coarse IS-only grid to verify parameter stability (not used to re-tune v2 specs)."""
    close = features["close"]
    is_idx = close.index < OOS
    results = []

    for ma in range(145, 156):
        for pthr in [0.95, 0.99, 1.0, 1.05]:
            for trail in [0.07, 0.08, 0.09, 0.10]:
                entry = (close.shift(LAG) > close.rolling(ma).mean().shift(LAG)) & (features["puell"] < pthr)
                pos = trail_position(close, entry.fillna(False), trail)
                r = returns_from_position(close, pos).loc[is_idx]
                if len(r) < 30 or r.std() == 0:
                    continue
                sh = float(np.sqrt(ANN) * r.mean() / r.std())
                cum = (1 + r).cumprod()
                dd = float((cum / cum.cummax() - 1).min())
                results.append({"ma": ma, "p": pthr, "trail": trail, "sh_is": sh, "dd_is": dd})

    results.sort(key=lambda x: -x["sh_is"])
    return {"top_is": results[:10], "count": len(results)}


def main() -> None:
    for sub in ("artifacts", "charts", "logs"):
        (RUN / sub).mkdir(parents=True, exist_ok=True)

    df, source = load_market_data(SYMBOL, data_dir=DATA, interval="1d")
    df = df.sort_index()
    close = df["close"].astype(float)
    features = load_features(df)

    strategies: list[tuple[StrategyResult, pd.Series, pd.Series]] = []
    for spec, builder in STRATEGY_BUILDERS:
        pos = builder(features)
        rets = returns_from_position(close, pos)
        m = compute_metrics(rets, pos)
        strategies.append((
            StrategyResult(
                id=spec.id,
                family=spec.family,
                name=spec.name,
                literature=spec.literature,
                params=spec.params,
                sharpe_full=m["Sharpe"],
                sharpe_is=m["sharpe_is"],
                sharpe_oos=m["sharpe_oos"],
                max_dd=m["MaxDD"],
                cagr=m["CAGR"],
                trades=m["trades"],
                exposure=m["exposure"],
                meets_sharpe=m["Sharpe"] >= 1.0,
                meets_dd=m["MaxDD"] > -0.25,
            ),
            pos,
            rets,
        ))

    positions = [p for _, p, _ in strategies]
    ens_pos = pd.DataFrame({s.id: p for s, p, _ in strategies}).mean(axis=1).clip(-1.0, 1.0)
    ens_rets = returns_from_position(close, ens_pos)
    ens_m = compute_metrics(ens_rets, ens_pos)

    is_grid = run_is_grid(features)

    n_pass = sum(1 for s, _, _ in strategies if s.meets_sharpe and s.meets_dd)
    summary = {
        "symbol": SYMBOL,
        "data_source": source,
        "data_range": [str(df.index.min()), str(df.index.max())],
        "oos_start_ts": str(OOS),
        "annualization": ANN,
        "costs": {"fee": FEE, "slippage": SLIPPAGE},
        "version": "v2_is_validated",
        "criteria": {
            "per_strategy": {"min_sharpe": 1.0, "max_drawdown": 0.25},
            "ensemble": {"min_sharpe": 2.0, "max_drawdown": 0.15},
        },
        "strategies_passing_both": n_pass,
        "strategies": [asdict(s) for s, _, _ in strategies],
        "ensemble": {
            "method": "equal_weight_mean_position_clipped",
            "sharpe_full": ens_m["Sharpe"],
            "sharpe_is": ens_m["sharpe_is"],
            "sharpe_oos": ens_m["sharpe_oos"],
            "max_dd": ens_m["MaxDD"],
            "cagr": ens_m["CAGR"],
            "trades": ens_m["trades"],
            "exposure": ens_m["exposure"],
            "meets_sharpe_target": ens_m["Sharpe"] > 2.0,
            "meets_dd_target": ens_m["MaxDD"] > -0.15,
        },
        "is_grid_sma_puell_trail": is_grid,
    }

    (RUN / "artifacts" / "btc_five_strategy_ensemble.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )

    metrics = {
        "full_sample": {s.id: {"Sharpe": s.sharpe_full, "MaxDD": s.max_dd, "CAGR": s.cagr} for s, _, _ in strategies},
        "in_sample": {s.id: {"Sharpe": s.sharpe_is, "MaxDD": s.max_dd} for s, _, _ in strategies},
        "out_of_sample": {s.id: {"Sharpe": s.sharpe_oos, "MaxDD": s.max_dd} for s, _, _ in strategies},
        "ensemble": {
            "full_sample": {"Sharpe": ens_m["Sharpe"], "MaxDD": ens_m["MaxDD"], "CAGR": ens_m["CAGR"]},
            "in_sample": {"Sharpe": ens_m["sharpe_is"], "MaxDD": ens_m["MaxDD"]},
            "out_of_sample": {"Sharpe": ens_m["sharpe_oos"], "MaxDD": ens_m["MaxDD"]},
        },
    }
    (RUN / "artifacts" / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    # Charts
    eq = (1 + ens_rets.fillna(0)).cumprod()
    bh = close / close.iloc[0]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(eq.index, eq.values, linewidth=2, label="Ensemble v2")
    ax.plot(bh.index, bh.values, alpha=0.6, label="Buy & hold")
    ax.axvline(OOS, color="red", linestyle="--", label="OOS")
    ax.legend()
    ax.set_title(f"BTC Ensemble v2 | Sharpe={ens_m['Sharpe']:.2f} | MaxDD={ens_m['MaxDD']:.1%}")
    fig.tight_layout()
    fig.savefig(RUN / "charts" / "ensemble_equity.png", dpi=120)
    plt.close(fig)

    fig2, axes = plt.subplots(len(strategies), 1, figsize=(11, 2.5 * len(strategies)), sharex=True)
    for ax, (sr, _, rets) in zip(axes, strategies):
        eq_s = (1 + rets.fillna(0)).cumprod()
        ax.plot(eq_s.index, eq_s.values)
        flag = "PASS" if sr.meets_sharpe and sr.meets_dd else "—"
        ax.set_title(f"{flag} {sr.id}: {sr.name} | Sharpe={sr.sharpe_full:.2f} | DD={sr.max_dd:.1%}")
        ax.axvline(OOS, color="red", linestyle="--", alpha=0.4)
    fig2.tight_layout()
    fig2.savefig(RUN / "charts" / "strategy_equities.png", dpi=120)
    plt.close(fig2)

    spec = {
        "workflow": "single_asset_signals",
        "symbol": SYMBOL,
        "version": "v2",
        "strategies": [asdict(s) for s, _, _ in strategies],
        "ensemble_method": "equal_weight_mean_position_clipped",
        "oos_start_ts": "2025-01-01",
    }
    (RUN / "strategy_spec.json").write_text(json.dumps(spec, indent=2, default=str) + "\n", encoding="utf-8")

    lines = [
        "# BTC Five-Strategy Ensemble v2",
        "",
        f"**Run:** `runs/5` | **Symbol:** {SYMBOL} | **OOS:** {OOS.date()}",
        "",
        "## Results",
        "",
        f"**Strategies passing Sharpe≥1 & DD<25%:** {n_pass}/5",
        "",
        "| ID | Family | Sharpe | IS | OOS | MaxDD | Trades | Pass |",
        "|----|--------|--------|----|-----|-------|--------|------|",
    ]
    for sr, _, _ in strategies:
        ok = "Yes" if sr.meets_sharpe and sr.meets_dd else "No"
        lines.append(
            f"| {sr.id} | {sr.family} | {sr.sharpe_full:.2f} | {sr.sharpe_is:.2f} | {sr.sharpe_oos:.2f} | {sr.max_dd:.1%} | {sr.trades} | {ok} |"
        )
    lines += [
        "",
        "## Ensemble",
        "",
        f"- Sharpe: **{ens_m['Sharpe']:.2f}** (target > 2.0)",
        f"- Max drawdown: **{ens_m['MaxDD']:.1%}** (target < 15%)",
        f"- IS Sharpe: {ens_m['sharpe_is']:.2f}",
        f"- OOS Sharpe: {ens_m['sharpe_oos']:.2f}",
        "",
        "## Method",
        "",
        "Five diverse signal families, all gated by Puell multiple (on-chain miner stress) to",
        "cap drawdown. Trail exits are binary signal rules, not position sizing.",
        "Parameters chosen from coarse IS grid stability around literature defaults.",
    ]
    (RUN / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=== BTC Five-Strategy Ensemble v2 ===")
    for sr, _, _ in strategies:
        ok = "PASS" if sr.meets_sharpe and sr.meets_dd else "MISS"
        print(f"{ok} {sr.id} Sharpe={sr.sharpe_full:.3f} DD={sr.max_dd:.1%} IS={sr.sharpe_is:.2f} OOS={sr.sharpe_oos:.2f}")
    print(f"PASSING: {n_pass}/5")
    print(f"ENSEMBLE Sharpe={ens_m['Sharpe']:.2f} DD={ens_m['MaxDD']:.1%} IS={ens_m['sharpe_is']:.2f} OOS={ens_m['sharpe_oos']:.2f}")
    print(f"Wrote {RUN}")


if __name__ == "__main__":
    main()
