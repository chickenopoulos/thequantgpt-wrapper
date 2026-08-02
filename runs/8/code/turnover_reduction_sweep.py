"""Compare turnover-reduction variants for continuation L/S stress factor."""

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

REPO = Path(__file__).resolve().parents[3]

BOTTOM_PCT = TOP_PCT
ENTRY_PCT = 0.08
EXIT_PCT = 0.15
DISPERSION_MIN_PERIODS = 120
TOP_LIQ_N = 50


@dataclass
class VariantConfig:
    name: str
    description: str
    smooth_days: int = 0
    rebalance_days: int = 1
    hysteresis: bool = False
    min_hold_days: int = 0
    dispersion_gate: bool = False
    top_liquidity: int | None = None


VARIANTS: list[VariantConfig] = [
    VariantConfig("01_baseline_daily", "Daily decile L/S continuation"),
    VariantConfig("02_smooth_3d", "3-day rolling mean on stress", smooth_days=3),
    VariantConfig("03_smooth_5d", "5-day rolling mean on stress", smooth_days=5),
    VariantConfig("04_weekly_5d", "Rebalance every 5 trading days", rebalance_days=5),
    VariantConfig("05_hysteresis", "Enter top/bottom 8%, exit outside 15%", hysteresis=True),
    VariantConfig("06_min_hold_3d", "Minimum 3-day hold per name", min_hold_days=3),
    VariantConfig("07_min_hold_5d", "Minimum 5-day hold per name", min_hold_days=5),
    VariantConfig("08_dispersion_gate", "Trade only when xs stress std > expanding median", dispersion_gate=True),
    VariantConfig("09_top50_liquidity", "Universe restricted to top-50 20d quote volume", top_liquidity=TOP_LIQ_N),
    VariantConfig(
        "10_hysteresis_dispersion",
        "Hysteresis + dispersion gate",
        hysteresis=True,
        dispersion_gate=True,
    ),
    VariantConfig(
        "11_smooth3d_weekly",
        "3-day smooth + weekly rebalance",
        smooth_days=3,
        rebalance_days=5,
    ),
    VariantConfig(
        "12_top50_hysteresis",
        "Top-50 liquidity + hysteresis",
        top_liquidity=TOP_LIQ_N,
        hysteresis=True,
    ),
    VariantConfig(
        "13_top50_hysteresis_dispersion",
        "Top-50 + hysteresis + dispersion gate",
        top_liquidity=TOP_LIQ_N,
        hysteresis=True,
        dispersion_gate=True,
    ),
    VariantConfig(
        "14_hysteresis_minhold3d",
        "Hysteresis + 3-day minimum hold",
        hysteresis=True,
        min_hold_days=3,
    ),
    VariantConfig(
        "15_all_moderate",
        "Top-50 + smooth3d + hysteresis + dispersion (no weekly)",
        smooth_days=3,
        top_liquidity=TOP_LIQ_N,
        hysteresis=True,
        dispersion_gate=True,
    ),
]


def load_liquidity_panel(assets: pd.Index, index: pd.DatetimeIndex) -> pd.DataFrame:
    path = REPO / "data" / "binance" / "binance_futures_ohlcv_1d.parquet"
    df = pd.read_parquet(path, columns=["time", "asset", "quote_asset_volume"])
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df[df["asset"].isin(assets)]
    liq = (
        df.pivot_table(index="time", columns="asset", values="quote_asset_volume", aggfunc="last")
        .sort_index()
        .reindex(index)
        .reindex(columns=assets)
        .astype(float)
    )
    return liq.rolling(20, min_periods=10).mean()


def prepare_signal(stress: pd.DataFrame, cfg: VariantConfig, liq: pd.DataFrame | None) -> pd.DataFrame:
    sig = stress.copy()
    if cfg.smooth_days > 1:
        sig = sig.T.rolling(cfg.smooth_days, min_periods=1).mean().T
    if cfg.top_liquidity and liq is not None:
        masked = sig.copy()
        for t in sig.index:
            row = liq.loc[t].dropna() if t in liq.index else pd.Series(dtype=float)
            if len(row) < cfg.top_liquidity:
                continue
            keep = set(row.nlargest(cfg.top_liquidity).index)
            drop = [c for c in masked.columns if c not in keep]
            masked.loc[t, drop] = np.nan
        sig = masked
    return sig


def dispersion_gate_series(signal: pd.DataFrame) -> pd.Series:
    xs_std = signal.std(axis=1)
    thr = xs_std.expanding(min_periods=DISPERSION_MIN_PERIODS).median()
    return (xs_std >= thr).fillna(False)


