#!/usr/bin/env python3
"""Plot layered refresh equity curve to PNG."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import OOS_START, RESULTS_DIR


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    oos = pd.Timestamp(OOS_START, tz="UTC")

    returns_path = RESULTS_DIR / "returns_layered_refresh_daily.csv"
    summary_path = RESULTS_DIR / "layered_refresh_walkforward.json"
    if not returns_path.exists():
        raise FileNotFoundError(f"Missing {returns_path}; run backtest_layered_refresh.py first")

    rets = pd.read_csv(returns_path, index_col=0, parse_dates=True).iloc[:, 0]
    if rets.index.tz is None:
        rets.index = rets.index.tz_localize("UTC")
    equity = (1 + rets).cumprod()

    sharpe = max_dd = None
    refresh_dates: list[pd.Timestamp] = []
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        for row in summary["results"]:
            if row["variant"] == "layered_refresh":
                sharpe = row["full_sharpe"]
                max_dd = row["full_max_dd"]
                break
        refresh_dates = [
            pd.Timestamp(ev["date"], tz="UTC") for ev in summary.get("refresh_events", [])
        ]

    fig, ax = plt.subplots(figsize=(12, 6))

    is_mask = equity.index < oos
    oos_mask = equity.index >= oos

    ax.plot(equity.index[is_mask], equity[is_mask], color="#2563eb", linewidth=1.4, label="In-sample")
    ax.plot(equity.index[oos_mask], equity[oos_mask], color="#16a34a", linewidth=1.6, label="Out-of-sample")
    ax.axvline(oos, color="#94a3b8", linestyle="--", linewidth=1, label=f"OOS start ({oos.date()})")

    for i, dt in enumerate(refresh_dates):
        ax.axvline(dt, color="#f59e0b", linestyle=":", linewidth=1.2, alpha=0.85)
        if i == 0:
            ax.axvline(dt, color="#f59e0b", linestyle=":", linewidth=1.2, alpha=0.85, label="Triangle refresh")

    peak = equity.cummax()
    dd = (equity / peak - 1) * 100

    ax2 = ax.twinx()
    ax2.fill_between(equity.index, dd, 0, color="#ef4444", alpha=0.12)
    ax2.set_ylabel("Drawdown (%)", color="#64748b", fontsize=10)
    ax2.tick_params(axis="y", labelcolor="#64748b")
    ax2.set_ylim(min(dd.min() * 1.3, -5), 2)

    subtitle = []
    if sharpe is not None:
        subtitle.append(f"Sharpe {sharpe:.2f}")
    if max_dd is not None:
        subtitle.append(f"MaxDD {max_dd:.1%}")
    subtitle.append("Layered refresh · daily-compounded")

    ax.set_title(
        "Layered Refresh Triangular Pairs — Equity Curve\n" + "  ·  ".join(subtitle),
        fontsize=13,
        pad=12,
    )
    ax.set_ylabel("Equity (start = 1.0)")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", framealpha=0.9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    fig.autofmt_xdate()
    fig.tight_layout()

    out = RESULTS_DIR / "equity_curve_layered_refresh_daily.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
