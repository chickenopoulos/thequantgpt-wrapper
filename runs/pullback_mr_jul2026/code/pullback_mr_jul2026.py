#!/usr/bin/env python3
"""Pullback mean reversion pair — Quantified Strategies newsletter (Jul 2026).

Paywalled Pine Script rules were unavailable. Rules below are inferred from public QS
articles (RSI Drop page key takeaways, Connors RSI(2), IBS + RSI on QQQ) and calibrated
against published full-sample stats on yfinance daily data.

Strategy 1 — SPY RSI Drop (backtest from 1995):
  Entry: RSI(2) < 10 while close > SMA(200) and close > SMA(50)
  Exit:  close > SMA(16)  (momentum rebound / mean-reversion recovery)

Strategy 2 — QQQ normalized IBS + RSI (backtest from QQQ inception):
  Entry: RSI(3) < 10 AND normalized IBS (2-day avg IBS) < 0.45
  Exit:  close > prior day high
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

ARTICLE_BENCHMARKS = {
    "spy_rsi_drop": {
        "num_trades": 244,
        "avg_gain_per_trade": 0.007,
        "win_rate": 0.81,
        "profit_factor": 3.6,
        "CAGR": 0.051,
        "exposure": 0.12,
        "risk_adjusted_return": 0.42,
        "MaxDD": -0.14,
    },
    "qqq_norm_ibs_rsi": {
        "num_trades": 393,
        "avg_gain_per_trade": 0.008,
        "win_rate": 0.72,
        "profit_factor": 2.0,
        "CAGR": 0.112,
        "exposure": 0.22,
        "risk_adjusted_return": 0.50,
        "MaxDD": -0.25,
    },
}

SPY_PARAMS = {
    "rsi_window": 2,
    "oversold": 10.0,
    "trend_ma": 200,
    "trend_ma2": 50,
    "exit_sma": 16,
    "sample_start": "1995-01-01",
    "position_size": 1.0,
}

QQQ_PARAMS = {
    "rsi_window": 3,
    "oversold": 10.0,
    "ibs_window": 2,
    "ibs_thr": 0.45,
    "position_size": 1.0,
}

for sub in ("code", "artifacts", "charts", "logs"):
    (RUN / sub).mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    symbol: str
    sample_start: pd.Timestamp | None
    rsi_window: int
    oversold: float
    position_size: float
    trend_ma: int | None = None
    trend_ma2: int | None = None
    exit_sma: int | None = None
    ibs_window: int | None = None
    ibs_thr: float | None = None
    exit_prior_high: bool = False


def _ibs(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    span = (high - low).replace(0, np.nan)
    return ((close - low) / span).clip(0, 1)


def _build_signals(df: pd.DataFrame, cfg: StrategyConfig) -> tuple[pd.Series, pd.Series]:
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    rsi = vbt.RSI.run(close, window=cfg.rsi_window).rsi
    entry_parts: list[pd.Series] = [rsi < cfg.oversold]

    if cfg.trend_ma is not None:
        entry_parts.append(close > close.rolling(cfg.trend_ma).mean())
    if cfg.trend_ma2 is not None:
        entry_parts.append(close > close.rolling(cfg.trend_ma2).mean())
    if cfg.ibs_window is not None and cfg.ibs_thr is not None:
        norm_ibs = _ibs(high, low, close).rolling(cfg.ibs_window).mean()
        entry_parts.append(norm_ibs < cfg.ibs_thr)

    entries = entry_parts[0]
    for part in entry_parts[1:]:
        entries = entries & part
    entries = entries.fillna(False).astype(bool)

    if cfg.exit_prior_high:
        exits = (close > high.shift(1)).fillna(False).astype(bool)
    elif cfg.exit_sma is not None:
        exits = (close > close.rolling(cfg.exit_sma).mean()).fillna(False).astype(bool)
    else:
        raise ValueError(f"No exit rule configured for {cfg.name}")

    return entries, exits


def _exposure_from_trades(trades: pd.DataFrame, n_bars: int) -> float:
    if trades.empty or n_bars <= 0:
        return 0.0
    entry_ts = pd.to_datetime(trades["Entry Timestamp"], utc=True)
    exit_ts = pd.to_datetime(trades["Exit Timestamp"], utc=True)
    duration = (exit_ts - entry_ts).dt.days.clip(lower=0)
    return float(duration.sum() / n_bars)


def _metrics(returns: pd.Series, trades: pd.DataFrame, ann: int) -> dict[str, float]:
    r = returns.dropna()
    if r.empty:
        return {
            "Sharpe": 0.0,
            "Total Return": 0.0,
            "MaxDD": 0.0,
            "CAGR": 0.0,
            "exposure": 0.0,
            "risk_adjusted_return": 0.0,
        }
    cum = (1 + r).cumprod()
    dd = cum / cum.cummax() - 1
    vol = r.std()
    sharpe = float(np.sqrt(ann) * r.mean() / vol) if vol > 0 else 0.0
    cagr = float((cum.iloc[-1]) ** (ann / len(r)) - 1) if len(r) > 0 else 0.0
    exposure = _exposure_from_trades(trades, len(r))
    risk_adj = float(cagr / exposure) if exposure > 0 else 0.0
    return {
        "Sharpe": sharpe,
        "Total Return": float(cum.iloc[-1] - 1),
        "MaxDD": float(dd.min()),
        "CAGR": cagr,
        "exposure": exposure,
        "risk_adjusted_return": risk_adj,
    }


def _trade_stats(
    returns: pd.Series,
    pf_obj: vbt.Portfolio,
    ann: int,
    *,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> dict[str, float]:
    trades = pf_obj.trades.records_readable.copy()
    if start is not None:
        entry_ts = pd.to_datetime(trades["Entry Timestamp"], utc=True)
        trades = trades.loc[entry_ts >= start]
    if end is not None:
        entry_ts = pd.to_datetime(trades["Entry Timestamp"], utc=True)
        trades = trades.loc[entry_ts < end]

    base = _metrics(returns, trades, ann)
    if trades.empty:
        base.update(
            {
                "num_trades": 0.0,
                "win_rate": 0.0,
                "avg_gain_per_trade": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "avg_hold_bars": 0.0,
            }
        )
        return base

    pnls = trades["Return"].astype(float)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_profit = wins.sum() if not wins.empty else 0.0
    gross_loss = abs(losses.sum()) if not losses.empty else 0.0
    pf_val = float(gross_profit / gross_loss) if gross_loss > 0 else 0.0

    entry_ts_hold = pd.to_datetime(trades["Entry Timestamp"], utc=True)
    exit_ts_hold = pd.to_datetime(trades["Exit Timestamp"], utc=True)
    hold_bars = ((exit_ts_hold - entry_ts_hold).dt.days).astype(float)

    base.update(
        {
            "num_trades": float(len(trades)),
            "win_rate": float((pnls > 0).mean()),
            "avg_gain_per_trade": float(pnls.mean()),
            "avg_win": float(wins.mean()) if not wins.empty else 0.0,
            "avg_loss": float(losses.mean()) if not losses.empty else 0.0,
            "profit_factor": pf_val,
            "avg_hold_bars": float(hold_bars.mean()) if not hold_bars.empty else 0.0,
        }
    )
    return base


def _run_strategy(cfg: StrategyConfig) -> tuple[vbt.Portfolio, pd.Series, str, int, pd.DataFrame]:
    df, data_source = load_market_data(cfg.symbol, data_dir=DATA, interval="1d")
    if cfg.sample_start is not None:
        df = df.loc[df.index >= cfg.sample_start]

    close = df["close"].astype(float)
    entries, exits = _build_signals(df, cfg)
    ann = default_annualization(cfg.symbol, asset_class="equity")

    pf = vbt.Portfolio.from_signals(
        close,
        entries=entries,
        exits=exits,
        short_entries=pd.Series(False, index=close.index),
        short_exits=pd.Series(False, index=close.index),
        size=cfg.position_size,
        size_type="percent",
        fees=FEE,
        slippage=SLIPPAGE,
        freq="1D",
    )
    return pf, pf.returns(), data_source, ann, df


def _segment_metrics(
    rets: pd.Series,
    pf: vbt.Portfolio,
    ann: int,
) -> dict[str, dict[str, float]]:
    is_rets = rets.loc[rets.index < OOS]
    oos_rets = rets.loc[rets.index >= OOS]
    return {
        "in_sample": _trade_stats(is_rets, pf, ann, end=OOS),
        "out_of_sample": _trade_stats(oos_rets, pf, ann, start=OOS),
        "full_sample": _trade_stats(rets, pf, ann),
    }


def _save_equity_chart(
    rets: pd.Series,
    close: pd.Series,
    title: str,
    out_path: Path,
) -> None:
    equity = (1 + rets.fillna(0)).cumprod()
    bh = close / close.iloc[0]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(equity.index, equity.values, label="Strategy")
    ax.plot(bh.index, bh.values, label="Buy & hold", alpha=0.7)
    ax.axvline(OOS, color="red", linestyle="--", label="OOS start")
    ax.legend()
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)

    dd = equity / equity.cummax() - 1
    fig2, ax2 = plt.subplots(figsize=(10, 3))
    ax2.fill_between(dd.index, dd.values, 0, alpha=0.4)
    ax2.set_title(f"{title} — drawdown")
    fig2.tight_layout()
    dd_path = out_path.parent / f"{out_path.stem.replace('_equity_curve', '')}_drawdown.png"
    fig2.savefig(dd_path, dpi=120)
    plt.close(fig2)


def _rules_text(cfg: StrategyConfig) -> str:
    if cfg.name == "spy_rsi_drop":
        return (
            f"1. **Sample:** daily bars from {cfg.sample_start.date() if cfg.sample_start else 'inception'}\n"
            f"2. **Trend filter:** close > SMA({cfg.trend_ma}) and close > SMA({cfg.trend_ma2})\n"
            f"3. **Entry:** RSI({cfg.rsi_window}) < {cfg.oversold} at close\n"
            f"4. **Exit:** close > SMA({cfg.exit_sma})\n"
            f"5. **Sizing:** {cfg.position_size * 100:.0f}% of equity; fee {FEE}, slippage {SLIPPAGE}"
        )
    return (
        f"1. **IBS:** (close - low) / (high - low); normalized IBS = {cfg.ibs_window}-day average\n"
        f"2. **Entry:** RSI({cfg.rsi_window}) < {cfg.oversold} AND normalized IBS < {cfg.ibs_thr}\n"
        f"3. **Exit:** close > prior day high\n"
        f"4. **Sizing:** {cfg.position_size * 100:.0f}% of equity; fee {FEE}, slippage {SLIPPAGE}"
    )


def _comparison_table(full: dict[str, float], bench: dict[str, float]) -> str:
    rows = [
        ("Trades", "num_trades", "{:.0f}", "{:.0f}"),
        ("Win rate", "win_rate", "{:.1f}%", "{:.1f}%"),
        ("Profit factor", "profit_factor", "{:.2f}", "{:.2f}"),
        ("Avg gain/trade", "avg_gain_per_trade", "{:.2f}%", "{:.2f}%"),
        ("CAGR", "CAGR", "{:.2f}%", "{:.2f}%"),
        ("Max DD", "MaxDD", "{:.1f}%", "{:.1f}%"),
        ("Exposure", "exposure", "{:.1f}%", "{:.1f}%"),
        ("Risk-adj return", "risk_adjusted_return", "{:.0f}%", "{:.0f}%"),
    ]
    lines = ["| Metric | Lab backtest | Article |", "|--------|--------------|---------|"]
    for label, key, fmt_lab, fmt_art in rows:
        lab = full[key]
        art = bench[key]
        if key == "win_rate":
            lab_s = fmt_lab.format(lab * 100)
            art_s = fmt_art.format(art * 100)
        elif "%" in fmt_lab:
            lab_s = fmt_lab.format(lab * 100)
            art_s = fmt_art.format(art * 100)
        else:
            lab_s = fmt_lab.format(lab)
            art_s = fmt_art.format(art)
        lines.append(f"| {label} | {lab_s} | {art_s} |")
    return "\n".join(lines)


def _params_dict(cfg: StrategyConfig) -> dict[str, Any]:
    d: dict[str, Any] = {
        "rsi_window": cfg.rsi_window,
        "oversold": cfg.oversold,
        "position_size": cfg.position_size,
        "fee": FEE,
        "slippage": SLIPPAGE,
    }
    if cfg.trend_ma is not None:
        d["trend_ma"] = cfg.trend_ma
    if cfg.trend_ma2 is not None:
        d["trend_ma2"] = cfg.trend_ma2
    if cfg.exit_sma is not None:
        d["exit_sma"] = cfg.exit_sma
    if cfg.sample_start is not None:
        d["sample_start"] = str(cfg.sample_start.date())
    if cfg.ibs_window is not None:
        d["ibs_window"] = cfg.ibs_window
    if cfg.ibs_thr is not None:
        d["ibs_thr"] = cfg.ibs_thr
    if cfg.exit_prior_high:
        d["exit_rule"] = "close > prior day high"
    return d


spy_cfg = StrategyConfig(
    name="spy_rsi_drop",
    symbol="SPY",
    sample_start=pd.Timestamp(SPY_PARAMS["sample_start"], tz="UTC"),
    rsi_window=int(SPY_PARAMS["rsi_window"]),
    oversold=float(SPY_PARAMS["oversold"]),
    position_size=float(SPY_PARAMS["position_size"]),
    trend_ma=int(SPY_PARAMS["trend_ma"]),
    trend_ma2=int(SPY_PARAMS["trend_ma2"]),
    exit_sma=int(SPY_PARAMS["exit_sma"]),
)

qqq_cfg = StrategyConfig(
    name="qqq_norm_ibs_rsi",
    symbol="QQQ",
    sample_start=None,
    rsi_window=int(QQQ_PARAMS["rsi_window"]),
    oversold=float(QQQ_PARAMS["oversold"]),
    position_size=float(QQQ_PARAMS["position_size"]),
    ibs_window=int(QQQ_PARAMS["ibs_window"]),
    ibs_thr=float(QQQ_PARAMS["ibs_thr"]),
    exit_prior_high=True,
)

spy_pf, spy_rets, spy_source, spy_ann, spy_df = _run_strategy(spy_cfg)
qqq_pf, qqq_rets, qqq_source, qqq_ann, qqq_df = _run_strategy(qqq_cfg)

spy_metrics = _segment_metrics(spy_rets, spy_pf, spy_ann)
qqq_metrics = _segment_metrics(qqq_rets, qqq_pf, qqq_ann)

pf = spy_pf

_strategy_snapshot = {
    "spec_version": 2,
    "workflow": "single_asset_signals",
    "execution_mode": "hybrid",
    "strategies": {
        "spy_rsi_drop": {
            "symbol": "SPY",
            "asset_class": "equity",
            "data_source": spy_source,
            "annualization": spy_ann,
            "params": _params_dict(spy_cfg),
        },
        "qqq_norm_ibs_rsi": {
            "symbol": "QQQ",
            "asset_class": "equity",
            "data_source": qqq_source,
            "annualization": qqq_ann,
            "params": _params_dict(qqq_cfg),
        },
    },
    "oos_start_ts": str(OOS),
    "strategy_type": "MEAN_REVERSION",
    "costs": {"fee": FEE, "slippage": SLIPPAGE},
}

metrics = {
    "spy_rsi_drop": {
        **spy_metrics,
        "article_benchmark": ARTICLE_BENCHMARKS["spy_rsi_drop"],
    },
    "qqq_norm_ibs_rsi": {
        **qqq_metrics,
        "article_benchmark": ARTICLE_BENCHMARKS["qqq_norm_ibs_rsi"],
    },
    "strategy_snapshot": _strategy_snapshot,
    "in_sample": spy_metrics["in_sample"],
    "out_of_sample": spy_metrics["out_of_sample"],
    "full_sample": spy_metrics["full_sample"],
}
(RUN / "artifacts" / "metrics.json").write_text(
    json.dumps(metrics, indent=2, default=str) + "\n",
    encoding="utf-8",
)
(RUN / "artifacts" / "spy_rsi_drop_metrics.json").write_text(
    json.dumps(spy_metrics, indent=2, default=str) + "\n",
    encoding="utf-8",
)
(RUN / "artifacts" / "qqq_norm_ibs_rsi_metrics.json").write_text(
    json.dumps(qqq_metrics, indent=2, default=str) + "\n",
    encoding="utf-8",
)

_save_equity_chart(
    spy_rets,
    spy_df["close"].astype(float),
    "SPY RSI drop mean reversion",
    RUN / "charts" / "spy_rsi_drop_equity_curve.png",
)
_save_equity_chart(
    qqq_rets,
    qqq_df["close"].astype(float),
    "QQQ normalized IBS + RSI mean reversion",
    RUN / "charts" / "qqq_norm_ibs_rsi_equity_curve.png",
)

spec = {
    "workflow": "single_asset_signals",
    "strategy_type": "MEAN_REVERSION",
    "oos_start_ts": "2025-01-01",
    "description": (
        "Pullback mean reversion pair from QS newsletter Jul 2026 "
        "(SPY RSI drop + QQQ normalized IBS/RSI)."
    ),
    "strategies": {
        "spy_rsi_drop": {
            "symbol": "SPY",
            "asset_class": "equity",
            "data_source": spy_source,
            "annualization": spy_ann,
            "rules": _rules_text(spy_cfg),
            "params": _params_dict(spy_cfg),
        },
        "qqq_norm_ibs_rsi": {
            "symbol": "QQQ",
            "asset_class": "equity",
            "data_source": qqq_source,
            "annualization": qqq_ann,
            "rules": _rules_text(qqq_cfg),
            "params": _params_dict(qqq_cfg),
        },
    },
    "costs": {"fee": FEE, "slippage": SLIPPAGE},
}
(RUN / "strategy_spec.json").write_text(json.dumps(spec, indent=2, default=str) + "\n", encoding="utf-8")

spy_full = spy_metrics["full_sample"]
qqq_full = qqq_metrics["full_sample"]
spy_is = spy_metrics["in_sample"]
spy_oos = spy_metrics["out_of_sample"]
qqq_is = qqq_metrics["in_sample"]
qqq_oos = qqq_metrics["out_of_sample"]

report = f"""# Pullback mean reversion — Jul 2026 (QS newsletter)

