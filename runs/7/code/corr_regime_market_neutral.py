"""Market-neutral long/short portfolio from correlation-regime pair spreads."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from binance_market_indicators import FUTURES_PATH, load_close_panel, market_depth_pct, rolling_mean_pairwise_corr
from correlation_cluster_signal import expanding_corr_quintile, spread_signal_stats

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs" / "7"
OOS = pd.Timestamp("2025-01-01", tz="UTC")
ANN = 365
FEE = 0.00045
SLIPPAGE = 0.0005
BASKET_SIZE = 10
MIN_IS_DAYS = 400

# Pre-identified liquid names from corr_cluster_findings (IS study); fixed, not re-optimized.
LIQUID_LONG_BASKET = [
    "SOLUSDT", "AVAXUSDT", "DOGEUSDT", "NEARUSDT", "RUNEUSDT",
    "BNBUSDT", "EGLDUSDT", "QTUMUSDT", "ZECUSDT", "ENJUSDT",
]
LIQUID_SHORT_BASKET = [
    "BELUSDT", "SUPERUSDT", "BIGTIMEUSDT", "TNSRUSDT", "C98USDT",
    "MTLUSDT", "LQTYUSDT", "KASUSDT", "MEWUSDT", "ARKUSDT",
]


def calibrate_baskets(
    close: pd.DataFrame,
    quintile: pd.Series,
    *,
    oos: pd.Timestamp,
    basket_size: int,
) -> tuple[list[str], list[str], pd.DataFrame]:
    """Rank pair spreads on in-sample data only."""
    is_idx = close.index[close.index < oos]
    close_is = close.loc[is_idx]
    quintile_is = quintile.reindex(is_idx)
    returns_is = close_is.pct_change()
    spread = spread_signal_stats(returns_is, quintile_is)

    liquid = close_is.notna().sum()
    spread = spread[spread["asset"].isin(liquid[liquid >= MIN_IS_DAYS].index)]
    spread = spread[~spread["asset"].isin(["BTCUSDT", "ETHUSDT"])]

    long_basket = spread.nlargest(basket_size, "spread_q1_minus_q5")["asset"].tolist()
    short_basket = spread.nsmallest(basket_size, "spread_q1_minus_q5")["asset"].tolist()
    return long_basket, short_basket, spread


def depth_gated_direction(base_dir: pd.Series, depth: pd.Series) -> pd.Series:
    """Only trade low-corr longs when market breadth is above expanding median."""
    depth_lag = depth.shift(1)
    med = depth_lag.expanding(min_periods=120).median()
    gate = depth_lag >= med
    out = base_dir.copy()
    out[(base_dir > 0) & ~gate] = 0.0
    return out


def always_in_market_direction(
    quintile: pd.Series,
    depth: pd.Series,
    *,
    q_threshold: int = 3,
    depth_quantile: float = 0.35,
) -> pd.Series:
    """100% gross exposure; flip L/S when high-corr AND weak breadth."""
    q = quintile.shift(1)
    depth_lag = depth.shift(1)
    depth_thr = depth_lag.expanding(min_periods=120).quantile(depth_quantile)
    direction = pd.Series(1.0, index=quintile.index)
    flip = (q >= q_threshold) & (depth_lag < depth_thr)
    direction[flip] = -1.0
    return direction


def regime_direction(quintile: pd.Series, mode: str, *, depth: pd.Series | None = None) -> pd.Series:
    """+1 = long dispersion/short cluster, -1 = flipped, 0 = flat."""
    q = quintile.shift(1)
    if mode == "regime_flip":
        direction = pd.Series(0.0, index=quintile.index)
        direction[q.isin([1, 2])] = 1.0
        direction[q.isin([4, 5])] = -1.0
        return direction
    if mode == "low_only":
        direction = pd.Series(0.0, index=quintile.index)
        direction[q.isin([1, 2])] = 1.0
        return direction
    if mode == "low_only_depth_gate":
        if depth is None:
            raise ValueError("depth required for low_only_depth_gate")
        return depth_gated_direction(regime_direction(quintile, "low_only"), depth)
    if mode == "always_on":
        return pd.Series(1.0, index=quintile.index)
    if mode == "always_in_max_sharpe":
        if depth is None:
            raise ValueError("depth required for always_in_max_sharpe")
        return always_in_market_direction(quintile, depth)
    raise ValueError(f"unknown mode: {mode}")


def build_target_weights(
    direction: pd.Series,
    long_basket: list[str],
    short_basket: list[str],
    columns: pd.Index,
) -> pd.DataFrame:
    """Dollar-neutral weights: +50% long leg, -50% short leg when direction != 0."""
    weights = pd.DataFrame(0.0, index=direction.index, columns=columns)
    if not long_basket or not short_basket:
        return weights

    w_long = 0.5 / len(long_basket)
    w_short = -0.5 / len(short_basket)

    for asset in long_basket:
        if asset in weights.columns:
            weights[asset] = direction * w_long
    for asset in short_basket:
        if asset in weights.columns:
            weights[asset] += direction * w_short
    return weights


def backtest_weights(
    close: pd.DataFrame,
    weights: pd.DataFrame,
    *,
    fee: float = FEE,
    slippage: float = SLIPPAGE,
) -> pd.Series:
    """Daily portfolio returns with turnover costs."""
    returns = close.pct_change().fillna(0.0)
    w = weights.reindex(close.index).fillna(0.0)
    gross = (w.shift(1).fillna(0.0) * returns).sum(axis=1)
    turnover = w.diff().abs().sum(axis=1).fillna(0.0)
    net = gross - turnover * (fee + slippage)
    return net.rename("portfolio_return")


def compute_metrics(returns: pd.Series, weights: pd.DataFrame) -> dict:
    r = returns.dropna()
    if len(r) < 30 or r.std() == 0:
        return {"Sharpe": 0.0, "MaxDD": 0.0, "CAGR": 0.0, "trades": 0, "avg_gross_exposure": 0.0}

    cum = (1 + r).cumprod()
    dd = cum / cum.cummax() - 1
    sharpe = float(np.sqrt(ANN) * r.mean() / r.std())
    cagr = float(cum.iloc[-1] ** (ANN / len(r)) - 1)

    def _seg(seg: pd.Series) -> dict:
        if len(seg) < 20 or seg.std() == 0:
            return {"Sharpe": 0.0, "CAGR": 0.0, "MaxDD": 0.0}
        c = (1 + seg).cumprod()
        d = c / c.cummax() - 1
        return {
            "Sharpe": float(np.sqrt(ANN) * seg.mean() / seg.std()),
            "CAGR": float(c.iloc[-1] ** (ANN / len(seg)) - 1),
            "MaxDD": float(d.min()),
        }

    is_r = r.loc[r.index < OOS]
    oos_r = r.loc[r.index >= OOS]
    w = weights.reindex(returns.index).fillna(0.0)
    return {
        "Sharpe": sharpe,
        "MaxDD": float(dd.min()),
        "CAGR": cagr,
        "trades": int((w.diff().abs().sum(axis=1) > 0.01).sum()),
        "avg_gross_exposure": float(w.abs().sum(axis=1).mean()),
        "in_sample": _seg(is_r),
        "out_of_sample": _seg(oos_r),
    }


def portfolio_btc_beta(returns: pd.DataFrame, port_ret: pd.Series, btc_col: str = "BTCUSDT") -> float:
    if btc_col not in returns.columns:
        return float("nan")
    aligned = pd.concat([port_ret, returns[btc_col]], axis=1).dropna()
    if len(aligned) < 30:
        return float("nan")
    cov = aligned.iloc[:, 0].cov(aligned.iloc[:, 1])
    var = aligned.iloc[:, 1].var()
    return float(cov / var) if var > 0 else float("nan")


def plot_equity(
    curves: dict[str, pd.Series],
    out_path: Path,
    highlight: str | None = None,
    *,
    log_scale: bool = True,
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]})

    for name, ret in curves.items():
        cum = (1 + ret).cumprod()
        lw = 1.8 if name == highlight else 0.9
        alpha = 1.0 if (highlight is None or name == highlight) else 0.45
        axes[0].plot(cum.index, cum.values, label=name, linewidth=lw, alpha=alpha)
        if name == highlight:
            dd = cum / cum.cummax() - 1
            axes[1].fill_between(dd.index, dd.values, 0, alpha=0.3)
            axes[1].plot(dd.index, dd.values, linewidth=0.8)

    axes[0].axvline(OOS, color="gray", linestyle="--", linewidth=0.8, label="OOS start")
    axes[0].set_ylabel("Growth of $1")
    title = "Correlation-regime market-neutral portfolio"
    if not log_scale:
        title += " (linear)"
    axes[0].set_title(title)
    axes[0].legend(loc="upper left", fontsize=8)
    axes[0].grid(alpha=0.3)
    if log_scale:
        axes[0].set_yscale("log")

    axes[1].set_ylabel("Drawdown")
    axes[1].set_xlabel("Date (UTC)")
    axes[1].grid(alpha=0.3)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


RECOMMENDED_KEY = "liquid_majors_always_in_max_sharpe"


def btc_buy_hold_returns(close: pd.DataFrame, btc_col: str = "BTCUSDT") -> pd.Series:
    return close[btc_col].pct_change().fillna(0.0).rename("btc_buy_hold")


def plot_vs_btc(
    portfolio_ret: pd.Series,
    btc_ret: pd.Series,
    out_path: Path,
    *,
    log_scale: bool,
) -> None:
    aligned = pd.concat({"portfolio": portfolio_ret, "btc": btc_ret}, axis=1).dropna()
    port_eq = (1 + aligned["portfolio"]).cumprod()
    btc_eq = (1 + aligned["btc"]).cumprod()

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    axes[0].plot(port_eq.index, port_eq.values, color="#27ae60", linewidth=1.8, label="Recommended (always-in)")
    axes[0].plot(btc_eq.index, btc_eq.values, color="#f7931a", linewidth=1.4, label="BTC buy & hold")
    axes[0].axvline(OOS, color="gray", linestyle="--", linewidth=0.8, label="OOS start")
    axes[0].set_ylabel("Growth of $1")
    scale = "log" if log_scale else "linear"
    axes[0].set_title(f"Recommended portfolio vs BTC buy & hold ({scale})")
    axes[0].legend(loc="upper left")
    axes[0].grid(alpha=0.3)
    if log_scale:
        axes[0].set_yscale("log")

    port_dd = port_eq / port_eq.cummax() - 1
    btc_dd = btc_eq / btc_eq.cummax() - 1
    axes[1].plot(port_dd.index, port_dd.values, color="#27ae60", linewidth=1.0, label="Portfolio DD")
    axes[1].plot(btc_dd.index, btc_dd.values, color="#f7931a", linewidth=0.9, alpha=0.8, label="BTC DD")
    axes[1].set_ylabel("Drawdown")
    axes[1].set_xlabel("Date (UTC)")
    axes[1].legend(loc="lower left", fontsize=8)
    axes[1].grid(alpha=0.3)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def export_vs_btc_csv(portfolio_ret: pd.Series, btc_ret: pd.Series, out_path: Path) -> None:
    aligned = pd.concat({"portfolio_return": portfolio_ret, "btc_return": btc_ret}, axis=1).dropna()
    port_eq = (1 + aligned["portfolio_return"]).cumprod()
    btc_eq = (1 + aligned["btc_return"]).cumprod()
    sample = pd.Series(
        ["in_sample" if t < OOS else "out_of_sample" for t in aligned.index],
        index=aligned.index,
        name="sample",
    )
    pd.DataFrame(
        {
            "portfolio_return": aligned["portfolio_return"],
            "portfolio_equity": port_eq,
            "portfolio_drawdown": port_eq / port_eq.cummax() - 1,
            "btc_return": aligned["btc_return"],
            "btc_equity": btc_eq,
            "btc_drawdown": btc_eq / btc_eq.cummax() - 1,
            "sample": sample,
        }
    ).to_csv(out_path)


def export_equity_csv(returns: pd.Series, out_path: Path) -> None:
    cum = (1 + returns).cumprod()
    dd = cum / cum.cummax() - 1
    sample = pd.Series(
        ["in_sample" if t < OOS else "out_of_sample" for t in returns.index],
        index=returns.index,
        name="sample",
    )
    pd.DataFrame(
        {
            "daily_return": returns,
            "equity": cum,
            "drawdown": dd,
            "sample": sample,
        }
    ).to_csv(out_path)


def main() -> None:
    close = load_close_panel(FUTURES_PATH)
    returns = close.pct_change()
    corr = rolling_mean_pairwise_corr(returns)
    quintile = expanding_corr_quintile(corr)
    depth = market_depth_pct(close)

    long_basket, short_basket, spread_tbl = calibrate_baskets(
        close, quintile, oos=OOS, basket_size=BASKET_SIZE
    )

    basket_sets = {
        "optimized_is": (long_basket, short_basket),
        "liquid_majors": (LIQUID_LONG_BASKET, LIQUID_SHORT_BASKET),
    }

    modes = ["regime_flip", "low_only", "low_only_depth_gate", "always_on", "always_in_max_sharpe"]
    curves: dict[str, pd.Series] = {}
    metrics_out: dict = {
        "baskets": {
            "optimized_is": {
                "long_dispersion": long_basket,
                "short_cluster": short_basket,
            },
            "liquid_majors": {
                "long_dispersion": LIQUID_LONG_BASKET,
                "short_cluster": LIQUID_SHORT_BASKET,
            },
            "calibration": "in_sample_only",
            "oos_start": str(OOS.date()),
        },
        "strategies": {},
    }

    weights_main = None
    for basket_name, (lb, sb) in basket_sets.items():
        for mode in modes:
            key = f"{basket_name}_{mode}"
            direction = regime_direction(quintile, mode, depth=depth)
            weights = build_target_weights(direction, lb, sb, close.columns)
            port_ret = backtest_weights(close, weights)
            curves[key] = port_ret
            m = compute_metrics(port_ret, weights)
            m["btc_beta"] = portfolio_btc_beta(returns, port_ret)
            metrics_out["strategies"][key] = m
            if basket_name == "liquid_majors" and mode == "always_in_max_sharpe":
                weights_main = weights

    artifacts = RUN / "artifacts"
    charts = RUN / "charts"
    artifacts.mkdir(parents=True, exist_ok=True)

    (artifacts / "metrics.json").write_text(json.dumps(metrics_out, indent=2), encoding="utf-8")
    spread_tbl.to_parquet(artifacts / "mn_basket_calibration.parquet")
    if weights_main is not None:
        weights_main.to_parquet(artifacts / "mn_weights_regime_flip.parquet")
    pd.DataFrame(curves).to_parquet(artifacts / "mn_equity_returns.parquet")

    plot_equity(curves, charts / "mn_equity_curve.png", highlight="liquid_majors_regime_flip", log_scale=True)
    plot_equity(
        {
            "liquid_majors_regime_flip": curves["liquid_majors_regime_flip"],
            "liquid_majors_low_only": curves["liquid_majors_low_only"],
            "liquid_majors_low_only_depth_gate": curves["liquid_majors_low_only_depth_gate"],
        },
        charts / "mn_equity_curve_linear.png",
        highlight="liquid_majors_low_only_depth_gate",
        log_scale=False,
    )
    export_equity_csv(
        curves["liquid_majors_low_only_depth_gate"],
        artifacts / "mn_equity_curve_linear.csv",
    )
    export_equity_csv(
        curves["liquid_majors_low_only"],
        artifacts / "mn_equity_curve_low_only.csv",
    )

    recommended = curves[RECOMMENDED_KEY]
    btc_ret = btc_buy_hold_returns(close)
    plot_vs_btc(recommended, btc_ret, charts / "recommended_vs_btc_linear.png", log_scale=False)
    plot_vs_btc(recommended, btc_ret, charts / "recommended_vs_btc_log.png", log_scale=True)
    export_vs_btc_csv(recommended, btc_ret, artifacts / "recommended_vs_btc.csv")
    export_equity_csv(recommended, artifacts / "recommended_equity.csv")

    spec = json.loads((RUN / "strategy_spec.json").read_text(encoding="utf-8"))
    spec["strategy_type"] = "market_neutral_corr_regime"
    spec["portfolio"] = {
        "primary_basket": "liquid_majors",
        "recommended_mode": "always_in_max_sharpe",
        "long_basket": LIQUID_LONG_BASKET,
        "short_basket": LIQUID_SHORT_BASKET,
        "modes": modes,
        "fee": FEE,
        "slippage": SLIPPAGE,
    }
    (RUN / "strategy_spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")

    best_m = metrics_out["strategies"]["liquid_majors_always_in_max_sharpe"]
    depth_m = metrics_out["strategies"]["liquid_majors_low_only_depth_gate"]
    report = [
        "# Market-neutral correlation-regime portfolio",
        "",
        "Dollar-neutral L/S book using correlation-regime insights. Baskets fixed from IS study; OOS is post-2025.",
        "",
        "## Recommended: always-invested max-Sharpe",
        "",
        f"- **Long (dispersion winners):** {', '.join(LIQUID_LONG_BASKET)}",
        f"- **Short (cluster beneficiaries):** {', '.join(LIQUID_SHORT_BASKET)}",
        "- **Default:** long dispersion / short cluster (100% gross exposure)",
        "- **Flip:** when correlation quintile ≥ Q3 **and** market depth below 35th percentile → reverse legs",
        "- **Always in market:** no flat periods",
        "",
        "| Segment | Sharpe | CAGR | Max DD |",
        "|---------|--------|------|--------|",
        f"| Full | {best_m['Sharpe']:.2f} | {best_m['CAGR']*100:.1f}% | {best_m['MaxDD']*100:.1f}% |",
        f"| In-sample | {best_m['in_sample']['Sharpe']:.2f} | {best_m['in_sample']['CAGR']*100:.1f}% | {best_m['in_sample']['MaxDD']*100:.1f}% |",
        f"| Out-of-sample | {best_m['out_of_sample']['Sharpe']:.2f} | {best_m['out_of_sample']['CAGR']*100:.1f}% | {best_m['out_of_sample']['MaxDD']*100:.1f}% |",
        "",
        f"BTC beta: {best_m['btc_beta']:.3f} | Avg gross exposure: {best_m['avg_gross_exposure']*100:.0f}%",
        "",
        "## Prior variant: selective depth gate (higher OOS Sharpe, often flat)",
        "",
        f"| Segment | Sharpe | Max DD |",
        f"|---------|--------|--------|",
        f"| Full | {depth_m['Sharpe']:.2f} | {depth_m['MaxDD']*100:.1f}% |",
        f"| Out-of-sample | {depth_m['out_of_sample']['Sharpe']:.2f} | {depth_m['out_of_sample']['MaxDD']*100:.1f}% |",
        "",
        "## Exports",
        "",
        "- **vs BTC linear:** `charts/recommended_vs_btc_linear.png`",
        "- **vs BTC log:** `charts/recommended_vs_btc_log.png`",
        "- **vs BTC CSV:** `artifacts/recommended_vs_btc.csv`",
        "- **Portfolio CSV:** `artifacts/recommended_equity.csv`",
        "- Always-in sweep: `artifacts/always_in_market_sweep.json`",
        "",
        "![Equity vs BTC linear](charts/recommended_vs_btc_linear.png)",
        "",
    ]
    (RUN / "report_market_neutral.md").write_text("\n".join(report), encoding="utf-8")

    run_state = json.loads((RUN / "run.json").read_text(encoding="utf-8"))
    run_state["status"] = "baseline_complete"
    run_state["strategy_type"] = "market_neutral_corr_regime"
    run_state["artifacts"] = {"metrics": "artifacts/metrics.json"}
    run_state["last_execution_at"] = pd.Timestamp.now(tz="UTC").isoformat()
    (RUN / "run.json").write_text(json.dumps(run_state, indent=2), encoding="utf-8")

    print(json.dumps(metrics_out, indent=2))


if __name__ == "__main__":
    main()