def select_decile_baskets(row: pd.Series) -> tuple[set[str], set[str]]:
    n_top = max(1, int(len(row) * TOP_PCT))
    n_bot = max(1, int(len(row) * BOTTOM_PCT))
    long_basket = set(row.nsmallest(n_bot).index)
    short_basket = set(row.nlargest(n_top).index)
    return long_basket, short_basket


def update_hysteresis(
    row: pd.Series,
    long_basket: set[str],
    short_basket: set[str],
    *,
    entry_pct: float = ENTRY_PCT,
    exit_pct: float = EXIT_PCT,
) -> tuple[set[str], set[str]]:
    ranks = row.rank(pct=True, method="average")
    for asset, r in ranks.items():
        if r <= entry_pct:
            long_basket.add(asset)
        if r >= 1.0 - entry_pct:
            short_basket.add(asset)
    long_basket = {a for a in long_basket if a in ranks.index and ranks[a] <= exit_pct}
    short_basket = {a for a in short_basket if a in ranks.index and ranks[a] >= 1.0 - exit_pct}
    return long_basket, short_basket


def apply_min_hold(
    prev_long: set[str],
    prev_short: set[str],
    proposed_long: set[str],
    proposed_short: set[str],
    held_since: dict[str, pd.Timestamp],
    t: pd.Timestamp,
    min_hold_days: int,
) -> tuple[set[str], set[str]]:
    final_long = set(proposed_long)
    final_short = set(proposed_short)
    for asset in prev_long:
        if asset not in proposed_long and asset in held_since:
            if (t - held_since[asset]).days < min_hold_days:
                final_long.add(asset)
    for asset in prev_short:
        if asset not in proposed_short and asset in held_since:
            if (t - held_since[asset]).days < min_hold_days:
                final_short.add(asset)
    for asset in final_long | final_short:
        held_since.setdefault(asset, t)
    for asset in list(held_since):
        if asset not in final_long and asset not in final_short:
            del held_since[asset]
    return final_long, final_short


def weights_from_baskets(long_basket: set[str], short_basket: set[str], universe: pd.Index) -> pd.Series:
    w = pd.Series(0.0, index=universe)
    if long_basket:
        w.loc[list(long_basket)] = 0.5 / len(long_basket)
    if short_basket:
        w.loc[list(short_basket)] = -0.5 / len(short_basket)
    return w


def build_weight_panel(signal: pd.DataFrame, cfg: VariantConfig) -> pd.DataFrame:
    gate = dispersion_gate_series(signal) if cfg.dispersion_gate else None
    weights: dict[pd.Timestamp, pd.Series] = {}
    prev_w: pd.Series | None = None
    long_basket: set[str] = set()
    short_basket: set[str] = set()
    held_since: dict[str, pd.Timestamp] = {}
    dates = list(signal.index)

    for i, t in enumerate(dates):
        row = signal.loc[t].dropna()
        min_names = min(MIN_UNIVERSE, cfg.top_liquidity or MIN_UNIVERSE)
        if len(row) < min_names:
            if prev_w is not None:
                weights[t] = prev_w.copy()
            continue

        trade_today = True
        if gate is not None and not bool(gate.loc[t]):
            trade_today = False
        if cfg.rebalance_days > 1 and i % cfg.rebalance_days != 0 and prev_w is not None:
            trade_today = False

        if not trade_today and prev_w is not None:
            weights[t] = prev_w.copy()
            continue

        if cfg.hysteresis:
            long_basket, short_basket = update_hysteresis(row, long_basket, short_basket)
            prop_long, prop_short = long_basket, short_basket
        else:
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

        w = weights_from_baskets(prop_long, prop_short, row.index)
        weights[t] = w
        prev_w = w

    return pd.DataFrame(weights).T.sort_index()


def turnover_stats(weights: pd.DataFrame) -> dict[str, float]:
    prev: pd.Series | None = None
    gross_turns: list[float] = []
    for t in weights.index:
        w = weights.loc[t].fillna(0.0)
        if prev is not None:
            idx = w.index.union(prev.index)
            gross_turns.append(float((w.reindex(idx, fill_value=0) - prev.reindex(idx, fill_value=0)).abs().sum()))
        prev = w
    s = pd.Series(gross_turns)
    if s.empty:
        return {
            "daily_gross_turnover": 0.0,
            "annualized_gross_turnover": 0.0,
            "daily_one_way_turnover": 0.0,
        }
    return {
        "daily_gross_turnover": float(s.mean()),
        "annualized_gross_turnover": float(s.mean() * ANN),
        "daily_one_way_turnover": float(s.mean() / 2.0),
    }