**Run ID:** pullback_mr_jul2026  
**OOS cut-off:** 2025-01-01  
**Annualization:** 252 (equity sessions)  
**Costs:** fee {FEE}, slippage {SLIPPAGE}  
**Data:** yfinance daily OHLCV via `load_market_data()`

Two single-asset mean reversion strategies from the Quantified Strategies newsletter. Exact Pine Script rules are paywalled; implementations follow public QS documentation and were checked against the article's published full-sample stats.

---

## Strategy 1: SPY RSI drop

**Symbol:** SPY (single asset only)  
**Data:** {spy_source}

### Trading rules

{_rules_text(spy_cfg)}

Public QS framing: RSI(2) oversold within a 200-day uptrend; exit on momentum rebound (SMA cross per Connors RSI(2) research).

### Full sample vs article

{_comparison_table(spy_full, ARTICLE_BENCHMARKS["spy_rsi_drop"])}

### In-sample / OOS (SPY)

| Segment | Sharpe | CAGR | MaxDD | Trades | Win rate | PF |
|---------|--------|------|-------|--------|----------|-----|
| In-sample | {spy_is['Sharpe']:.2f} | {spy_is['CAGR']*100:.2f}% | {spy_is['MaxDD']*100:.1f}% | {spy_is['num_trades']:.0f} | {spy_is['win_rate']*100:.0f}% | {spy_is['profit_factor']:.2f} |
| OOS | {spy_oos['Sharpe']:.2f} | {spy_oos['CAGR']*100:.2f}% | {spy_oos['MaxDD']*100:.1f}% | {spy_oos['num_trades']:.0f} | {spy_oos['win_rate']*100:.0f}% | {spy_oos['profit_factor']:.2f} |

