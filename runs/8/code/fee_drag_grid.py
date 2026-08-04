"""Grid: rebalance lag × hysteresis bands × turnover-penalized sizing.

Continuation L/S on the liquidation-stress factor. Signal unchanged;
only portfolio construction / rebalance policy varies.
"""

from __future__ import annotations

import itertools
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
    select_decile_baskets,
    turnover_stats,
    update_hysteresis,
    weights_from_baskets,
)

BOTTOM_PCT = TOP_PCT

# Grid axes (edge-preserving construction knobs only)
REBALANCE_DAYS = (1, 3, 5)
HYSTERESIS_BANDS: tuple[tuple[str, float | None, float | None], ...] = (
    ("none", None, None),
    ("e08_x15", 0.08, 0.15),
    ("e10_x20", 0.10, 0.20),
)
# Fraction of gap closed toward target each rebalance day (1=full, lower=less churn)
TURNOVER_BLEND = (1.0, 0.5, 0.25)


@dataclass(frozen=True)
class GridConfig:
    rebalance_days: int
    hyst_name: str
    entry_pct: float | None
    exit_pct: float | None
    blend: float

    @property
    def name(self) -> str:
        return f"rb{self.rebalance_days}_{self.hyst_name}_b{self.blend:g}"

    @property
    def description(self) -> str:
        hyst = (
            "no hysteresis"
            if self.entry_pct is None
            else f"hysteresis enter {self.entry_pct:.0%}/exit {self.exit_pct:.0%}"
        )
        return (
            f"rebalance every {self.rebalance_days}d, {hyst}, "
            f"blend={self.blend:g} toward target"
        )


def build_grid() -> list[GridConfig]:
    configs: list[GridConfig] = []
    for rb, (hname, entry, exit_), blend in itertools.product(
        REBALANCE_DAYS, HYSTERESIS_BANDS, TURNOVER_BLEND
    ):
        configs.append(
            GridConfig(
                rebalance_days=rb,
                hyst_name=hname,
                entry_pct=entry,
                exit_pct=exit_,
                blend=blend,
            )
        )
    return configs


def build_weight_panel(signal: pd.DataFrame, cfg: GridConfig) -> pd.DataFrame:
    """Continuation L/S weights with optional hysteresis + partial rebalance."""
    weights: dict[pd.Timestamp, pd.Series] = {}
    prev_w: pd.Series | None = None
    long_basket: set[str] = set()
    short_basket: set[str] = set()
    dates = list(signal.index)

    for i, t in enumerate(dates):
        row = signal.loc[t].dropna()
        if len(row) < MIN_UNIVERSE:
            if prev_w is not None:
                weights[t] = prev_w.reindex(row.index, fill_value=0.0) if len(row) else prev_w.copy()
            continue

        hold = cfg.rebalance_days > 1 and i % cfg.rebalance_days != 0 and prev_w is not None
        if hold:
            # Carry prior dollar weights onto today's tradable universe
            w = prev_w.reindex(row.index, fill_value=0.0)
            # Renormalize gross exposure so dead names don't silently shrink book
            gross = float(w.abs().sum())
            if gross > 1e-12:
                w = w * (1.0 / gross)
            weights[t] = w
            prev_w = w
            continue

        if cfg.entry_pct is not None and cfg.exit_pct is not None:
            long_basket, short_basket = update_hysteresis(
                row,
                long_basket,
                short_basket,
                entry_pct=cfg.entry_pct,
                exit_pct=cfg.exit_pct,
            )
            prop_long, prop_short = long_basket, short_basket
        else:
            prop_long, prop_short = select_decile_baskets(row)
            long_basket, short_basket = prop_long, prop_short

        target = weights_from_baskets(prop_long, prop_short, row.index)
        if prev_w is None or cfg.blend >= 1.0 - 1e-12:
            w = target
        else:
            prev_aligned = prev_w.reindex(row.index, fill_value=0.0)
            w = prev_aligned + cfg.blend * (target - prev_aligned)
            # Keep dollar-neutral L/S gross ≈ 1
            gross = float(w.abs().sum())
            if gross > 1e-12:
                w = w * (1.0 / gross)

        weights[t] = w
        prev_w = w

    if not weights:
        return pd.DataFrame()
    return pd.DataFrame(weights).T.sort_index()


def returns_from_weights(close: pd.DataFrame, weights: pd.DataFrame, *, apply_costs: bool) -> pd.Series:
    fwd = close.pct_change().shift(-1)
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
            traded = float(
                (w.reindex(idx, fill_value=0) - prev.reindex(idx, fill_value=0)).abs().sum()
            )
            cost = traded * (FEE + SLIPPAGE)
        net_vals[t] = float(gross.loc[t] - cost)
        prev = w
    return pd.Series(net_vals).sort_index()


