#!/usr/bin/env python3
"""BTCUSDT mean reversion demo for runs/demo_btc_mr (standalone vectorbt)."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import vectorbt as vbt

from tqg_client.market_data import load_symbol_from_parquet

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs" / "demo_btc_mr"
DATA = REPO / "data" / "binance" / "binance_futures_ohlcv_1d.parquet"

Z_WINDOW = 30
MA_WINDOW = 90
ENTRY_Z = 1.5
EXIT_Z = 0.0
LAG = 1
FEE = 0.00045
SLIPPAGE = 0.0005
OOS = pd.Timestamp("2025-01-01", tz="UTC")
ANN = 365


def _metrics(returns: pd.Series) -> dict[str, float]:
    r = returns.dropna()
    if r.empty:
        return {"Sharpe": 0.0, "Total Return": 0.0, "MaxDD": 0.0}
    cum = (1 + r).cumprod()
    dd = cum / cum.cummax() - 1
    vol = r.std()
    sharpe = float(np.sqrt(ANN) * r.mean() / vol) if vol > 0 else 0.0
    return {
        "Sharpe": sharpe,
        "Total Return": float(cum.iloc[-1] - 1),
        "MaxDD": float(dd.min()),
        "CAGR": float((cum.iloc[-1]) ** (ANN / len(r)) - 1) if len(r) > 0 else 0.0,
    }


def main() -> None:
    for sub in ("code", "artifacts", "charts", "logs"):
        (RUN / sub).mkdir(parents=True, exist_ok=True)

    df = load_symbol_from_parquet(DATA, "BTCUSDT", interval="1d")
    close = df["close"].astype(float)
    ret = close.pct_change()
    z = (ret - ret.rolling(Z_WINDOW).mean()) / ret.rolling(Z_WINDOW).std()
    ma = close.rolling(MA_WINDOW).mean()
    z = z.shift(LAG)
    ma = ma.shift(LAG)
    price = close.shift(LAG)

    long_e = (z < -ENTRY_Z) & (price > ma)
    long_x = (z > EXIT_Z) | (price < ma)
    short_e = (z > ENTRY_Z) & (price < ma)
    short_x = (z < EXIT_Z) | (price > ma)

    pf = vbt.Portfolio.from_signals(
        close,
        entries=long_e.fillna(False),
        exits=long_x.fillna(False),
        short_entries=short_e.fillna(False),
        short_exits=short_x.fillna(False),
        fees=FEE,
        slippage=SLIPPAGE,
        freq="1D",
    )
    strat_rets = pf.returns()

    is_rets = strat_rets.loc[strat_rets.index < OOS]
    oos_rets = strat_rets.loc[strat_rets.index >= OOS]
    metrics = {
        "in_sample": _metrics(is_rets),
        "out_of_sample": _metrics(oos_rets),
        "strategy_snapshot": {
            "symbol": "BTCUSDT",
            "z_window": Z_WINDOW,
            "ma_window": MA_WINDOW,
            "entry_z": ENTRY_Z,
            "oos_start_ts": str(OOS),
        },
    }
    (RUN / "artifacts" / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    equity = (1 + strat_rets.fillna(0)).cumprod()
    bh = close / close.iloc[0]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(equity.index, equity.values, label="Strategy")
    ax.plot(bh.index, bh.values, label="Buy & hold", alpha=0.7)
    ax.axvline(OOS, color="red", linestyle="--", label="OOS start")
    ax.legend()
    ax.set_title("BTC mean reversion vs buy & hold")
    fig.tight_layout()
    fig.savefig(RUN / "charts" / "equity_curve.png", dpi=120)
    plt.close(fig)

    dd = equity / equity.cummax() - 1
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.fill_between(dd.index, dd.values, 0, alpha=0.4)
    ax.set_title("Drawdown")
    fig.tight_layout()
    fig.savefig(RUN / "charts" / "drawdown.png", dpi=120)
    plt.close(fig)

    spec = {
        "workflow": "single_asset_signals",
        "strategy_type": "MEAN_REVERSION",
        "symbol": "BTCUSDT",
        "oos_start_ts": "2025-01-01",
        "params": {"z_window": Z_WINDOW, "ma_window": MA_WINDOW, "entry_z": ENTRY_Z},
    }
    (RUN / "strategy_spec.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    (RUN / "report.md").write_text(
        "# BTC mean reversion demo\n\nBaseline backtest with OOS from 2025-01-01.\n",
        encoding="utf-8",
    )
    print(f"Wrote demo artifacts under {RUN}")


if __name__ == "__main__":
    main()