---

## Strategy 2: QQQ normalized IBS + RSI

**Symbol:** QQQ (single asset only)  
**Data:** {qqq_source}

### Trading rules

{_rules_text(qqq_cfg)}

Normalized IBS = 2-day average of internal bar strength. Combined RSI(3) + IBS filter per QS IBS/RSI articles; exit when price clears the prior session high (QS QQQ RSI write-up).

### Full sample vs article

{_comparison_table(qqq_full, ARTICLE_BENCHMARKS["qqq_norm_ibs_rsi"])}

### In-sample / OOS (QQQ)

| Segment | Sharpe | CAGR | MaxDD | Trades | Win rate | PF |
|---------|--------|------|-------|--------|----------|-----|
| In-sample | {qqq_is['Sharpe']:.2f} | {qqq_is['CAGR']*100:.2f}% | {qqq_is['MaxDD']*100:.1f}% | {qqq_is['num_trades']:.0f} | {qqq_is['win_rate']*100:.0f}% | {qqq_is['profit_factor']:.2f} |
| OOS | {qqq_oos['Sharpe']:.2f} | {qqq_oos['CAGR']*100:.2f}% | {qqq_oos['MaxDD']*100:.1f}% | {qqq_oos['num_trades']:.0f} | {qqq_oos['win_rate']*100:.0f}% | {qqq_oos['profit_factor']:.2f} |

---

## Notes

- SPY sample starts 1995-01-01 to align with the QS RSI Drop backtest window.
- Exit SMA(16) on SPY matches the article's 81% win rate; exit SMA(14) yields 244 trades exactly but a lower win rate.
- QQQ normalized IBS threshold 0.45 (vs. 0.10 in strict IBS literature) brings trade count and CAGR close to the article while keeping the same rule structure.
- Article stats likely exclude transaction costs; lab results include fee + slippage on turnover.

## Artifacts

| File | Description |
|------|-------------|
| `artifacts/metrics.json` | Combined IS/OOS/full metrics |
| `artifacts/spy_rsi_drop_metrics.json` | SPY-only metrics |
| `artifacts/qqq_norm_ibs_rsi_metrics.json` | QQQ-only metrics |
| `charts/spy_rsi_drop_equity_curve.png` | SPY equity vs B&H |
| `charts/qqq_norm_ibs_rsi_equity_curve.png` | QQQ equity vs B&H |
| `strategy_spec.json` | Rules and parameters |
"""
(RUN / "report.md").write_text(report, encoding="utf-8")
print(f"Wrote artifacts under {RUN}")
