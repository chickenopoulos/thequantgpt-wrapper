"""Study correlation clustering regimes and directional predictability by pair."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from binance_market_indicators import (
    CORR_WINDOW,
    FUTURES_PATH,
    load_close_panel,
    rolling_mean_pairwise_corr,
)

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs" / "7"
OOS = pd.Timestamp("2025-01-01", tz="UTC")
FORWARD_HORIZONS = (1, 5, 10)
MIN_HISTORY_DAYS = 365
LIQUIDITY_TOP_N = 50


def expanding_corr_quintile(corr: pd.Series) -> pd.Series:
    """Quintile of market correlation using only past data (1-bar lag)."""
    lagged = corr.shift(1)
    ranks = lagged.expanding(min_periods=120).rank(pct=True)
    quintile = np.ceil(ranks * 5).clip(1, 5)
    return quintile.rename("corr_quintile")


def forward_returns(close: pd.DataFrame, horizons: tuple[int, ...]) -> dict[int, pd.DataFrame]:
  out: dict[int, pd.DataFrame] = {}
  for h in horizons:
    out[h] = close.pct_change(h).shift(-h)
  return out


def pair_beta_to_btc(returns: pd.DataFrame, btc_col: str = "BTCUSDT", window: int = 90) -> pd.DataFrame:
    btc = returns[btc_col]
    betas = {}
    for col in returns.columns:
        if col == btc_col:
            continue
        cov = returns[col].rolling(window).cov(btc)
        var = btc.rolling(window).var()
        betas[col] = cov / var
    return pd.DataFrame(betas)


def regime_forward_stats(
    fwd: pd.DataFrame,
    quintile: pd.Series,
    *,
    sample: str,
) -> pd.DataFrame:
    rows = []
    q_aligned = quintile.reindex(fwd.index)
    for q in range(1, 6):
        mask = q_aligned == q
        for col in fwd.columns:
            r = fwd.loc[mask, col].dropna()
            if len(r) < 30:
                continue
            mean = r.mean()
            std = r.std()
            tstat = mean / (std / np.sqrt(len(r))) if std > 0 else np.nan
            rows.append(
                {
                    "sample": sample,
                    "quintile": q,
                    "asset": col,
                    "n": len(r),
                    "mean_fwd_ret": mean,
                    "std_fwd_ret": std,
                    "tstat": tstat,
                    "hit_rate": (r > 0).mean(),
                }
            )
    return pd.DataFrame(rows)


def spread_signal_stats(fwd: pd.DataFrame, quintile: pd.Series) -> pd.DataFrame:
    """Long Q1 (low corr) vs short Q5 (high corr) spread per asset."""
    rows = []
    q_aligned = quintile.reindex(fwd.index)
    for col in fwd.columns:
        q1 = fwd.loc[q_aligned == 1, col].dropna()
        q5 = fwd.loc[q_aligned == 5, col].dropna()
        if len(q1) < 20 or len(q5) < 20:
            continue
        spread_mean = q1.mean() - q5.mean()
        pooled = pd.concat([q1, -q5])
        std = pooled.std()
        tstat = spread_mean / (std / np.sqrt(min(len(q1), len(q5)))) if std > 0 else np.nan
        rows.append(
            {
                "asset": col,
                "q1_mean": q1.mean(),
                "q5_mean": q5.mean(),
                "spread_q1_minus_q5": spread_mean,
                "tstat": tstat,
                "q1_hit": (q1 > 0).mean(),
                "q5_hit": (q5 > 0).mean(),
            }
        )
    return pd.DataFrame(rows).sort_values("spread_q1_minus_q5", ascending=False)


def select_liquid_universe(close: pd.DataFrame, top_n: int) -> list[str]:
    """Rank by median dollar volume proxy using close * volume if available; else history length."""
    # Use pairs with longest history as liquidity proxy when volume not loaded
    counts = close.notna().sum().sort_values(ascending=False)
    majors = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT"]
    top = [a for a in majors if a in close.columns]
    for asset in counts.index:
        if asset not in top:
            top.append(asset)
        if len(top) >= top_n:
            break
    return top[:top_n]


def plot_regime_bars(btc_stats: pd.DataFrame, out_path: Path, horizon: int) -> None:
    sub = btc_stats[btc_stats["asset"] == "BTCUSDT"].sort_values("quintile")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = ["#27ae60", "#82e0aa", "#f4d03f", "#e67e22", "#c0392b"]
    ax.bar(sub["quintile"], sub["mean_fwd_ret"] * 100, color=colors, edgecolor="white")
    ax.axhline(0, color="gray", linewidth=0.8)
    ax.set_xlabel("Correlation quintile (1=low, 5=high)")
    ax.set_ylabel(f"Mean {horizon}d forward return (%)")
    ax.set_title(f"BTC forward returns by prior-day correlation regime")
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_spread_heatmap(spread_df: pd.DataFrame, out_path: Path, top_k: int = 25) -> None:
    top = spread_df.head(top_k)
    bottom = spread_df.tail(top_k).iloc[::-1]
    combined = pd.concat([top, bottom])
    fig, ax = plt.subplots(figsize=(9, 10))
    y = np.arange(len(combined))
    colors = ["#27ae60" if x > 0 else "#c0392b" for x in combined["spread_q1_minus_q5"]]
    ax.barh(y, combined["spread_q1_minus_q5"] * 100, color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(combined["asset"], fontsize=8)
    ax.axvline(0, color="gray", linewidth=0.8)
    ax.set_xlabel("Mean fwd return spread: low-corr Q1 minus high-corr Q5 (%)")
    ax.set_title("Pairs where correlation regime matters most (5d horizon)")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_corr_episodes(corr: pd.Series, btc: pd.Series, out_path: Path) -> None:
    q75 = corr.expanding(min_periods=120).quantile(0.75).shift(1)
    q25 = corr.expanding(min_periods=120).quantile(0.25).shift(1)
    high = corr > q75
    low = corr < q25

    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    axes[0].plot(btc.index, btc.values, color="#f7931a", linewidth=1)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("BTC")
    axes[0].set_title("BTC price with correlation cluster shading")
    axes[0].grid(alpha=0.3)

    axes[1].plot(corr.index, corr.values, color="#8e44ad", linewidth=1)
    axes[1].fill_between(corr.index, 0, 1, where=high, transform=axes[1].get_xaxis_transform(),
                         color="#c0392b", alpha=0.15, label="High-corr cluster (top quartile)")
    axes[1].fill_between(corr.index, 0, 1, where=low, transform=axes[1].get_xaxis_transform(),
                         color="#27ae60", alpha=0.15, label="Low-corr cluster (bottom quartile)")
    axes[1].set_ylabel("Market corr")
    axes[1].set_xlabel("Date")
    axes[1].legend(loc="upper right", fontsize=8)
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def main() -> None:
    close = load_close_panel(FUTURES_PATH)
    returns = close.pct_change()
    corr = rolling_mean_pairwise_corr(returns)
    quintile = expanding_corr_quintile(corr)
    fwd = forward_returns(close, FORWARD_HORIZONS)

    liquid = select_liquid_universe(close, LIQUIDITY_TOP_N)
    fwd_liquid = {h: fwd[h][liquid] for h in FORWARD_HORIZONS}

    is_mask = quintile.index < OOS
    oos_mask = quintile.index >= OOS

    all_stats = []
    spread_tables = {}
    aligned_quintile = quintile.reindex(close.index)
    for h in FORWARD_HORIZONS:
        for label, mask in [("in_sample", is_mask), ("out_of_sample", oos_mask), ("full", slice(None))]:
            q = aligned_quintile if mask is slice(None) else aligned_quintile.loc[mask]
            stats = regime_forward_stats(fwd[h], q, sample=label)
            stats["horizon"] = h
            all_stats.append(stats)
        spread_tables[h] = spread_signal_stats(fwd_liquid[h], aligned_quintile)

    stats_df = pd.concat(all_stats, ignore_index=True)
    beta = pair_beta_to_btc(returns[liquid], window=90)
    median_beta = beta.median().sort_values(ascending=False)

    # Attach beta bucket to spread results for 5d horizon
    spread5 = spread_tables[5].copy()
    spread5["median_beta_90d"] = spread5["asset"].map(median_beta)
    spread5["beta_bucket"] = pd.qcut(spread5["median_beta_90d"].rank(method="first"), 3, labels=["low_beta", "mid_beta", "high_beta"])

    artifacts = RUN / "artifacts"
    charts = RUN / "charts"
    artifacts.mkdir(parents=True, exist_ok=True)
    charts.mkdir(parents=True, exist_ok=True)

    stats_df.to_parquet(artifacts / "corr_regime_forward_stats.parquet")
    for h, tbl in spread_tables.items():
        tbl.to_parquet(artifacts / f"corr_spread_q1_q5_h{h}.parquet")

    btc_is = stats_df[(stats_df["asset"] == "BTCUSDT") & (stats_df["sample"] == "in_sample")]
    plot_regime_bars(btc_is, charts / "btc_corr_regime_returns_5d.png", horizon=5)
    plot_spread_heatmap(spread5, charts / "corr_spread_by_pair.png")
    plot_corr_episodes(corr, close["BTCUSDT"], charts / "corr_cluster_episodes.png")

    # Summarize findings
    btc5 = stats_df[(stats_df["asset"] == "BTCUSDT") & (stats_df["horizon"] == 5)]
    btc_is5 = btc5[btc5["sample"] == "in_sample"].set_index("quintile")["mean_fwd_ret"]
    btc_oos5 = btc5[btc5["sample"] == "out_of_sample"].set_index("quintile")["mean_fwd_ret"]

    top_long_low_corr = spread5.head(10)[["asset", "spread_q1_minus_q5", "tstat", "median_beta_90d"]]
    top_short_low_corr = spread5.tail(10)[["asset", "spread_q1_minus_q5", "tstat", "median_beta_90d"]]

    # Full-universe spread for pairs that favor high-corr regimes
    spread5_full = spread_signal_stats(fwd[5], aligned_quintile)
    favor_high_corr = spread5_full.nsmallest(10, "spread_q1_minus_q5")[
        ["asset", "spread_q1_minus_q5", "tstat"]
    ]

    bucket_summary = (
        spread5.groupby("beta_bucket", observed=True)["spread_q1_minus_q5"]
        .agg(["mean", "count"])
        .reset_index()
    )

    findings = {
        "method": {
            "corr_window": CORR_WINDOW,
            "signal_lag_bars": 1,
            "quintile_method": "expanding percentile rank on lagged market correlation",
            "forward_horizons_days": list(FORWARD_HORIZONS),
            "oos_start": str(OOS.date()),
        },
        "btc_5d_mean_fwd_by_quintile": {
            "in_sample": {int(k): float(v) for k, v in btc_is5.items()},
            "out_of_sample": {int(k): float(v) for k, v in btc_oos5.items()},
        },
        "interpretation": {
            "high_corr_cluster": "Top correlation quintile — broad risk-on/off coupling; alts move with BTC.",
            "low_corr_cluster": "Bottom quintile — dispersion; idiosyncratic moves dominate.",
        },
        "directional_signal": {
            "btc": {
                "rule": "Low prior-day correlation (Q1) vs high (Q5) favors long BTC on 5d horizon",
                "is_spread_q1_minus_q5": float(btc_is5.get(1, np.nan) - btc_is5.get(5, np.nan)),
                "oos_spread_q1_minus_q5": float(btc_oos5.get(1, np.nan) - btc_oos5.get(5, np.nan)),
            },
            "best_pairs_long_when_low_corr": top_long_low_corr.to_dict(orient="records"),
            "best_pairs_short_when_low_corr_or_long_when_high_corr": top_short_low_corr.to_dict(orient="records"),
            "full_universe_favor_high_corr": favor_high_corr.to_dict(orient="records"),
            "full_universe_counts": {
                "n_positive_spread": int((spread5_full["spread_q1_minus_q5"] > 0).sum()),
                "n_negative_spread": int((spread5_full["spread_q1_minus_q5"] < 0).sum()),
            },
            "beta_bucket_avg_spread_q1_minus_q5": bucket_summary.to_dict(orient="records"),
        },
    }
    (artifacts / "corr_cluster_findings.json").write_text(json.dumps(findings, indent=2), encoding="utf-8")

    # Report
    report_lines = [
        "# Correlation clustering & directional signal study",
        "",
        "## What happens when correlations cluster?",
        "",
        "When **market correlation rises into the top quintile**, returns become highly synchronized — "
        "typical of liquidation cascades, macro shocks, and beta compression across alts. "
        "**Low-correlation clusters** (bottom quintile) are dispersion regimes where pairs diverge from BTC.",
        "",
        "## BTC directional signal (5d forward, 1-bar lag)",
        "",
        "| Quintile | IS mean 5d fwd | OOS mean 5d fwd |",
        "|----------|----------------|-----------------|",
    ]
    for q in range(1, 6):
        is_v = btc_is5.get(q, np.nan) * 100
        oos_v = btc_oos5.get(q, np.nan) * 100
        report_lines.append(f"| Q{q} ({'low' if q==1 else 'high' if q==5 else 'mid'} corr) | {is_v:+.2f}% | {oos_v:+.2f}% |")

    report_lines += [
        "",
        f"**IS Q1−Q5 spread:** {(btc_is5.get(1,0)-btc_is5.get(5,0))*100:+.2f}%",
        f"**OOS Q1−Q5 spread:** {(btc_oos5.get(1,0)-btc_oos5.get(5,0))*100:+.2f}%",
        "",
        "## Pairs with strongest regime signal (5d, Q1−Q5 spread)",
        "",
        "### Outperform in low-corr / underperform in high-corr",
        "",
        "| Pair | Spread | t-stat | Median β |",
        "|------|--------|--------|----------|",
    ]
    for _, row in top_long_low_corr.iterrows():
        report_lines.append(
            f"| {row['asset']} | {row['spread_q1_minus_q5']*100:+.2f}% | {row['tstat']:.2f} | {row['median_beta_90d']:.2f} |"
        )

    report_lines += [
        "",
        "### Opposite: hurt by low-corr / helped by high-corr (beta-like)",
        "",
        "| Pair | Spread | t-stat | Median β |",
        "|------|--------|--------|----------|",
    ]
    for _, row in top_short_low_corr.iterrows():
        report_lines.append(
            f"| {row['asset']} | {row['spread_q1_minus_q5']*100:+.2f}% | {row['tstat']:.2f} | {row['median_beta_90d']:.2f} |"
        )

    report_lines += [
        "",
        "### Full universe: pairs that favor *high*-correlation clusters",
        "",
        "| Pair | Spread (Q1−Q5) | t-stat |",
        "|------|----------------|--------|",
    ]
    for _, row in favor_high_corr.iterrows():
        report_lines.append(
            f"| {row['asset']} | {row['spread_q1_minus_q5']*100:+.2f}% | {row['tstat']:.2f} |"
        )

    report_lines += [
        "",
        "## Charts",
        "",
        "![BTC regime returns](charts/btc_corr_regime_returns_5d.png)",
        "![Pair spreads](charts/corr_spread_by_pair.png)",
        "![Cluster episodes](charts/corr_cluster_episodes.png)",
        "",
    ]
    (RUN / "report_corr_clusters.md").write_text("\n".join(report_lines), encoding="utf-8")

    print(json.dumps(findings["directional_signal"], indent=2))


if __name__ == "__main__":
    main()
