"""Binance cross-section market breadth and correlation indicators."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs" / "7"
DATA = REPO / "data"
FUTURES_PATH = DATA / "binance" / "binance_futures_ohlcv_1d.parquet"

SMA_WINDOW = 90
CORR_WINDOW = 30
MIN_UNIVERSE = 20


def load_close_panel(path: Path) -> pd.DataFrame:
    """Load daily close prices for all Binance futures USDT pairs."""
    df = pd.read_parquet(path, columns=["time", "asset", "close"])
    df["time"] = pd.to_datetime(df["time"], utc=True)
    close = (
        df.pivot_table(index="time", columns="asset", values="close", aggfunc="last")
        .sort_index()
        .astype(float)
    )
    return close


def market_depth_pct(close: pd.DataFrame, window: int = SMA_WINDOW) -> pd.Series:
    """Share of pairs trading above their N-day SMA."""
    sma = close.rolling(window, min_periods=window).mean()
    above = close > sma
    valid = close.notna() & sma.notna()
    n_valid = valid.sum(axis=1)
    depth = above.where(valid).sum(axis=1) / n_valid.replace(0, np.nan)
    depth = depth.where(n_valid >= MIN_UNIVERSE)
    return (depth * 100.0).rename("market_depth_pct")


def rolling_mean_pairwise_corr(returns: pd.DataFrame, window: int = CORR_WINDOW) -> pd.Series:
    """Average pairwise correlation across the cross-section over a rolling window."""
    values = returns.to_numpy(dtype=float)
    index = returns.index
    out = np.full(len(index), np.nan)

    for i in range(window, len(index)):
        block = values[i - window : i]
        valid_cols = np.sum(~np.isnan(block), axis=0) >= window
        if valid_cols.sum() < 2:
            continue
        block = block[:, valid_cols]
        corr = np.corrcoef(block, rowvar=False)
        upper = corr[np.triu_indices(corr.shape[0], k=1)]
        if upper.size:
            out[i] = upper.mean()

    return pd.Series(out, index=index, name="market_corr_30d")


def plot_indicators(
    btc_close: pd.Series,
    depth: pd.Series,
    corr: pd.Series,
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    fig.suptitle(
        "Binance USDT-M Perpetuals — BTC Price, Market Depth & Correlation",
        fontsize=13,
        y=0.98,
    )

    axes[0].plot(btc_close.index, btc_close.values, color="#f7931a", linewidth=1.2)
    axes[0].set_ylabel("BTC Close (USDT)")
    axes[0].set_yscale("log")
    axes[0].grid(True, alpha=0.3)
    axes[0].set_title("Bitcoin Close Price", loc="left", fontsize=11)

    axes[1].plot(depth.index, depth.values, color="#2e86de", linewidth=1.2)
    axes[1].axhline(50, color="gray", linestyle="--", linewidth=0.8, alpha=0.7)
    axes[1].set_ylabel("% Above 90d SMA")
    axes[1].set_ylim(0, 100)
    axes[1].grid(True, alpha=0.3)
    axes[1].set_title("Market Depth (% of pairs above 90-day SMA)", loc="left", fontsize=11)

    axes[2].plot(corr.index, corr.values, color="#8e44ad", linewidth=1.2)
    axes[2].set_ylabel("Avg Pairwise Corr")
    axes[2].set_xlabel("Date (UTC)")
    axes[2].grid(True, alpha=0.3)
    axes[2].set_title("Market Correlation (30-day rolling avg cross-section)", loc="left", fontsize=11)

    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    axes[2].xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    fig.autofmt_xdate()
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def main() -> None:
    close = load_close_panel(FUTURES_PATH)
    btc = close["BTCUSDT"].dropna()

    depth = market_depth_pct(close)
    returns = close.pct_change()
    corr = rolling_mean_pairwise_corr(returns)

    chart_path = RUN / "charts" / "binance_market_indicators.png"
    plot_indicators(btc, depth, corr, chart_path)

    aligned = pd.concat(
        {
            "btc_close": btc,
            "market_depth_pct": depth,
            "market_corr_30d": corr,
        },
        axis=1,
    ).dropna(how="all")

    artifacts_dir = RUN / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    aligned.to_parquet(artifacts_dir / "market_indicators.parquet")
    summary = {
        "universe": "binance_futures_usdt_perpetuals",
        "data_source": str(FUTURES_PATH.relative_to(REPO)),
        "n_assets": int(close.shape[1]),
        "start": str(close.index.min()),
        "end": str(close.index.max()),
        "sma_window": SMA_WINDOW,
        "corr_window": CORR_WINDOW,
        "latest": {
            "btc_close": float(btc.iloc[-1]),
            "market_depth_pct": float(depth.dropna().iloc[-1]),
            "market_corr_30d": float(corr.dropna().iloc[-1]),
        },
    }
    (artifacts_dir / "market_indicators_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    report = RUN / "report.md"
    report.write_text(
        "\n".join(
            [
                "# Binance market breadth & correlation",
                "",
                f"- **Universe:** Binance USDT-M perpetual futures ({summary['n_assets']} pairs)",
                f"- **Data:** `{summary['data_source']}`",
                f"- **Range:** {summary['start'][:10]} → {summary['end'][:10]}",
                "",
                "## Latest readings",
                "",
                f"| Indicator | Value |",
                f"|-----------|-------|",
                f"| BTC close | {summary['latest']['btc_close']:,.2f} |",
                f"| Market depth (% > 90d SMA) | {summary['latest']['market_depth_pct']:.1f}% |",
                f"| Market correlation (30d avg) | {summary['latest']['market_corr_30d']:.3f} |",
                "",
                f"![Market indicators](charts/binance_market_indicators.png)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {chart_path}")
    print(json.dumps(summary["latest"], indent=2))


if __name__ == "__main__":
    main()
