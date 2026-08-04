"""Targeted sweep for short-only beta-hedged funding harvest."""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

_CODE_DIR = Path(__file__).resolve().parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

import pandas as pd

from data_core import (
    HarvestConfig,
    RUN,
    align_universe,
    load_close_panel,
    load_coinglass_panel,
    load_daily_funding_payments,
    run_config,
    save_equity_chart,
    write_json,
)

FUND_WINDOWS = (7, 14)
BETA_WINDOWS = (90, 120)
TOP_PCTS = (0.10, 0.15)
MIN_FUNDING = (0.00003, 0.0001)
REBALANCE_DAYS = (5, 7)
LIQUIDITY = (50, 75)


def stability_score(row: dict) -> float:
    is_s, oos_s = row["is_sharpe"], row["oos_sharpe"]
    gap = max(0.0, is_s - oos_s - 0.75)
    # reward consistent positive years via min(IS,OOS)
    return oos_s - 0.6 * gap + 0.15 * min(is_s, oos_s)


def main() -> None:
    close = load_close_panel()
    funding = load_daily_funding_payments()
    oi = load_coinglass_panel("futures_open_interest_history_ohlc_binance_1d.parquet", "close")
    close, funding, oi = align_universe(close, funding, oi)

    rows = []
    grid = list(
        itertools.product(FUND_WINDOWS, BETA_WINDOWS, TOP_PCTS, MIN_FUNDING, REBALANCE_DAYS, LIQUIDITY)
    )
    print(f"Short-only sweep: {len(grid)} configs")

    for i, (fw, bw, tp, mf, rb, liq) in enumerate(grid):
        cfg = HarvestConfig(
            fund_window=fw,
            beta_window=bw,
            top_pct=tp,
            min_abs_funding=mf,
            rebalance_days=rb,
            liquidity_top_n=liq,
            long_short=False,
            vol_adjust=False,
            portfolio_hedge=False,
        )
        res = run_config(close, funding, oi, cfg)
        row = {**res["params"], **res["summary"], "config": cfg.name}
        row["stability_score"] = stability_score(row)
        rows.append(row)
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(grid)}")

    df = pd.DataFrame(rows).sort_values("stability_score", ascending=False)
    write_json(RUN / "artifacts" / "short_only_sweep.json", df.to_dict(orient="records"))
    df.head(25).to_csv(RUN / "artifacts" / "short_only_sweep_top25.csv", index=False)

    best = df.iloc[0]
    best_cfg = HarvestConfig(
        fund_window=int(best["fund_window"]),
        beta_window=int(best["beta_window"]),
        top_pct=float(best["top_pct"]),
        min_abs_funding=float(best["min_abs_funding"]),
        rebalance_days=int(best["rebalance_days"]),
        liquidity_top_n=int(best["liquidity_top_n"]),
        long_short=False,
    )
    best_res = run_config(close, funding, oi, best_cfg)
    save_equity_chart(
        best_res["returns"],
        RUN / "charts" / "best_short_only_equity.png",
        f"Best short-only (OOS Sharpe {best['oos_sharpe']:.2f})",
    )
    write_json(RUN / "artifacts" / "best_short_only.json", {
        "config": best_cfg.name,
        "params": best_res["params"],
        "summary": best_res["summary"],
        "metrics": best_res["metrics"],
    })

    print("\nTop 5:")
    for _, r in df.head(5).iterrows():
        print(
            f"  score={r['stability_score']:.2f} OOS={r['oos_sharpe']:.2f} IS={r['is_sharpe']:.2f} "
            f"fw={int(r['fund_window'])} tp={r['top_pct']} mf={r['min_abs_funding']} rb={int(r['rebalance_days'])}"
        )
    print(f"\nBest: {best_cfg.name}")


if __name__ == "__main__":
    main()