def evaluate(close: pd.DataFrame, stress: pd.DataFrame, cfg: GridConfig) -> dict:
    weights = build_weight_panel(stress, cfg)
    if weights.empty:
        empty = metrics_from_returns(pd.Series(dtype=float))
        return {
            "name": cfg.name,
            "description": cfg.description,
            "params": {
                "rebalance_days": cfg.rebalance_days,
                "hysteresis": cfg.hyst_name,
                "entry_pct": cfg.entry_pct,
                "exit_pct": cfg.exit_pct,
                "blend": cfg.blend,
            },
            "turnover": {
                "daily_gross_turnover": 0.0,
                "annualized_gross_turnover": 0.0,
                "daily_one_way_turnover": 0.0,
            },
            "gross": empty,
            "net": empty,
        }

    gross = returns_from_weights(close, weights, apply_costs=False)
    net = returns_from_weights(close, weights, apply_costs=True)
    turn = turnover_stats(weights)
    return {
        "name": cfg.name,
        "description": cfg.description,
        "params": {
            "rebalance_days": cfg.rebalance_days,
            "hysteresis": cfg.hyst_name,
            "entry_pct": cfg.entry_pct,
            "exit_pct": cfg.exit_pct,
            "blend": cfg.blend,
        },
        "turnover": turn,
        "gross": metrics_from_returns(gross),
        "net": metrics_from_returns(net),
        "n_weight_days": int(len(weights)),
        "returns_net": net,
    }


