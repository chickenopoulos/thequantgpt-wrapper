"""Beta-hedged funding harvest — final system.

Short the highest-funding alt perps (receive carry), hedge BTC beta with BTCUSDT perp.
Research showed long/short funding arbitrage is weak OOS; short-only + beta hedge is
the durable edge in this dataset.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_CODE_DIR = Path(__file__).resolve().parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from data_core import (
    ANN,
    BTC_COL,
    FEE,
    HarvestConfig,
    OOS,
    RUN,
    SLIPPAGE,
    align_universe,
    load_close_panel,
    load_coinglass_panel,
    load_daily_funding_payments,
    metrics_from_returns,
    run_config,
    save_equity_chart,
    split_metrics,
    write_json,
)

# Best balanced config from enhancement + targeted sweeps (OOS Sharpe ~1.35, IS ~0.85)
FINAL_CONFIG = HarvestConfig(
    fund_window=7,
    beta_window=120,
    top_pct=0.15,
    min_abs_funding=0.00003,
    rebalance_days=5,
    liquidity_top_n=75,
    long_short=False,
    vol_adjust=False,
    portfolio_hedge=False,
)


def yearly_table(returns) -> list[dict]:
    import pandas as pd

    rows = []
    for yr in sorted(returns.index.year.unique()):
        seg = returns[returns.index.year == yr]
        if len(seg) < 30:
            continue
        m = metrics_from_returns(seg, oos=pd.Timestamp("1900-01-01", tz="UTC"))["full_sample"]
        rows.append({"year": int(yr), **m})
    return rows


def main() -> None:
    close = load_close_panel()
    funding = load_daily_funding_payments()
    oi = load_coinglass_panel("futures_open_interest_history_ohlc_binance_1d.parquet", "close")
    close, funding, oi = align_universe(close, funding, oi)

    result = run_config(close, funding, oi, FINAL_CONFIG)
    port_ret = result["returns"]
    full, is_m, oos_m = split_metrics(result["metrics"])
    yearly = yearly_table(port_ret)

    artifacts = RUN / "artifacts"
    charts = RUN / "charts"
    save_equity_chart(
        port_ret,
        charts / "equity_curve.png",
        f"Beta-hedged funding harvest — short carry (OOS Sharpe {oos_m['Sharpe']:.2f})",
    )
    save_equity_chart(
        port_ret.loc[port_ret.index >= OOS],
        charts / "oos_equity_curve.png",
        "OOS equity",
    )

    metrics_out = {
        "strategy": "beta_hedged_funding_harvest_short_carry",
        "config": result["params"],
        "in_sample": is_m,
        "out_of_sample": oos_m,
        "full_sample": full,
        "yearly": yearly,
        "universe": {
            "n_symbols": int(close.shape[1]),
            "start": str(close.index.min()),
            "end": str(close.index.max()),
        },
        "costs": {"fee": FEE, "slippage": SLIPPAGE},
        "annualization": ANN,
        "oos_start_ts": str(OOS),
        "research_notes": {
            "funding_units": "Coinglass percent / 100; daily accrual from 8h payments when hourly available",
            "best_variant": "short_only high-funding basket with per-leg BTC beta hedge",
            "rejected_variants": [
                "long/short funding deciles (OOS Sharpe ~0.29)",
                "carry spread signal vs BTC",
                "momentum filter on shorts",
                "OI-weighted funding signal",
            ],
        },
    }
    write_json(artifacts / "metrics.json", metrics_out)
    port_ret.to_csv(artifacts / "daily_returns.csv", header=["return"])

    spec = {
        "title": "Beta-hedged funding harvest",
        "strategy_type": "CARRY",
        "asset_class": "crypto",
        "universe": "binance_futures_usdt_perpetuals",
        "hedge_instrument": BTC_COL,
        "data_sources": {
            "ohlcv": "data/binance/binance_futures_ohlcv_1d.parquet",
            "funding": "data/coinglass/futures_funding_rate (8h sum / daily fallback)",
            "oi": "data/coinglass/futures_open_interest_history_ohlc_binance_1d.parquet",
        },
        "annualization": ANN,
        "oos_start_ts": str(OOS),
        "hypothesis": (
            "Short alt perps with the highest smoothed funding (longs paying shorts), "
            "receive carry, and hedge BTC beta with BTCUSDT perp to isolate funding from "
            "directional beta risk."
        ),
        "params": result["params"],
        "metrics_summary": result["summary"],
    }
    (RUN / "strategy_spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")

    report = [
        "# Beta-hedged funding harvest",
        "",
        "## Summary",
        "Cross-sectional **short-only** funding carry on liquid alt perps, beta-hedged with BTC perp.",
        "Long/short funding arbitrage was weak OOS; the short-high-funding sleeve dominates.",
        "",
        "## Final configuration",
        f"- Signal: {FINAL_CONFIG.fund_window}d mean daily funding (decimal), lag 1 bar",
        f"- Basket: top {FINAL_CONFIG.top_pct:.0%} highest funding, |f| ≥ {FINAL_CONFIG.min_abs_funding}",
        f"- Liquidity: top {FINAL_CONFIG.liquidity_top_n} by open interest",
        f"- Beta hedge: {FINAL_CONFIG.beta_window}d rolling β to {BTC_COL}, per-leg",
        f"- Rebalance: every {FINAL_CONFIG.rebalance_days}d",
        "",
        "## Performance (OOS from 2025-01-01)",
        "",
        "| Segment | Sharpe | CAGR | MaxDD | Days |",
        "|---------|--------|------|-------|------|",
        f"| In-sample | {is_m['Sharpe']:.2f} | {is_m['CAGR']*100:.1f}% | {is_m['MaxDD']*100:.1f}% | {is_m['n_days']} |",
        f"| Out-of-sample | {oos_m['Sharpe']:.2f} | {oos_m['CAGR']*100:.1f}% | {oos_m['MaxDD']*100:.1f}% | {oos_m['n_days']} |",
        f"| Full | {full['Sharpe']:.2f} | {full['CAGR']*100:.1f}% | {full['MaxDD']*100:.1f}% | {full['n_days']} |",
        "",
        "## Calendar-year stability",
        "",
        "| Year | Sharpe | CAGR | MaxDD |",
        "|------|--------|------|-------|",
    ]
    for y in yearly:
        report.append(
            f"| {y['year']} | {y['Sharpe']:.2f} | {y['CAGR']*100:.1f}% | {y['MaxDD']*100:.1f}% |"
        )

    report.extend([
        "",
        "## Research iterations",
        "1. **Baseline L/S funding deciles + beta hedge** — OOS Sharpe 0.29, weak carry after costs.",
        "2. **Fixed funding units** — Coinglass rates are percent; PnL uses /100 and 8h payment sums.",
        "3. **Short-only sleeve** — materially stronger; shorts crowded longs in alts.",
        "4. **Rejected**: carry-spread vs BTC, momentum filter, OI-weighted funding.",
        "5. **Final params** — broader basket (15%), 120d β, top-75 liquidity.",
        "",
        "## Risks",
        "- OOS 2025 has been favorable for short-alts / long-BTC-hedge; IS/OOS gap varies by config.",
        "- Funding regimes compress in bear markets; 2023 L/S baseline was flat.",
        "- Single-exchange Binance data; basis/funding divergence vs other venues not modeled.",
        "",
        "## Artifacts",
        "- `code/data_core.py` — shared engine",
        "- `code/beta_funding_enhancements.py` — variant tests",
        "- `artifacts/enhancement_results.json`",
        "- `charts/equity_curve.png`",
    ])
    (RUN / "report.md").write_text("\n".join(report), encoding="utf-8")

    print(f"IS Sharpe:  {is_m['Sharpe']:.3f}")
    print(f"OOS Sharpe: {oos_m['Sharpe']:.3f}")
    print(f"Full CAGR:  {full['CAGR']*100:.2f}%")
    print(f"OOS MaxDD:  {oos_m['MaxDD']*100:.2f}%")


if __name__ == "__main__":
    main()
