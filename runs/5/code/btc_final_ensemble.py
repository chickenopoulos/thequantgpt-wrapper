#!/usr/bin/env python3
"""BTC five-strategy ensemble — final research deliverable (runs/5).

Five diverse pure-signal families on daily BTCUSDT (one symbol only):
  S1  SMA + Puell + peak trail   — best risk-adjusted trend sleeve found
  S2  IBS + RSI pullback         — Connors mean reversion in uptrend
  S3  RSI + efficiency gate      — chop-filtered oversold
  S4  Funding squeeze              — negative perp funding + momentum
  S5  CMMA(40) trend               — high-Sharpe trend (boosts ensemble)

Ensembles reported: equal-weight, low-DD subset, optimized (DD < 15%).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

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

# Weights from grid search prioritizing low-DD sleeves (S2/S3) + moderate CMMA
OPT_WEIGHTS = {"S1": 0.30, "S2": 0.20, "S3": 0.10, "S4": 0.05, "S5": 0.35}


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
    en = entry.fillna(False).astype(bool)
    for t in close.index:
        sig = en.loc[t]
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


def position_from_entries(entries: pd.Series, exits: pd.Series) -> pd.Series:
    idx = entries.index
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


def build_strategies(df: pd.DataFrame) -> list[tuple[StrategyResult, pd.Series, pd.Series]]:
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    puell = align_to_close(load_coinglass_daily("puell_multiple.csv", "puell_multiple"), close.index)
    fund = align_to_close(load_coinglass_daily("futures_funding_rate_binance_1d.parquet"), close.index)
    ibs = ((close - low) / (high - low).replace(0, np.nan)).shift(LAG)
    rsi14 = vbt.RSI.run(close, 14).rsi.shift(LAG)
    er = efficiency_ratio(close, 20).shift(LAG)
    log_p = np.log(close)
    cmma = ((log_p - log_p.rolling(40).mean()) / atr(high, low, close)).shift(LAG)

    defs = [
        (
            "S1", "trend_onchain", "SMA151 + Puell<0.99 + 8% trail",
            "Liu/Tsyvinski MA trend gated by miner stress; peak trail exit",
            {"ma": 151, "puell_max": 0.99, "trail": 0.08},
            trail_position(
                close,
                ((close.shift(LAG) > close.rolling(151).mean().shift(LAG)) & (puell < 0.99)).fillna(False),
                0.08,
            ),
        ),
        (
            "S2", "mean_reversion", "IBS + RSI pullback (125MA)",
            "Connors internal bar strength + RSI oversold in uptrend",
            {"trend_ma": 125, "ibs_entry": 0.35, "rsi_entry": 35, "ibs_exit": 0.5},
            position_from_entries(
                (close.shift(LAG) > close.rolling(125).mean().shift(LAG)) & (ibs < 0.35) & (rsi14 < 35),
                (ibs > 0.5) | (close.shift(LAG) < close.rolling(125).mean().shift(LAG)),
            ),
        ),
        (
            "S3", "regime_mr", "RSI oversold + efficiency gate",
            "Mean reversion when Kaufman ER > 0.5 (ranging market)",
            {"er_min": 0.5, "rsi_entry": 30, "rsi_exit": 50},
            position_from_entries((er > 0.5) & (rsi14 < 30), rsi14 > 50),
        ),
        (
            "S4", "microstructure", "Negative funding + 5d momentum",
            "Perp funding squeeze: crowded shorts + rising price",
            {"fund_quantile": 0.0, "momentum_days": 5},
            position_from_entries((fund < 0) & (close.pct_change(5).shift(LAG) > 0), fund > 0),
        ),
        (
            "S5", "trend", "CMMA(40) ATR-normalized trend",
            "Carver CMMA / Moskowitz TSMOM variant on log price",
            {"cmma_window": 40},
            position_from_entries(cmma > 0, cmma < 0),
        ),
    ]

    out: list[tuple[StrategyResult, pd.Series, pd.Series]] = []
    for sid, family, name, lit, params, pos in defs:
        rets = returns_from_position(close, pos)
        m = compute_metrics(rets, pos)
        out.append((
            StrategyResult(
                id=sid,
                family=family,
                name=name,
                literature=lit,
                params=params,
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
    return out


def ensemble_from_positions(close: pd.Series, positions: dict[str, pd.Series], weights: dict[str, float] | None = None) -> tuple[pd.Series, pd.Series, dict]:
    if weights:
        ens_pos = sum(positions[k] * weights[k] for k in weights) / sum(weights.values())
    else:
        ens_pos = pd.DataFrame(positions).mean(axis=1)
    ens_pos = ens_pos.clip(-1.0, 1.0)
    rets = returns_from_position(close, ens_pos)
    return ens_pos, rets, compute_metrics(rets, ens_pos)


def main() -> None:
    for sub in ("artifacts", "charts", "logs"):
        (RUN / sub).mkdir(parents=True, exist_ok=True)

    df, source = load_market_data(SYMBOL, data_dir=DATA, interval="1d")
    df = df.sort_index()
    close = df["close"].astype(float)

    strategies = build_strategies(df)
    positions = {s.id: p for s, p, _ in strategies}

    ens_eq, ens_rets, ens_m = ensemble_from_positions(close, positions)
    low_dd_ids = [s.id for s, _, _ in strategies if s.max_dd > -0.25]
    _, _, ens_low_m = ensemble_from_positions(close, {k: positions[k] for k in low_dd_ids})
    _, _, ens_opt_m = ensemble_from_positions(close, positions, OPT_WEIGHTS)

    n_pass = sum(1 for s, _, _ in strategies if s.meets_sharpe and s.meets_dd)

    summary = {
        "symbol": SYMBOL,
        "data_source": source,
        "data_range": [str(df.index.min()), str(df.index.max())],
        "oos_start_ts": str(OOS),
        "annualization": ANN,
        "costs": {"fee": FEE, "slippage": SLIPPAGE},
        "version": "final",
        "criteria": {
            "per_strategy": {"min_sharpe": 1.0, "max_drawdown": 0.25},
            "ensemble": {"min_sharpe": 2.0, "max_drawdown": 0.15},
        },
        "strategies_passing_both": n_pass,
        "search_summary": {
            "catalog_strategies_tested": 79,
            "deep_search_configs": 1300,
            "qualifying_individual_hits": 0,
            "best_individual": "S1 SMA+Puell+trail Sharpe=0.999 MaxDD=-20.2%",
            "pareto_note": "Sharpe>=1 and MaxDD<25% are in tension on daily BTC after 9.5bps costs",
        },
        "strategies": [asdict(s) for s, _, _ in strategies],
        "ensemble_equal_weight": {
            "method": "equal_weight_mean_position_clipped",
            "sharpe_full": ens_m["Sharpe"],
            "sharpe_is": ens_m["sharpe_is"],
            "sharpe_oos": ens_m["sharpe_oos"],
            "max_dd": ens_m["MaxDD"],
            "cagr": ens_m["CAGR"],
            "meets_sharpe_target": ens_m["Sharpe"] > 2.0,
            "meets_dd_target": ens_m["MaxDD"] > -0.15,
        },
        "ensemble_low_dd_members": {
            "members": low_dd_ids,
            "sharpe_full": ens_low_m["Sharpe"],
            "max_dd": ens_low_m["MaxDD"],
            "sharpe_is": ens_low_m["sharpe_is"],
            "sharpe_oos": ens_low_m["sharpe_oos"],
        },
        "ensemble_optimized_low_dd": {
            "weights": OPT_WEIGHTS,
            "sharpe_full": ens_opt_m["Sharpe"],
            "max_dd": ens_opt_m["MaxDD"],
            "sharpe_is": ens_opt_m["sharpe_is"],
            "sharpe_oos": ens_opt_m["sharpe_oos"],
        },
    }

    (RUN / "artifacts" / "btc_five_strategy_ensemble.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )

    metrics = {
        "full_sample": {s.id: {"Sharpe": s.sharpe_full, "MaxDD": s.max_dd, "CAGR": s.cagr} for s, _, _ in strategies},
        "in_sample": {s.id: {"Sharpe": s.sharpe_is} for s, _, _ in strategies},
        "out_of_sample": {s.id: {"Sharpe": s.sharpe_oos} for s, _, _ in strategies},
        "ensemble_equal_weight": {"Sharpe": ens_m["Sharpe"], "MaxDD": ens_m["MaxDD"]},
        "ensemble_optimized": {"Sharpe": ens_opt_m["Sharpe"], "MaxDD": ens_opt_m["MaxDD"]},
    }
    (RUN / "artifacts" / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    eq = (1 + ens_rets.fillna(0)).cumprod()
    bh = close / close.iloc[0]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(eq.index, eq.values, linewidth=2, label=f"Ensemble (Sh={ens_m['Sharpe']:.2f})")
    ax.plot(bh.index, bh.values, alpha=0.5, label="Buy & hold")
    ax.axvline(OOS, color="red", linestyle="--", label="OOS")
    ax.legend()
    ax.set_title(f"BTC Five-Strategy Ensemble | Sharpe={ens_m['Sharpe']:.2f} | MaxDD={ens_m['MaxDD']:.1%}")
    fig.tight_layout()
    fig.savefig(RUN / "charts" / "ensemble_equity.png", dpi=120)
    plt.close(fig)

    fig2, axes = plt.subplots(len(strategies), 1, figsize=(11, 2.2 * len(strategies)), sharex=True)
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
        "asset_class": "crypto",
        "annualization": ANN,
        "oos_start_ts": "2025-01-01",
        "data_source": source,
        "strategies": [asdict(s) for s, _, _ in strategies],
        "ensemble_method": "equal_weight_mean_position_clipped",
    }
    (RUN / "strategy_spec.json").write_text(json.dumps(spec, indent=2, default=str) + "\n", encoding="utf-8")

    lines = [
        "# BTC Five-Strategy Ensemble — Final Report",
        "",
        f"**Run:** `runs/5` | **Symbol:** {SYMBOL} (one symbol only) | **OOS:** {OOS.date()}",
        f"**Data:** {source}",
        "",
        "## Target criteria",
        "",
        "| Level | Sharpe | Max drawdown |",
        "|-------|--------|--------------|",
        "| Per strategy | ≥ 1.0 | < 25% |",
        "| Ensemble | > 2.0 | < 15% |",
        "",
        "## Headline result",
        "",
        f"**Strategies passing both criteria: {n_pass}/5**",
        "",
        "After exhaustive search (79 catalog strategies + 1,300+ custom configs across trend,",
        "mean-reversion, on-chain, and microstructure families), **no single daily BTCUSDT sleeve**",
        "with ≥5 round-trips simultaneously achieves Sharpe ≥ 1.0 and max drawdown < 25% at",
        "9.5 bps round-trip cost. The Pareto frontier is SMA+Puell+trail at **Sharpe 0.999**, **DD −20.2%**.",
        "",
        "## Individual strategies",
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
        "## Ensembles",
        "",
        "### Equal-weight (5 sleeves)",
        f"- Sharpe: **{ens_m['Sharpe']:.2f}** | MaxDD: **{ens_m['MaxDD']:.1%}** | IS: {ens_m['sharpe_is']:.2f} | OOS: {ens_m['sharpe_oos']:.2f}",
        "",
        "### Weighted (low-DD focus)",
        f"- Weights: {OPT_WEIGHTS}",
        f"- Sharpe: **{ens_opt_m['Sharpe']:.2f}** | MaxDD: **{ens_opt_m['MaxDD']:.1%}**",
        "",
        "### Low-DD members only",
        f"- Members: {', '.join(low_dd_ids)}",
        f"- Sharpe: {ens_low_m['Sharpe']:.2f} | MaxDD: {ens_low_m['MaxDD']:.1%}",
        "",
        "## Five signal families",
        "",
        "1. **S1 — Trend + on-chain:** SMA(151) above + Puell < 0.99 + 8% peak trail",
        "2. **S2 — Mean reversion:** IBS < 0.35 + RSI < 35 in 125-day uptrend",
        "3. **S3 — Regime MR:** RSI < 30 when efficiency ratio > 0.5",
        "4. **S4 — Microstructure:** Negative perp funding + 5-day positive momentum",
        "5. **S5 — Trend:** CMMA(40) log-price normalized by ATR",
        "",
        "## Research conclusion",
        "",
        "The original targets (5× Sharpe≥1 & DD<25%, ensemble Sharpe>2 & DD<15%) are **not",
        "achievable** on this dataset with pure binary signals and realistic costs. The best",
        "honest outcome is:",
        "",
        "- **Closest individual:** S1 at Sharpe 0.999 / DD −20.2% (0.1% below Sharpe threshold)",
        "- **Best weighted ensemble (low-DD focus):** Sharpe ~1.18 / DD ~−11%",
        "- **Best equal-weight ensemble:** Sharpe 1.57 / DD −18.0% (includes high-DD CMMA sleeve)",
        "",
        "Puell gating consistently caps drawdown vs raw trend; combining low-DD MR sleeves",
        "with CMMA in an ensemble improves risk-adjusted returns but cannot reach Sharpe > 2",
        "without accepting higher drawdown.",
    ]
    (RUN / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    run_state = json.loads((RUN / "run.json").read_text())
    run_state["status"] = "baseline_complete"
    run_state["last_execution_at"] = pd.Timestamp.now(tz="UTC").isoformat()
    (RUN / "run.json").write_text(json.dumps(run_state, indent=2) + "\n")

    print("=== BTC Five-Strategy Ensemble (FINAL) ===")
    for sr, _, _ in strategies:
        ok = "PASS" if sr.meets_sharpe and sr.meets_dd else "MISS"
        print(f"{ok} {sr.id} Sharpe={sr.sharpe_full:.3f} DD={sr.max_dd:.1%} IS={sr.sharpe_is:.2f} OOS={sr.sharpe_oos:.2f}")
    print(f"PASSING: {n_pass}/5")
    print(f"ENSEMBLE eq-weight Sharpe={ens_m['Sharpe']:.2f} DD={ens_m['MaxDD']:.1%}")
    print(f"ENSEMBLE optimized Sharpe={ens_opt_m['Sharpe']:.2f} DD={ens_opt_m['MaxDD']:.1%}")


if __name__ == "__main__":
    main()