def plot_grid_heatmaps(results: list[dict], out_path: Path) -> None:
    """Net Sharpe heatmaps: blend × rebalance, one panel per hysteresis setting."""
    hyst_names = [h[0] for h in HYSTERESIS_BANDS]
    fig, axes = plt.subplots(1, len(hyst_names), figsize=(14, 4.5), sharey=True)
    if len(hyst_names) == 1:
        axes = [axes]

    for ax, hname in zip(axes, hyst_names, strict=True):
        mat = np.full((len(TURNOVER_BLEND), len(REBALANCE_DAYS)), np.nan)
        for r in results:
            p = r["params"]
            if p["hysteresis"] != hname:
                continue
            bi = TURNOVER_BLEND.index(p["blend"])
            ri = REBALANCE_DAYS.index(p["rebalance_days"])
            mat[bi, ri] = r["net"]["Sharpe"]
        im = ax.imshow(mat, aspect="auto", cmap="RdYlGn", vmin=-1.5, vmax=1.5)
        ax.set_xticks(range(len(REBALANCE_DAYS)), [str(d) for d in REBALANCE_DAYS])
        ax.set_yticks(range(len(TURNOVER_BLEND)), [f"{b:g}" for b in TURNOVER_BLEND])
        ax.set_xlabel("rebalance_days")
        ax.set_title(f"hysteresis={hname}")
        for i in range(mat.shape[0]):
            for j in range(mat.shape[1]):
                if np.isfinite(mat[i, j]):
                    ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center", fontsize=8)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    axes[0].set_ylabel("blend (gap closed)")
    fig.suptitle("Fee-drag grid — net Sharpe (continuation L/S)", y=1.02)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def plot_top_equity(results: list[dict], out_path: Path, n: int = 5) -> None:
    fig, ax = plt.subplots(figsize=(11, 5))
    for r in results[:n]:
        rets = r.get("returns_net")
        if rets is None or rets.empty:
            continue
        eq = (1 + rets.fillna(0)).cumprod()
        ax.plot(eq.index, eq.values, label=f"{r['name']} ({r['net']['Sharpe']:.2f})", linewidth=1.2)
    ax.axvline(OOS, color="gray", linestyle="--", linewidth=0.9, label="OOS start")
    ax.set_title(f"Top {n} fee-drag grid variants (net equity)")
    ax.set_ylabel("Growth of $1")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def markdown_table(results: list[dict], limit: int | None = None) -> str:
    rows = results if limit is None else results[:limit]
    lines = [
        "| Rank | Variant | Net Sharpe | IS Net | OOS Net | Gross Sharpe | Net CAGR | MaxDD | Ann. TO |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for i, r in enumerate(rows, 1):
        g, n, t = r["gross"], r["net"], r["turnover"]
        lines.append(
            f"| {i} | `{r['name']}` | {n['Sharpe']:.2f} | {n['in_sample']['Sharpe']:.2f} | "
            f"{n['out_of_sample']['Sharpe']:.2f} | {g['Sharpe']:.2f} | {n['CAGR']*100:.1f}% | "
            f"{n['MaxDD']*100:.1f}% | {t['annualized_gross_turnover']:.0f}x |"
        )
    return "\n".join(lines)


def strip_returns(results: list[dict]) -> list[dict]:
    """Drop Series before JSON serialize."""
    out = []
    for r in results:
        d = {k: v for k, v in r.items() if k != "returns_net"}
        out.append(d)
    return out


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

    configs = build_grid()
    results = [evaluate(close, stress, cfg) for cfg in configs]
    results.sort(key=lambda r: r["net"]["Sharpe"], reverse=True)

    baseline = next(r for r in results if r["name"] == "rb1_none_b1")
    best = results[0]

    artifacts = RUN / "artifacts"
    charts = RUN / "charts"
    artifacts.mkdir(parents=True, exist_ok=True)
    charts.mkdir(parents=True, exist_ok=True)

    payload = {
        "oos_start": str(OOS.date()),
        "costs": {"fee": FEE, "slippage": SLIPPAGE},
        "grid": {
            "rebalance_days": list(REBALANCE_DAYS),
            "hysteresis_bands": [
                {"name": n, "entry_pct": e, "exit_pct": x} for n, e, x in HYSTERESIS_BANDS
            ],
            "turnover_blend": list(TURNOVER_BLEND),
            "n_configs": len(configs),
        },
        "baseline": strip_returns([baseline])[0],
        "best": strip_returns([best])[0],
        "variants": strip_returns(results),
    }
    (artifacts / "fee_drag_grid.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    plot_grid_heatmaps(results, charts / "fee_drag_grid_heatmap.png")
    plot_top_equity(results, charts / "fee_drag_grid_top_equity.png")

    # Gross preservation check: how much gross Sharpe vs baseline
    base_gross = baseline["gross"]["Sharpe"]
    report = "\n".join(
        [
            "# Fee-drag grid — continuation L/S",
            "",
            "Construction-only grid (signal unchanged): **rebalance lag × hysteresis bands × "
            "turnover-penalized sizing (blend toward target)**.",
            "",
            f"OOS cut: **{OOS.date()}**. Costs: fee {FEE}, slippage {SLIPPAGE} on actual turnover.",
            f"Grid size: **{len(configs)}** configs.",
            "",
            "## Headline",
            "",
            f"- Baseline `{baseline['name']}`: net Sharpe **{baseline['net']['Sharpe']:.2f}**, "
            f"gross **{base_gross:.2f}**, ann. turnover **{baseline['turnover']['annualized_gross_turnover']:.0f}x**",
            f"- Best `{best['name']}`: net Sharpe **{best['net']['Sharpe']:.2f}**, "
            f"gross **{best['gross']['Sharpe']:.2f}**, "
            f"IS/OOS net **{best['net']['in_sample']['Sharpe']:.2f} / {best['net']['out_of_sample']['Sharpe']:.2f}**, "
            f"ann. turnover **{best['turnover']['annualized_gross_turnover']:.0f}x**",
            f"- Gross Sharpe retained vs baseline: "
            f"**{best['gross']['Sharpe'] / base_gross * 100:.0f}%**"
            if abs(base_gross) > 1e-9
            else "- Gross Sharpe retained vs baseline: n/a",
            "",
            "## Top 10 by net Sharpe",
            "",
            markdown_table(results, limit=10),
            "",
            "## Full ranking",
            "",
            markdown_table(results),
            "",
            "## Charts",
            "",
            "![Heatmap](charts/fee_drag_grid_heatmap.png)",
            "",
            "![Top equity](charts/fee_drag_grid_top_equity.png)",
        ]
    )
    (RUN / "report_fee_drag_grid.md").write_text(report + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "n_configs": len(configs),
                "baseline_net_sharpe": baseline["net"]["Sharpe"],
                "best": {
                    "name": best["name"],
                    "net_sharpe": best["net"]["Sharpe"],
                    "gross_sharpe": best["gross"]["Sharpe"],
                    "oos_net_sharpe": best["net"]["out_of_sample"]["Sharpe"],
                    "ann_turnover": best["turnover"]["annualized_gross_turnover"],
                },
                "top_5": [
                    {
                        "name": r["name"],
                        "net": r["net"]["Sharpe"],
                        "gross": r["gross"]["Sharpe"],
                        "oos": r["net"]["out_of_sample"]["Sharpe"],
                        "to": r["turnover"]["annualized_gross_turnover"],
                    }
                    for r in results[:5]
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
