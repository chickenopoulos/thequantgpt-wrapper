#!/usr/bin/env python3
"""Cross-asset sweep: normalized IBS + RSI (same rules as QQQ baseline).

Rules (fixed from pullback_mr_jul2026 QQQ implementation):
  Entry: RSI(3) < 10 AND 2-day avg IBS < 0.45
  Exit:  close > prior day high
  Sizing: 100% equity; fee 0.00045; slippage 0.0005
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

RSI_WINDOW = 3
OVERSOLD = 10.0
IBS_WINDOW = 2
IBS_THR = 0.45
POSITION_SIZE = 1.0

ASSETS: list[dict[str, str]] = [
    {"symbol": "QQQ", "asset_class": "equity", "label": "Nasdaq-100 (QQQ)"},
    {"symbol": "SPY", "asset_class": "equity", "label": "S&P 500 (SPY)"},
    {"symbol": "IWM", "asset_class": "equity", "label": "Russell 2000 (IWM)"},
    {"symbol": "GLD", "asset_class": "equity", "label": "Gold (GLD ETF)"},
    {"symbol": "BTCUSDT", "asset_class": "crypto", "label": "Bitcoin (BTC-USD)"},
    {"symbol": "ETHUSDT", "asset_class": "crypto", "label": "Ethereum (ETH-USD)"},
]

for sub in ("code", "artifacts", "charts", "logs"):
    (RUN / sub).mkdir(parents=True, exist_ok=True)


def _ibs(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    span = (high - low).replace(0, np.nan)
    return ((close - low) / span).clip(0, 1)


def _signals(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    rsi = vbt.RSI.run(close, window=RSI_WINDOW).rsi
    norm_ibs = _ibs(high, low, close).rolling(IBS_WINDOW).mean()
    entries = ((rsi < OVERSOLD) & (norm_ibs < IBS_THR)).fillna(False).astype(bool)
    exits = (close > high.shift(1)).fillna(False).astype(bool)
    return entries, exits


def _exposure(trades: pd.DataFrame, n_bars: int) -> float:
    if trades.empty or n_bars <= 0:
        return 0.0
    entry_ts = pd.to_datetime(trades["Entry Timestamp"], utc=True)
    exit_ts = pd.to_datetime(trades["Exit Timestamp"], utc=True)
    duration = (exit_ts - entry_ts).dt.days.clip(lower=0)
    return float(duration.sum() / n_bars)


def _trade_stats(
    returns: pd.Series,
    pf: vbt.Portfolio,
    ann: int,
    *,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> dict[str, float]:
    trades = pf.trades.records_readable.copy()
    if start is not None:
        entry_ts = pd.to_datetime(trades["Entry Timestamp"], utc=True)
        trades = trades.loc[entry_ts >= start]
    if end is not None:
        entry_ts = pd.to_datetime(trades["Entry Timestamp"], utc=True)
        trades = trades.loc[entry_ts < end]

    r = returns.dropna()
    if r.empty:
        base = {
            "Sharpe": 0.0,
            "Total Return": 0.0,
            "MaxDD": 0.0,
            "CAGR": 0.0,
            "exposure": 0.0,
            "risk_adjusted_return": 0.0,
        }
    else:
        cum = (1 + r).cumprod()
        dd = cum / cum.cummax() - 1
        vol = r.std()
        sharpe = float(np.sqrt(ann) * r.mean() / vol) if vol > 0 else 0.0
        cagr = float((cum.iloc[-1]) ** (ann / len(r)) - 1) if len(r) > 0 else 0.0
        exposure = _exposure(trades, len(r))
        base = {
            "Sharpe": sharpe,
            "Total Return": float(cum.iloc[-1] - 1),
            "MaxDD": float(dd.min()),
            "CAGR": cagr,
            "exposure": exposure,
            "risk_adjusted_return": float(cagr / exposure) if exposure > 0 else 0.0,
        }

    if trades.empty:
        base.update(
            {
                "num_trades": 0.0,
                "win_rate": 0.0,
                "avg_gain_per_trade": 0.0,
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
    entry_ts_hold = pd.to_datetime(trades["Entry Timestamp"], utc=True)
    exit_ts_hold = pd.to_datetime(trades["Exit Timestamp"], utc=True)
    hold_bars = ((exit_ts_hold - entry_ts_hold).dt.days).astype(float)

    base.update(
        {
            "num_trades": float(len(trades)),
            "win_rate": float((pnls > 0).mean()),
            "avg_gain_per_trade": float(pnls.mean()),
            "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else 0.0,
            "avg_hold_bars": float(hold_bars.mean()) if not hold_bars.empty else 0.0,
        }
    )
    return base


def _backtest(symbol: str, asset_class: str) -> dict:
    df, data_source = load_market_data(symbol, data_dir=DATA, interval="1d")
    ann = default_annualization(symbol, asset_class=asset_class)
    close = df["close"].astype(float)
    entries, exits = _signals(df)

    pf = vbt.Portfolio.from_signals(
        close,
        entries=entries,
        exits=exits,
        short_entries=pd.Series(False, index=close.index),
        short_exits=pd.Series(False, index=close.index),
        size=POSITION_SIZE,
        size_type="percent",
        fees=FEE,
        slippage=SLIPPAGE,
        freq="1D",
    )
    rets = pf.returns()
    is_rets = rets.loc[rets.index < OOS]
    oos_rets = rets.loc[rets.index >= OOS]

    return {
        "symbol": symbol,
        "asset_class": asset_class,
        "data_source": data_source,
        "annualization": ann,
        "data_start": str(df.index.min().date()),
        "data_end": str(df.index.max().date()),
        "in_sample": _trade_stats(is_rets, pf, ann, end=OOS),
        "out_of_sample": _trade_stats(oos_rets, pf, ann, start=OOS),
        "full_sample": _trade_stats(rets, pf, ann),
        "returns": rets,
        "close": close,
    }


results: dict[str, dict] = {}
for asset in ASSETS:
    sym = asset["symbol"]
    print(f"Backtesting {sym}...")
    try:
        results[sym] = _backtest(sym, asset["asset_class"])
        results[sym]["label"] = asset["label"]
    except Exception as exc:
        print(f"  SKIP {sym}: {exc}")
        results[sym] = {"symbol": sym, "error": str(exc), "label": asset["label"]}

summary_rows = []
for sym, res in results.items():
    if "error" in res:
        continue
    full = res["full_sample"]
    summary_rows.append(
        {
            "symbol": sym,
            "label": res["label"],
            "data_source": res["data_source"],
            "annualization": res["annualization"],
            "data_start": res["data_start"],
            "data_end": res["data_end"],
            **{f"full_{k}": v for k, v in full.items()},
            "oos_CAGR": res["out_of_sample"]["CAGR"],
            "oos_Sharpe": res["out_of_sample"]["Sharpe"],
            "oos_num_trades": res["out_of_sample"]["num_trades"],
        }
    )

payload = {
    "strategy": "normalized_ibs_rsi",
    "rules": {
        "rsi_window": RSI_WINDOW,
        "oversold": OVERSOLD,
        "ibs_window": IBS_WINDOW,
        "ibs_thr": IBS_THR,
        "exit": "close > prior day high",
        "position_size": POSITION_SIZE,
        "fee": FEE,
        "slippage": SLIPPAGE,
    },
    "oos_start_ts": str(OOS),
    "assets": {sym: {k: v for k, v in res.items() if k not in {"returns", "close"}} for sym, res in results.items()},
    "summary_table": summary_rows,
}
(RUN / "artifacts" / "ibs_cross_asset.json").write_text(
    json.dumps(payload, indent=2, default=str) + "\n",
    encoding="utf-8",
)

fig, ax = plt.subplots(figsize=(11, 6))
for sym, res in results.items():
    if "error" in res:
        continue
    equity = (1 + res["returns"].fillna(0)).cumprod()
    ax.plot(equity.index, equity.values, label=f"{sym} (CAGR {res['full_sample']['CAGR']*100:.1f}%)")
ax.axvline(OOS, color="red", linestyle="--", alpha=0.6, label="OOS start")
ax.set_title("Normalized IBS + RSI — cross-asset equity curves")
ax.legend(fontsize=8, loc="upper left")
ax.set_ylabel("Growth of $1")
fig.tight_layout()
fig.savefig(RUN / "charts" / "ibs_cross_asset_equity.png", dpi=120)
plt.close(fig)

for sym, res in results.items():
    if "error" in res:
        continue
    equity = (1 + res["returns"].fillna(0)).cumprod()
    bh = res["close"] / res["close"].iloc[0]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(equity.index, equity.values, label="Strategy")
    ax.plot(bh.index, bh.values, label="Buy & hold", alpha=0.7)
    ax.axvline(OOS, color="red", linestyle="--", alpha=0.6)
    ax.legend()
    ax.set_title(f"{res['label']} — normalized IBS + RSI")
    fig.tight_layout()
    fig.savefig(RUN / "charts" / f"ibs_{sym.lower()}_equity.png", dpi=120)
    plt.close(fig)

lines = [
    "# Normalized IBS + RSI — cross-asset sweep",
    "",
    f"**Run:** pullback_mr_jul2026  ",
    f"**OOS cut-off:** 2025-01-01  ",
    f"**Rules:** RSI({RSI_WINDOW}) < {OVERSOLD}, 2-day avg IBS < {IBS_THR}, exit when close > prior day high  ",
    f"**Costs:** fee {FEE}, slippage {SLIPPAGE}; 100% equity per trade",
    "",
    "Same parameters as the QQQ baseline (no per-asset tuning).",
    "",
    "## Full-sample comparison",
    "",
    "| Asset | Data | Ann. | Trades | Win% | PF | Avg/trade | CAGR | MaxDD | Exposure |",
    "|-------|------|------|--------|------|-----|-----------|------|-------|----------|",
]
for row in summary_rows:
    lines.append(
        f"| {row['label']} | {row['data_source']} | {row['annualization']} | "
        f"{row['full_num_trades']:.0f} | {row['full_win_rate']*100:.0f}% | "
        f"{row['full_profit_factor']:.2f} | {row['full_avg_gain_per_trade']*100:.2f}% | "
        f"{row['full_CAGR']*100:.1f}% | {row['full_MaxDD']*100:.1f}% | {row['full_exposure']*100:.0f}% |"
    )

lines.extend(
    [
        "",
        "## Out-of-sample (from 2025-01-01)",
        "",
        "| Asset | Sharpe | CAGR | MaxDD | Trades | Win% | PF |",
        "|-------|--------|------|-------|--------|------|-----|",
    ]
)
for sym, res in results.items():
    if "error" in res:
        continue
    oos = res["out_of_sample"]
    lines.append(
        f"| {res['label']} | {oos['Sharpe']:.2f} | {oos['CAGR']*100:.1f}% | "
        f"{oos['MaxDD']*100:.1f}% | {oos['num_trades']:.0f} | "
        f"{oos['win_rate']*100:.0f}% | {oos['profit_factor']:.2f} |"
    )

lines.extend(
    [
        "",
        "## Notes",
        "",
        "- IBS mean reversion is documented by QS primarily on broad equity indices; crypto/metals may behave differently.",
        "- BTC/ETH use 365-day annualization; ETFs use 252.",
        "- Charts: `charts/ibs_cross_asset_equity.png` and per-asset `charts/ibs_<symbol>_equity.png`.",
        "",
    ]
)
(RUN / "report_ibs_cross_asset.md").write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {RUN / 'artifacts' / 'ibs_cross_asset.json'}")
print(f"Wrote {RUN / 'report_ibs_cross_asset.md'}")
