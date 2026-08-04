"""Parameter sweep and enhancement search for beta-hedged funding harvest."""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

_CODE_DIR = Path(__file__).resolve().parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

import pandas as pd

from data_core import (
    HarvestConfig,
    OOS,
    RUN,
    align_universe,
    load_close_panel,
    load_coinglass_panel,
    load_daily_funding_payments,
    run_config,
    save_equity_chart,
    write_json,
)

# Focused grid (full factorial would be 5832+ configs)
FUND_WINDOWS = (5, 7, 14)
BETA_WINDOWS = (60, 90)
TOP_PCTS = (0.05, 0.10)
MIN_FUNDING = (0.0, 0.00003, 0.0001)
REBALANCE_DAYS = (3, 5, 7)
LIQUIDITY = (50, 100)
LONG_SHORT = (True, False)
VOL_ADJ = (False,)
PORTFOLIO_HEDGE = (False, True)


def build_grid() -> list[HarvestConfig]:
    configs: list[HarvestConfig] = []
    for fw, bw, tp, mf, rb, liq, ls, va, ph in itertools.product(
        FUND_WINDOWS,
        BETA_WINDOWS,
        TOP_PCTS,
        MIN_FUNDING,
        REBALANCE_DAYS,
        LIQUIDITY,
        LONG_SHORT,
        VOL_ADJ,
        PORTFOLIO_HEDGE,
    ):
        configs.append(
            HarvestConfig(
                fund_window=fw,
                beta_window=bw,
                top_pct=tp,
                min_abs_funding=mf,
                rebalance_days=rb,
                liquidity_top_n=liq,
                long_short=ls,
                vol_adjust=va,
                portfolio_hedge=ph,
            )
        )
    return configs


def stability_score(row: dict) -> float:
    """Rank by OOS Sharpe with penalty for IS/OOS gap."""
    is_s = row["is_sharpe"]
    oos_s = row["oos_sharpe"]
    gap_penalty = max(0.0, is_s - oos_s - 0.5) * 0.5
    return oos_s - gap_penalty + 0.1 * min(is_s, oos_s)


def main() -> None:
    close = load_close_panel()
    funding = load_daily_funding_payments()
    oi = load_coinglass_panel("futures_open_interest_history_ohlc_binance_1d.parquet", "close")
    close, funding, oi = align_universe(close, funding, oi)

    grid = build_grid()
    print(f"Running {len(grid)} configurations...")

    rows: list[dict] = []
    for i, cfg in enumerate(grid):
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(grid)}")
        try:
            res = run_config(close, funding, oi, cfg)
            row = {**res["params"], **res["summary"], "config": cfg.name}
            row["stability_score"] = stability_score(row)
            rows.append(row)
        except Exception as exc:
            print(f"  skip {cfg.name}: {exc}")

    df = pd.DataFrame(rows).sort_values("stability_score", ascending=False)
    artifacts = RUN / "artifacts"
    write_json(artifacts / "sweep_results.json", df.to_dict(orient="records"))

    top = df.head(20)
    top.to_csv(artifacts / "sweep_top20.csv", index=False)

    best = df.iloc[0]
    best_cfg = HarvestConfig(
        fund_window=int(best["fund_window"]),
        beta_window=int(best["beta_window"]),
        top_pct=float(best["top_pct"]),
        min_abs_funding=float(best["min_abs_funding"]),
        rebalance_days=int(best["rebalance_days"]),
        liquidity_top_n=int(best["liquidity_top_n"]) if pd.notna(best["liquidity_top_n"]) else None,
        long_short=bool(best["long_short"]),
        vol_adjust=bool(best["vol_adjust"]),
        portfolio_hedge=bool(best["portfolio_hedge"]),
    )
    best_result = run_config(close, funding, oi, best_cfg)
    save_equity_chart(
        best_result["returns"],
        RUN / "charts" / "best_sweep_equity.png",
        f"Best sweep: {best_cfg.name} (OOS Sharpe {best['oos_sharpe']:.2f})",
    )
    write_json(artifacts / "best_config.json", {
        "config": best_cfg.name,
        "params": best_result["params"],
        "summary": best_result["summary"],
        "metrics": best_result["metrics"],
    })

    # Enhancement pass: combine best structural knobs with finer funding thresholds
    base = best_cfg
    fine_grid = [
        HarvestConfig(
            fund_window=base.fund_window,
            beta_window=base.beta_window,
            top_pct=base.top_pct,
            min_abs_funding=mf,
            rebalance_days=base.rebalance_days,
            liquidity_top_n=base.liquidity_top_n,
            long_short=base.long_short,
            vol_adjust=base.vol_adjust,
            portfolio_hedge=base.portfolio_hedge,
        )
        for mf in (0.0, 0.00003, 0.0001, 0.0002, 0.0005)
    ]
    fine_rows = []
    for cfg in fine_grid:
        res = run_config(close, funding, oi, cfg)
        row = {**res["params"], **res["summary"], "config": cfg.name}
        row["stability_score"] = stability_score(row)
        fine_rows.append(row)
    fine_df = pd.DataFrame(fine_rows).sort_values("stability_score", ascending=False)
    write_json(artifacts / "fine_funding_threshold.json", fine_df.to_dict(orient="records"))

    report = [
        "# Beta-hedged funding harvest — sweep",
        "",
        f"Tested **{len(grid)}** configurations on {close.shape[1]} perps.",
        "",
        "## Top 10 by stability score (OOS Sharpe − IS/OOS gap penalty)",
        "",
        "| Rank | Config | OOS Sharpe | IS Sharpe | OOS CAGR | OOS MaxDD |",
        "|------|--------|------------|-----------|----------|-----------|",
    ]
    for i, (_, r) in enumerate(top.head(10).iterrows(), 1):
        report.append(
            f"| {i} | `{r['config'][:40]}…` | {r['oos_sharpe']:.2f} | {r['is_sharpe']:.2f} | "
            f"{r['oos_cagr']*100:.1f}% | {r['oos_maxdd']*100:.1f}% |"
        )
    report.extend([
        "",
        "## Best configuration",
        f"- **{best_cfg.name}**",
        f"- OOS Sharpe: {best['oos_sharpe']:.2f}, CAGR: {best['oos_cagr']*100:.1f}%, MaxDD: {best['oos_maxdd']*100:.1f}%",
        "",
        "## Fine funding threshold (around best)",
        "",
    ])
    for _, r in fine_df.head(5).iterrows():
        report.append(
            f"- min_funding={r['min_abs_funding']}: OOS Sharpe {r['oos_sharpe']:.2f}, "
            f"CAGR {r['oos_cagr']*100:.1f}%"
        )
    (RUN / "report_sweep.md").write_text("\n".join(report), encoding="utf-8")

    print("\n=== TOP 5 ===")
    for _, r in top.head(5).iterrows():
        print(
            f"  OOS {r['oos_sharpe']:.2f} | IS {r['is_sharpe']:.2f} | "
            f"{r['config'][:60]}"
        )
    print(f"\nBest: {best_cfg.name}")
    print(f"OOS Sharpe: {best['oos_sharpe']:.3f}")


if __name__ == "__main__":
    main()
