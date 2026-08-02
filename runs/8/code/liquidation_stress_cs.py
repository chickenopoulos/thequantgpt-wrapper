"""Cross-sectional liquidation-stress factor on Binance USDT-M perps."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs" / "8"
DATA = REPO / "data"

OOS = pd.Timestamp("2025-01-01", tz="UTC")
ANN = 365
LAG = 1
FEE = 0.00045
SLIPPAGE = 0.0005
LIQ_Z_WINDOW = 30
MIN_UNIVERSE = 30
TOP_PCT = 0.1
BOTTOM_PCT = 0.1


def load_coinglass_panel(path_rel: str, value_col: str) -> pd.DataFrame:
    path = DATA / "coinglass" / path_rel
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return (
        df.pivot_table(index="date", columns="symbol", values=value_col, aggfunc="last")
        .sort_index()
        .astype(float)
    )


def load_close_panel() -> pd.DataFrame:
    df = pd.read_parquet(DATA / "binance" / "binance_futures_ohlcv_1d.parquet", columns=["time", "asset", "close"])
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df.pivot_table(index="time", columns="asset", values="close", aggfunc="last").sort_index().astype(float)


def align_universe(*panels: pd.DataFrame) -> tuple[pd.DataFrame, ...]:
    symbols = panels[0].columns
    for p in panels[1:]:
        symbols = symbols.intersection(p.columns)
    symbols = symbols.sort_values()
    idx = panels[0].index
    for p in panels[1:]:
        idx = idx.intersection(p.index)
    idx = idx.sort_values()
    return tuple(p.reindex(index=idx, columns=symbols) for p in panels)


def build_stress_signal(
    funding: pd.DataFrame,
    oi: pd.DataFrame,
    liq_long: pd.DataFrame,
    liq_short: pd.DataFrame,
) -> pd.DataFrame:
    """Cross-sectional stress: crowded funding + OI + liquidation spike."""
    fund_rank = funding.rank(axis=1, pct=True, method="average")
    oi_rank = oi.rank(axis=1, pct=True, method="average")

    liq_total = liq_long.add(liq_short, fill_value=0.0)
    liq_mu = liq_total.rolling(LIQ_Z_WINDOW, min_periods=max(10, LIQ_Z_WINDOW // 3)).mean()
    liq_sd = liq_total.rolling(LIQ_Z_WINDOW, min_periods=max(10, LIQ_Z_WINDOW // 3)).std()
    liq_z = liq_total.sub(liq_mu).div(liq_sd.replace(0, np.nan))
    liq_rank = liq_z.rank(axis=1, pct=True, method="average")

    stress = (fund_rank + oi_rank + liq_rank) / 3.0
    return stress.shift(LAG)


def cross_section_ls_returns(
    wide_close: pd.DataFrame,
    signal: pd.DataFrame,
    *,
    top_pct: float = TOP_PCT,
    bottom_pct: float = BOTTOM_PCT,
    invert: bool = False,
    long_only: bool = False,
    apply_costs: bool = True,
) -> pd.Series:
    rets = wide_close.pct_change()
    fwd = rets.shift(-1)
    port = pd.Series(np.nan, index=wide_close.index, dtype=float)

    for t in signal.index:
        row = signal.loc[t].dropna()
        if len(row) < MIN_UNIVERSE:
            continue
        n_top = max(1, int(len(row) * top_pct))
        n_bot = max(1, int(len(row) * bottom_pct))
        top = row.nlargest(n_top).index
        bot = row.nsmallest(n_bot).index
        f = fwd.loc[t].reindex(row.index).dropna()
        if f.empty:
            continue
        if long_only:
            leg = f.reindex(top).mean()
        elif invert:
            leg = f.reindex(bot).mean() - f.reindex(top).mean()
        else:
            leg = f.reindex(top).mean() - f.reindex(bot).mean()
        port.loc[t] = leg

    gross_turnover = 2.0 if not long_only else 1.0
    costs = gross_turnover * (FEE + SLIPPAGE) if apply_costs else 0.0
    return (port - costs).dropna()


def metrics_from_returns(returns: pd.Series, oos: pd.Timestamp = OOS) -> dict:
    r = returns.dropna()
    if r.empty or len(r) < 30:
        return {
            "Sharpe": 0.0,
            "CAGR": 0.0,
            "MaxDD": 0.0,
            "trades": 0,
            "in_sample": {"Sharpe": 0.0, "CAGR": 0.0, "MaxDD": 0.0},
            "out_of_sample": {"Sharpe": 0.0, "CAGR": 0.0, "MaxDD": 0.0},
        }

    def _slice_metrics(x: pd.Series) -> dict:
        x = x.dropna()
        if len(x) < 20:
            return {"Sharpe": 0.0, "CAGR": 0.0, "MaxDD": 0.0}
        cum = (1 + x).cumprod()
        dd = cum / cum.cummax() - 1
        vol = x.std()
        sharpe = float(np.sqrt(ANN) * x.mean() / vol) if vol > 0 else 0.0
        cagr = float(cum.iloc[-1] ** (ANN / len(x)) - 1)
        return {"Sharpe": sharpe, "CAGR": cagr, "MaxDD": float(dd.min())}

    full = _slice_metrics(r)
    is_m = _slice_metrics(r[r.index < oos])
    oos_m = _slice_metrics(r[r.index >= oos])
    return {
        **full,
        "trades": int((r != 0).sum()),
        "in_sample": is_m,
        "out_of_sample": oos_m,
    }


def decile_forward_returns(
    close: pd.DataFrame,
    signal: pd.DataFrame,
    horizons: tuple[int, ...] = (1, 3, 5),
) -> dict:
    """Average cross-sectional forward return by stress decile (lag-safe)."""
    out: dict[str, dict] = {}
    for h in horizons:
        fwd = close.pct_change(h).shift(-h)
        bucket_rets: dict[int, list[float]] = {i: [] for i in range(1, 11)}

        for t in signal.index:
            row = signal.loc[t].dropna()
            if len(row) < MIN_UNIVERSE:
                continue
            try:
                dec = pd.qcut(row, 10, labels=False, duplicates="drop") + 1
            except ValueError:
                continue
            f = fwd.loc[t].reindex(row.index)
            for d in dec.unique():
                assets = dec.index[dec == d]
                vals = f.reindex(assets).dropna()
                if len(vals) >= 3:
                    bucket_rets[int(d)].append(float(vals.mean()))

        out[f"fwd_{h}d"] = {
            f"D{d}": float(np.mean(v)) if v else np.nan
            for d, v in bucket_rets.items()
        }
        spreads = []
        for t in signal.index:
            row = signal.loc[t].dropna()
            if len(row) < MIN_UNIVERSE:
                continue
            try:
                dec = pd.qcut(row, 10, labels=False, duplicates="drop")
            except ValueError:
                continue
            f = fwd.loc[t].reindex(row.index).dropna()
            if f.empty:
                continue
            top = f[dec == dec.max()].mean()
            bot = f[dec == dec.min()].mean()
            if pd.notna(top) and pd.notna(bot):
                spreads.append(float(top - bot))
        out[f"fwd_{h}d"]["top_minus_bottom_spread"] = float(np.mean(spreads)) if spreads else np.nan
    return out


def plot_equity(curves: dict[str, pd.Series], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 5))
    for name, rets in curves.items():
        eq = (1 + rets.fillna(0)).cumprod()
        ax.plot(eq.index, eq.values, label=name, linewidth=1.2)
    ax.axvline(OOS, color="gray", linestyle="--", linewidth=0.9, label="OOS start")
    ax.set_title("Liquidation stress cross-sectional strategies")
    ax.set_ylabel("Growth of $1")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_drawdown(curves: dict[str, pd.Series], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 4))
    for name, rets in curves.items():
        eq = (1 + rets.fillna(0)).cumprod()
        dd = eq / eq.cummax() - 1
        ax.plot(dd.index, dd.values, label=name, linewidth=1.0)
    ax.axvline(OOS, color="gray", linestyle="--", linewidth=0.9)
    ax.set_title("Drawdown")
    ax.set_ylabel("Drawdown")
    ax.legend(loc="lower left", fontsize=9)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_decile_bars(deciles: dict, out_path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=False)
    for ax, h in zip(axes, (1, 3, 5), strict=True):
        key = f"fwd_{h}d"
        vals = deciles[key]
        xs = [f"D{d}" for d in range(1, 11) if f"D{d}" in vals]
        ys = [vals[x] * 100 for x in xs]
        colors = ["#27ae60" if y >= 0 else "#c0392b" for y in ys]
        ax.bar(xs, ys, color=colors, alpha=0.85)
        spread = vals.get("top_minus_bottom_spread", np.nan)
        ax.set_title(f"{h}d forward return by stress decile\n(top-bottom spread: {spread*100:.3f}%)")
        ax.set_xlabel("Stress decile (D10 = highest)")
        ax.set_ylabel("Avg return (%)")
        ax.axhline(0, color="black", linewidth=0.6)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Forward returns vs liquidation-stress decile", y=1.02, fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    close = load_close_panel()
    funding = load_coinglass_panel("futures_funding_rate_binance_1d.parquet", "close")
    oi = load_coinglass_panel("futures_open_interest_history_ohlc_binance_1d.parquet", "close")
    liq_long = load_coinglass_panel("futures_liquidations_binance_1d.parquet", "long_liquidation_usd")
    liq_short = load_coinglass_panel("futures_liquidations_binance_1d.parquet", "short_liquidation_usd")

    close, funding, oi, liq_long, liq_short = align_universe(close, funding, oi, liq_long, liq_short)
    stress = build_stress_signal(funding, oi, liq_long, liq_short)

    # Drop warmup where stress is mostly NaN
    valid_days = stress.notna().sum(axis=1)
    start = valid_days[valid_days >= MIN_UNIVERSE].index.min()
    close = close.loc[start:]
    stress = stress.loc[start:]

    strategies = {
        "fade_stress_ls": cross_section_ls_returns(close, stress, invert=False),
        "continuation_ls": cross_section_ls_returns(close, stress, invert=True),
        "fade_stress_long_only": cross_section_ls_returns(close, stress, long_only=True),
    }
    strategies_gross = {
        "fade_stress_ls": cross_section_ls_returns(close, stress, invert=False, apply_costs=False),
        "continuation_ls": cross_section_ls_returns(close, stress, invert=True, apply_costs=False),
        "fade_stress_long_only": cross_section_ls_returns(close, stress, long_only=True, apply_costs=False),
    }

    deciles = decile_forward_returns(close, stress)
    metrics = {
        name: metrics_from_returns(rets)
        for name, rets in strategies.items()
    }
    metrics_gross = {
        name: metrics_from_returns(rets)
        for name, rets in strategies_gross.items()
    }

    universe_summary = {
        "n_symbols": int(close.shape[1]),
        "start": str(close.index.min()),
        "end": str(close.index.max()),
        "avg_daily_universe": float(stress.notna().sum(axis=1).mean()),
        "oos_start": str(OOS.date()),
    }

    artifacts_dir = RUN / "artifacts"
    charts_dir = RUN / "charts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "universe": universe_summary,
        "decile_forward_returns": deciles,
        "strategies": metrics,
        "strategies_gross": metrics_gross,
        "signal_definition": {
            "composite": "mean(cs_rank(funding), cs_rank(OI), cs_rank(liq_z))",
            "liq_z_window": LIQ_Z_WINDOW,
            "lag_bars": LAG,
        },
    }
    (artifacts_dir / "metrics.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (artifacts_dir / "decile_forward_returns.json").write_text(
        json.dumps(deciles, indent=2) + "\n", encoding="utf-8"
    )

    plot_equity(strategies, charts_dir / "equity_curve.png")
    plot_drawdown(strategies, charts_dir / "drawdown.png")
    plot_decile_bars(deciles, charts_dir / "stress_decile_forward_returns.png")

    fade = metrics["fade_stress_ls"]
    cont = metrics["continuation_ls"]
    fade_g = metrics_gross["fade_stress_ls"]
    cont_g = metrics_gross["continuation_ls"]
    lo_g = metrics_gross["fade_stress_long_only"]
    d1 = deciles["fwd_1d"]
    report = "\n".join(
        [
            "# Cross-sectional liquidation stress factor",
            "",
            f"- **Universe:** {universe_summary['n_symbols']} Binance USDT-M perps with Coinglass funding/OI/liquidations",
            f"- **Sample:** {universe_summary['start'][:10]} → {universe_summary['end'][:10]} "
            f"(avg {universe_summary['avg_daily_universe']:.0f} names/day)",
            f"- **OOS cut:** {universe_summary['oos_start']}",
            "",
            "## Signal",
            "",
            "Daily composite stress per symbol:",
            "`stress = mean(cs_percentile(funding), cs_percentile(OI), cs_percentile(liq_z))`, lagged 1 bar.",
            "",
            "**Hypothesis (fade):** highest-stress names mean-revert after a flush → long top decile / short bottom.",
            "",
            "## Decile forward returns (full sample)",
            "",
            f"| Horizon | D1 (low stress) | D10 (high stress) | Top − Bottom |",
            f"| --- | --- | --- | --- |",
            f"| 1d | {d1.get('D1', np.nan)*100:.3f}% | {d1.get('D10', np.nan)*100:.3f}% | "
            f"{d1.get('top_minus_bottom_spread', np.nan)*100:.3f}% |",
            f"| 3d | {deciles['fwd_3d'].get('D1', np.nan)*100:.3f}% | "
            f"{deciles['fwd_3d'].get('D10', np.nan)*100:.3f}% | "
            f"{deciles['fwd_3d'].get('top_minus_bottom_spread', np.nan)*100:.3f}% |",
            f"| 5d | {deciles['fwd_5d'].get('D1', np.nan)*100:.3f}% | "
            f"{deciles['fwd_5d'].get('D10', np.nan)*100:.3f}% | "
            f"{deciles['fwd_5d'].get('top_minus_bottom_spread', np.nan)*100:.3f}% |",
            "",
            "## Tradable sleeves (daily rebalance, decile L/S)",
            "",
            "### Fade stress (long crowded/flushed, short calm)",
            f"- Full-sample Sharpe: **{fade['Sharpe']:.2f}**, CAGR: **{fade['CAGR']*100:.1f}%**, MaxDD: **{fade['MaxDD']*100:.1f}%**",
            f"- IS Sharpe: {fade['in_sample']['Sharpe']:.2f} | OOS Sharpe: {fade['out_of_sample']['Sharpe']:.2f}",
            "",
            "### Continuation (inverse)",
            f"- Full-sample Sharpe: **{cont['Sharpe']:.2f}**, CAGR: **{cont['CAGR']*100:.1f}%**, MaxDD: **{cont['MaxDD']*100:.1f}%**",
            f"- IS Sharpe: {cont['in_sample']['Sharpe']:.2f} | OOS Sharpe: {cont['out_of_sample']['Sharpe']:.2f}",
            "",
            "## Gross returns (no fees/slippage)",
            "",
            "| Sleeve | Full Sharpe | IS Sharpe | OOS Sharpe | CAGR | MaxDD |",
            "| --- | --- | --- | --- | --- | --- |",
            f"| Fade stress L/S | {fade_g['Sharpe']:.2f} | {fade_g['in_sample']['Sharpe']:.2f} | "
            f"{fade_g['out_of_sample']['Sharpe']:.2f} | {fade_g['CAGR']*100:.1f}% | {fade_g['MaxDD']*100:.1f}% |",
            f"| Continuation L/S | {cont_g['Sharpe']:.2f} | {cont_g['in_sample']['Sharpe']:.2f} | "
            f"{cont_g['out_of_sample']['Sharpe']:.2f} | {cont_g['CAGR']*100:.1f}% | {cont_g['MaxDD']*100:.1f}% |",
            f"| Fade long-only | {lo_g['Sharpe']:.2f} | {lo_g['in_sample']['Sharpe']:.2f} | "
            f"{lo_g['out_of_sample']['Sharpe']:.2f} | {lo_g['CAGR']*100:.1f}% | {lo_g['MaxDD']*100:.1f}% |",
            "",
            "## Charts",
            "",
            "![Equity](charts/equity_curve.png)",
            "",
            "![Deciles](charts/stress_decile_forward_returns.png)",
            "",
            "![Drawdown](charts/drawdown.png)",
        ]
    )
    (RUN / "report.md").write_text(report + "\n", encoding="utf-8")

    print(json.dumps({"universe": universe_summary, "fade_stress_ls": fade, "continuation_ls": cont, "gross": metrics_gross}, indent=2))


if __name__ == "__main__":
    main()