def returns_from_weights(close: pd.DataFrame, weights: pd.DataFrame, *, apply_costs: bool) -> pd.Series:
    fwd = close.pct_change().shift(-1)
    turn = turnover_stats(weights)
    gross = pd.Series(index=weights.index, dtype=float)
    for t in weights.index:
        if t not in fwd.index:
            continue
        w = weights.loc[t].fillna(0.0)
        r = fwd.loc[t].reindex(w.index).fillna(0.0)
        gross.loc[t] = float((w * r).sum())
    gross = gross.dropna()
    if not apply_costs:
        return gross

    prev: pd.Series | None = None
    net_vals: dict[pd.Timestamp, float] = {}
    for t in gross.index:
        w = weights.loc[t].fillna(0.0)
        cost = 0.0
        if prev is not None:
            idx = w.index.union(prev.index)
            cost = float((w.reindex(idx, fill_value=0) - prev.reindex(idx, fill_value=0)).abs().sum()) * (FEE + SLIPPAGE)
        net_vals[t] = float(gross.loc[t] - cost)
        prev = w
    return pd.Series(net_vals).sort_index()


def evaluate_variant(
    close: pd.DataFrame,
    stress: pd.DataFrame,
    liq: pd.DataFrame,
    cfg: VariantConfig,
) -> dict:
    sig = prepare_signal(stress, cfg, liq)
    weights = build_weight_panel(sig, cfg)
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


def plot_comparison(results: list[dict], out_path: Path) -> None:
    names = [r["name"] for r in results]
    net_sharpe = [r["net"]["Sharpe"] for r in results]
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    y = np.arange(len(names))
    axes[0].barh(y, net_sharpe, color=["#27ae60" if s > 0 else "#c0392b" for s in net_sharpe])
    axes[0].set_yticks(y, labels=names, fontsize=8)
    axes[0].axvline(0, color="black", linewidth=0.6)
    axes[0].set_title("Net Sharpe by variant")
    axes[0].grid(axis="x", alpha=0.25)

    turn = [r["turnover"]["annualized_gross_turnover"] for r in results]
    axes[1].barh(y, turn, color="#3498db", alpha=0.85)
    axes[1].set_yticks(y, labels=names, fontsize=8)
    axes[1].set_title("Annualized gross turnover")
    axes[1].grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def markdown_table(results: list[dict]) -> str:
    lines = [
        "| Variant | Net Sharpe | Net CAGR | Net MaxDD | Gross Sharpe | OOS Net Sharpe | Ann. turnover |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        g, n, t = r["gross"], r["net"], r["turnover"]
        lines.append(
            f"| {r['name']} | {n['Sharpe']:.2f} | {n['CAGR']*100:.1f}% | {n['MaxDD']*100:.1f}% | "
            f"{g['Sharpe']:.2f} | {n['out_of_sample']['Sharpe']:.2f} | {t['annualized_gross_turnover']:.0f}x |"
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
    liq_panel = load_liquidity_panel(close.columns, close.index)

    results = [evaluate_variant(close, stress, liq_panel, cfg) for cfg in VARIANTS]
    results.sort(key=lambda r: r["net"]["Sharpe"], reverse=True)

    artifacts = RUN / "artifacts"
    charts = RUN / "charts"
    artifacts.mkdir(parents=True, exist_ok=True)
    charts.mkdir(parents=True, exist_ok=True)

    payload = {
        "oos_start": str(OOS.date()),
        "costs": {"fee": FEE, "slippage": SLIPPAGE},
        "variants": results,
    }
    (artifacts / "turnover_reduction_sweep.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    plot_comparison(results, charts / "turnover_reduction_comparison.png")

    report = "\n".join(
        [
            "# Turnover reduction sweep — continuation L/S",
            "",
            f"OOS cut: **{OOS.date()}**. Costs: fee {FEE}, slippage {SLIPPAGE} (applied on actual daily turnover).",
            "",
            markdown_table(results),
            "",
            "## Variant descriptions",
            "",
            *[f"- **{r['name']}**: {r['description']}" for r in sorted(results, key=lambda x: x["name"])],
            "",
            "![Comparison](charts/turnover_reduction_comparison.png)",
        ]
    )
    (RUN / "report_turnover_sweep.md").write_text(report + "\n", encoding="utf-8")
    print(json.dumps({"top_3_net_sharpe": results[:3], "baseline": next(r for r in results if r["name"] == "01_baseline_daily")}, indent=2))


if __name__ == "__main__":
    main()
