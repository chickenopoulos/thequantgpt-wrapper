"""Three turnover-reduction follow-ups on continuation L/S stress factor."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

_CODE_DIR = Path(__file__).resolve().parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from liquidation_stress_cs import (
    ANN,
    FEE,
    MIN_UNIVERSE,
    OOS,
    RUN,
    SLIPPAGE,
    TOP_PCT,
    align_universe,
    build_stress_signal,
    load_close_panel,
    load_coinglass_panel,
    metrics_from_returns,
)
from turnover_reduction_sweep import (
    apply_min_hold,
    evaluate_variant,
    load_liquidity_panel,
    markdown_table,
    prepare_signal,
    returns_from_weights,
    select_decile_baskets,
    turnover_stats,
    weights_from_baskets,
)

BOTTOM_PCT = TOP_PCT

# Soft-threshold L1 prox on weight deltas (per-name, portfolio scale).
LAMBDA_SWEEP = [0.002, 0.005, 0.01, 0.02, 0.05]
NO_TRADE_BAND = 0.005  # 0.5% portfolio per name


@dataclass
class FollowupConfig:
    name: str
    description: str
    rebalance_days: int = 1
    min_hold_days: int = 0
    no_trade_band: float = 0.0
    turnover_penalty_lam: float | None = None


def soft_threshold_l1(delta: pd.Series, lam: float) -> pd.Series:
    """Prox operator for lam * L1: sign(d) * max(|d| - lam, 0)."""
    if lam <= 0:
        return delta
    out = delta.copy()
    for idx in out.index:
        d = out.loc[idx]
        if abs(d) <= lam:
            out.loc[idx] = 0.0
        else:
            out.loc[idx] = np.sign(d) * (abs(d) - lam)
    return out


def apply_no_trade_band(w_target: pd.Series, w_prev: pd.Series, band: float) -> pd.Series:
    idx = w_target.index.union(w_prev.index)
    target = w_target.reindex(idx, fill_value=0.0)
    prev = w_prev.reindex(idx, fill_value=0.0)
    new = prev.copy()
    for asset in idx:
        delta = target.loc[asset] - prev.loc[asset]
        if abs(delta) >= band:
            new.loc[asset] = target.loc[asset]
    return new


def apply_turnover_penalty(
    w_target: pd.Series,
    w_prev: pd.Series,
    lam: float,
) -> pd.Series:
    idx = w_target.index.union(w_prev.index)
    target = w_target.reindex(idx, fill_value=0.0)
    prev = w_prev.reindex(idx, fill_value=0.0)
    delta = soft_threshold_l1(target - prev, lam)
    return prev + delta


def build_weight_panel_extended(signal: pd.DataFrame, cfg: FollowupConfig) -> pd.DataFrame:
    weights: dict[pd.Timestamp, pd.Series] = {}
    prev_w: pd.Series | None = None
    long_basket: set[str] = set()
    short_basket: set[str] = set()
    held_since: dict[str, pd.Timestamp] = {}
    dates = list(signal.index)

    for i, t in enumerate(dates):
        row = signal.loc[t].dropna()
        if len(row) < MIN_UNIVERSE:
            if prev_w is not None:
                weights[t] = prev_w.copy()
            continue

        is_rebalance = cfg.rebalance_days <= 1 or i % cfg.rebalance_days == 0 or prev_w is None

        if not is_rebalance and prev_w is not None:
            weights[t] = prev_w.copy()
            continue

        prop_long, prop_short = select_decile_baskets(row)

        if cfg.min_hold_days > 0:
            prop_long, prop_short = apply_min_hold(
                long_basket,
                short_basket,
                prop_long,
                prop_short,
                held_since,
                t,
                cfg.min_hold_days,
            )

        long_basket, short_basket = prop_long, prop_short
        w_target = weights_from_baskets(prop_long, prop_short, row.index)

        if prev_w is None:
            w = w_target
        elif cfg.turnover_penalty_lam is not None:
            w = apply_turnover_penalty(w_target, prev_w, cfg.turnover_penalty_lam)
        elif cfg.no_trade_band > 0:
            w = apply_no_trade_band(w_target, prev_w, cfg.no_trade_band)
        else:
            w = w_target

        weights[t] = w
        prev_w = w

    return pd.DataFrame(weights).T.sort_index()


def evaluate_followup(close: pd.DataFrame, stress: pd.DataFrame, cfg: FollowupConfig) -> dict:
    sig = prepare_signal(stress, type("V", (), {"smooth_days": 0, "top_liquidity": None})(), None)
    weights = build_weight_panel_extended(sig, cfg)
    gross = returns_from_weights(close, weights, apply_costs=False)
    net = returns_from_weights(close, weights, apply_costs=True)
    turn = turnover_stats(weights)
    return {
        "name": cfg.name,
        "description": cfg.description,
        "turnover": turn,
        "gross": metrics_from_returns(gross),
        "net": metrics_from_returns(net),
        "n_weight_days": int(len(weights)),
    }


def build_test_configs() -> list[FollowupConfig | type]:
    configs: list[FollowupConfig] = [
        FollowupConfig(
            "00_baseline_daily",
            "Daily decile L/S continuation (reference)",
        ),
        FollowupConfig(
            "01_weekly_minhold5d",
            "Weekly rebalance (5d) + 5-day minimum hold per name",
            rebalance_days=5,
            min_hold_days=5,
        ),
        FollowupConfig(
            "03_weekly_no_trade_band",
            f"Weekly rebalance + {NO_TRADE_BAND*100:.1f}% per-name no-trade band",
            rebalance_days=5,
            no_trade_band=NO_TRADE_BAND,
        ),
    ]
    for lam in LAMBDA_SWEEP:
        configs.append(
            FollowupConfig(
                f"02_lambda_{lam:.3f}".replace(".", "p"),
                f"Daily turnover-penalized optimizer (λ={lam})",
                turnover_penalty_lam=lam,
            )
        )
    return configs


def plot_followup(results: list[dict], out_path: Path) -> None:
    names = [r["name"] for r in results]
    net_sh = [r["net"]["Sharpe"] for r in results]
    gross_sh = [r["gross"]["Sharpe"] for r in results]
    turn = [r["turnover"]["annualized_gross_turnover"] for r in results]

    fig, axes = plt.subplots(1, 3, figsize=(16, max(5, len(names) * 0.35)))
    y = np.arange(len(names))

    axes[0].barh(y, net_sh, color=["#27ae60" if s > 0 else "#c0392b" for s in net_sh], alpha=0.9)
    axes[0].set_yticks(y, labels=names, fontsize=8)
    axes[0].axvline(0, color="black", linewidth=0.6)
    axes[0].set_title("Net Sharpe")
    axes[0].grid(axis="x", alpha=0.25)

    axes[1].barh(y, gross_sh, color="#8e44ad", alpha=0.85)
    axes[1].set_yticks(y, labels=names, fontsize=8)
    axes[1].set_title("Gross Sharpe")
    axes[1].grid(axis="x", alpha=0.25)

    axes[2].barh(y, turn, color="#3498db", alpha=0.85)
    axes[2].set_yticks(y, labels=names, fontsize=8)
    axes[2].set_title("Ann. gross turnover")
    axes[2].grid(axis="x", alpha=0.25)

    fig.suptitle("Turnover reduction follow-up — continuation L/S", y=1.01)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def detailed_table(results: list[dict]) -> str:
    lines = [
        "| Variant | Net Sharpe | Net CAGR | Net MaxDD | Gross Sharpe | Gross CAGR | IS Net Sharpe | OOS Net Sharpe | Ann. turnover |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        g, n, t = r["gross"], r["net"], r["turnover"]
        lines.append(
            f"| {r['name']} | {n['Sharpe']:.2f} | {n['CAGR']*100:.1f}% | {n['MaxDD']*100:.1f}% | "
            f"{g['Sharpe']:.2f} | {g['CAGR']*100:.1f}% | {n['in_sample']['Sharpe']:.2f} | "
            f"{n['out_of_sample']['Sharpe']:.2f} | {t['annualized_gross_turnover']:.0f}x |"
        )
    return "\n".join(lines)


def main() -> None:
    close = load_close_panel()
    funding = load_coinglass_panel("futures_funding_rate_binance_1d.parquet", "close")
    oi = load_coinglass_panel("futures_open_interest_history_ohlc_binance_1d.parquet", "close")
    liq_long = load_coinglass_panel("futures_liquidations_binance_1d.parquet", "long_liquidation_usd")
    liq_short = load_coinglass_panel("futures_liquidations_binance_1d.parquet", "short_liquidation_usd")
    close, funding, oi, liq_long, liq_short = align_universe(close, funding, oi, liq_long, liq_short)
    stress = build_stress_signal(funding, oi, liq_long, liq_short)

    valid_days = stress.notna().sum(axis=1)
    start = valid_days[valid_days >= MIN_UNIVERSE].index.min()
    close = close.loc[start:]
    stress = stress.loc[start:]

    configs = build_test_configs()
    results = [evaluate_followup(close, stress, cfg) for cfg in configs]

    # Sort: baseline first, then primary tests, then lambda sweep by net Sharpe
    primary = [r for r in results if r["name"] in ("00_baseline_daily", "01_weekly_minhold5d", "03_weekly_no_trade_band")]
    lambdas = sorted(
        [r for r in results if r["name"].startswith("02_lambda")],
        key=lambda r: r["net"]["Sharpe"],
        reverse=True,
    )
    results_sorted = primary + lambdas

    artifacts = RUN / "artifacts"
    charts = RUN / "charts"
    artifacts.mkdir(parents=True, exist_ok=True)
    charts.mkdir(parents=True, exist_ok=True)

    best_lambda = lambdas[0] if lambdas else None

    payload = {
        "oos_start": str(OOS.date()),
        "costs": {"fee": FEE, "slippage": SLIPPAGE},
        "no_trade_band": NO_TRADE_BAND,
        "lambda_sweep": LAMBDA_SWEEP,
        "best_lambda_variant": best_lambda,
        "primary_tests": {
            "weekly_minhold5d": next(r for r in results if r["name"] == "01_weekly_minhold5d"),
            "weekly_no_trade_band": next(r for r in results if r["name"] == "03_weekly_no_trade_band"),
        },
        "baseline": next(r for r in results if r["name"] == "00_baseline_daily"),
        "lambda_variants": lambdas,
        "all_variants": results_sorted,
    }
    (artifacts / "turnover_followup.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    plot_followup(results_sorted, charts / "turnover_followup_comparison.png")

    report_lines = [
        "# Turnover reduction follow-up — continuation L/S",
        "",
        f"OOS cut: **{OOS.date()}**. Costs: fee {FEE}, slippage {SLIPPAGE} (on actual daily turnover).",
        "",
        "## Primary tests (vs baseline)",
        "",
        detailed_table(primary),
        "",
        "## λ sweep (turnover-penalized optimizer, daily)",
        "",
        detailed_table(lambdas),
        "",
        "## Variant descriptions",
        "",
        *[f"- **{r['name']}**: {r['description']}" for r in results_sorted],
        "",
        f"Best λ variant: **{best_lambda['name']}** (net Sharpe {best_lambda['net']['Sharpe']:.2f}, "
        f"turnover {best_lambda['turnover']['annualized_gross_turnover']:.0f}x)" if best_lambda else "",
        "",
        "![Comparison](charts/turnover_followup_comparison.png)",
    ]
    (RUN / "report_turnover_followup.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    summary = {
        "baseline_net_sharpe": payload["baseline"]["net"]["Sharpe"],
        "weekly_minhold5d": {
            "net_sharpe": payload["primary_tests"]["weekly_minhold5d"]["net"]["Sharpe"],
            "gross_sharpe": payload["primary_tests"]["weekly_minhold5d"]["gross"]["Sharpe"],
            "turnover": payload["primary_tests"]["weekly_minhold5d"]["turnover"]["annualized_gross_turnover"],
        },
        "weekly_no_trade_band": {
            "net_sharpe": payload["primary_tests"]["weekly_no_trade_band"]["net"]["Sharpe"],
            "gross_sharpe": payload["primary_tests"]["weekly_no_trade_band"]["gross"]["Sharpe"],
            "turnover": payload["primary_tests"]["weekly_no_trade_band"]["turnover"]["annualized_gross_turnover"],
        },
        "best_lambda": {
            "name": best_lambda["name"],
            "net_sharpe": best_lambda["net"]["Sharpe"],
            "gross_sharpe": best_lambda["gross"]["Sharpe"],
            "turnover": best_lambda["turnover"]["annualized_gross_turnover"],
        } if best_lambda else None,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
