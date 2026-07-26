#!/usr/bin/env python3
"""Export T-13 (Network momentum hub) equity curve chart."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

import matplotlib.pyplot as plt
import numpy as np
import vectorbt as vbt

from tqg_client.market_data import default_annualization
from tqg_client.strategy_sweep_core import FEE, LAG, OOS, SLIPPAGE, load_close

OUT = _REPO / "docs" / "plans" / "charts" / "T-13_equity_curve.png"
BASELINE_LOOKBACK = 20
PSA_LOOKBACK = 40


def build_signals(lookback: int):
    bclose = load_close("BTCUSDT")
    eclose = load_close("ETHUSDT")
    idx = bclose.index.intersection(eclose.index)
    sig = (bclose.pct_change(lookback).shift(LAG + 1) > 0).reindex(idx).fillna(False)
    entries = sig.reindex(eclose.index).fillna(False)
    exits = ~entries
    return eclose, entries.astype(bool), exits.astype(bool)


def equity_and_metrics(close, entries, exits):
    pf = vbt.Portfolio.from_signals(
        close.astype(float),
        entries=entries,
        exits=exits,
        fees=FEE,
        slippage=SLIPPAGE,
        freq="1D",
    )
    rets = pf.returns().dropna()
    cum = (1 + rets).cumprod()
    ann = default_annualization("ETHUSDT", asset_class="crypto")

    def sharpe(r):
        if r.empty or r.std() == 0:
            return 0.0
        return float(np.sqrt(ann) * r.mean() / r.std())

    r_is = rets.loc[rets.index < OOS]
    r_oos = rets.loc[rets.index >= OOS]
    return cum, {
        "sharpe_full": sharpe(rets),
        "sharpe_is": sharpe(r_is),
        "sharpe_oos": sharpe(r_oos),
        "trades": int(pf.trades.count()),
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    close20, e20, x20 = build_signals(BASELINE_LOOKBACK)
    cum20, m20 = equity_and_metrics(close20, e20, x20)
    close40, e40, x40 = build_signals(PSA_LOOKBACK)
    cum40, m40 = equity_and_metrics(close40, e40, x40)

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(
        cum20.index,
        cum20.values,
        label=f"Baseline lookback={BASELINE_LOOKBACK} (IS Sharpe {m20['sharpe_is']:.2f})",
        linewidth=1.8,
    )
    ax.plot(
        cum40.index,
        cum40.values,
        label=f"PSA center lookback={PSA_LOOKBACK} (IS Sharpe {m40['sharpe_is']:.2f})",
        linewidth=1.8,
        alpha=0.85,
    )
    ax.axvline(OOS, color="black", linestyle="--", linewidth=1, label="OOS start 2025-01-01")
    ax.set_title("T-13 Network momentum hub — ETHUSDT equity (BTC hub signal)")
    ax.set_ylabel("Cumulative return (1 = start)")
    ax.set_xlabel("Date")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    plt.close(fig)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
