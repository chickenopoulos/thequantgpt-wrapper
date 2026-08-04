#!/usr/bin/env python3
"""Plot hourly-native equity curve to PNG."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import OOS_START, RESULTS_DIR


def plot_equity(
    equity: pd.Series,
    out_path: Path,
    *,
    oos_start: pd.Timestamp,
    sharpe: float | None = None,
    max_dd: float | None = None,
    title: str = "Hourly-Native Triangular Pairs — Equity Curve",
) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))

    is_mask = equity.index < oos_start
    oos_mask = equity.index >= oos_start

    ax.plot(equity.index[is_mask], equity[is_mask], color="#2563eb", linewidth=1.4, label="In-sample")
    ax.plot(equity.index[oos_mask], equity[oos_mask], color="#16a34a", linewidth=1.6, label="Out-of-sample")
    ax.axvline(oos_start, color="#94a3b8", linestyle="--", linewidth=1, label=f"OOS start ({oos_start.date()})")

    # Drawdown band (secondary visual via fill under running peak distance)
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
    subtitle.append("Daily-compounded from hourly bars")

    ax.set_title(title + ("\n" + "  ·  ".join(subtitle) if subtitle else ""), fontsize=13, pad=12)
    ax.set_ylabel("Equity (start = 1.0)")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", framealpha=0.9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    oos = pd.Timestamp(OOS_START, tz="UTC")

    daily_csv = RESULTS_DIR / "equity_curve_hourly_native_daily.csv"
    if not daily_csv.exists():
        raise FileNotFoundError(f"Missing {daily_csv}; run export_hourly_native.py first")

    df = pd.read_csv(daily_csv, parse_dates=["time"], index_col="time")
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    equity = df["equity"]

    sharpe = max_dd = None
    metrics_path = RESULTS_DIR / "robustness_hourly_native.json"
    if metrics_path.exists():
        import json

        m = json.loads(metrics_path.read_text())["baseline_daily_compounded"]
        sharpe = m["Sharpe"]
        max_dd = m["MaxDD"]

    out = RESULTS_DIR / "equity_curve_hourly_native_daily.png"
    plot_equity(equity, out, oos_start=oos, sharpe=sharpe, max_dd=max_dd)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
