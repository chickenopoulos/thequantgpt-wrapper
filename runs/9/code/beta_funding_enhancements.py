"""Enhancement experiments for beta-hedged funding harvest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_CODE_DIR = Path(__file__).resolve().parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

import numpy as np
import pandas as pd

from data_core import (
    BTC_COL,
    HarvestConfig,
    LAG,
    OOS,
    RUN,
    align_universe,
    beta_hedged_funding_returns,
    build_signal,
    liquidity_mask,
    load_close_panel,
    load_coinglass_panel,
    load_daily_funding_payments,
    metrics_from_returns,
    rolling_beta_to_btc,
    run_config,
    save_equity_chart,
    select_baskets,
    split_metrics,
    weights_from_baskets,
    write_json,
)


def carry_spread_signal(
    funding: pd.DataFrame,
    betas: pd.DataFrame,
    btc_funding: pd.Series,
    window: int,
) -> pd.DataFrame:
    """Net carry after beta-adjusted BTC hedge: alt_fund - beta * btc_fund."""
    smooth_alt = funding.rolling(window, min_periods=max(2, window // 2)).mean()
    smooth_btc = btc_funding.rolling(window, min_periods=max(2, window // 2)).mean()
    spread = smooth_alt.sub(smooth_btc, axis=0)
    for col in betas.columns:
        if col in spread.columns:
            spread[col] = spread[col] - (betas[col] * smooth_btc)
    return spread.shift(LAG)


def momentum_filtered_weights(
    close: pd.DataFrame,
    alt_w: pd.DataFrame,
    mom_window: int = 5,
    short_mom_cap: float = 0.15,
) -> pd.DataFrame:
    """Drop short legs in extreme positive momentum (squeeze risk)."""
    mom = close.pct_change(mom_window)
    out = alt_w.copy()
    for t in alt_w.index:
        row = alt_w.loc[t]
        shorts = row[row < 0].index
        for sym in shorts:
            m = mom.at[t, sym] if sym in mom.columns else np.nan
            if pd.notna(m) and m > short_mom_cap:
                out.at[t, sym] = 0.0
        # renormalize legs
        longs = out.loc[t, out.loc[t] > 0]
        shorts2 = out.loc[t, out.loc[t] < 0]
        if len(longs) > 0:
            out.loc[t, longs.index] = 0.5 / len(longs)
        if len(shorts2) > 0:
            out.loc[t, shorts2.index] = -0.5 / len(shorts2)
    return out


def regime_gate(funding: pd.DataFrame, window: int = 30, min_median: float = 0.00002) -> pd.Series:
    """Trade only when cross-sectional funding is elevated (carry-rich regime)."""
    xs_median = funding.median(axis=1)
    gate = xs_median.rolling(window, min_periods=10).median().shift(LAG) >= min_median
    return gate.fillna(False)


def run_enhanced(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    oi: pd.DataFrame,
    cfg: HarvestConfig,
    *,
    signal_mode: str = "raw",
    mom_filter: bool = False,
    gate: bool = False,
) -> dict:
    rets = close.pct_change()
    betas = rolling_beta_to_btc(rets, cfg.beta_window)
    btc_fund = funding[BTC_COL]

    if signal_mode == "carry_spread":
        signal = carry_spread_signal(funding, betas, btc_fund, cfg.fund_window)
    else:
        signal = build_signal(funding, close, cfg)

    tradable = liquidity_mask(close, oi, cfg.liquidity_top_n)
    long_b, short_b = select_baskets(
        signal,
        top_pct=cfg.top_pct,
        min_abs_funding=cfg.min_abs_funding,
        long_short=cfg.long_short,
        tradable=tradable,
    )
    alt_w = weights_from_baskets(long_b, short_b, cfg.rebalance_days)

    if mom_filter:
        alt_w = momentum_filtered_weights(close, alt_w)

    port_ret, _ = beta_hedged_funding_returns(
        close, funding, betas, alt_w, portfolio_hedge=cfg.portfolio_hedge
    )

    if gate:
        g = regime_gate(funding)
        port_ret = port_ret.where(g.reindex(port_ret.index).fillna(False))

    port_ret = port_ret.dropna()
    metrics = metrics_from_returns(port_ret)
    _, is_m, oos_m = split_metrics(metrics)
    return {
        "signal_mode": signal_mode,
        "mom_filter": mom_filter,
        "gate": gate,
        "params": cfg.__dict__,
        "metrics": metrics,
        "returns": port_ret,
        "summary": {
            "is_sharpe": is_m["Sharpe"],
            "oos_sharpe": oos_m["Sharpe"],
            "oos_cagr": oos_m["CAGR"],
            "oos_maxdd": oos_m["MaxDD"],
        },
    }


def main() -> None:
    close = load_close_panel()
    funding = load_daily_funding_payments()
    oi = load_coinglass_panel("futures_open_interest_history_ohlc_binance_1d.parquet", "close")
    close, funding, oi = align_universe(close, funding, oi)

    base = HarvestConfig()
    baseline = run_config(close, funding, oi, base)

    experiments = [
        ("baseline", dict(signal_mode="raw", mom_filter=False, gate=False)),
        ("carry_spread_signal", dict(signal_mode="carry_spread", mom_filter=False, gate=False)),
        ("momentum_filter", dict(signal_mode="raw", mom_filter=True, gate=False)),
        ("regime_gate", dict(signal_mode="raw", mom_filter=False, gate=True)),
        ("carry_spread+mom", dict(signal_mode="carry_spread", mom_filter=True, gate=False)),
        ("carry_spread+gate", dict(signal_mode="carry_spread", mom_filter=False, gate=True)),
        ("short_only", dict(signal_mode="raw", mom_filter=False, gate=False)),
        ("short_only+mom", dict(signal_mode="raw", mom_filter=True, gate=False)),
    ]

    rows = []
    best_ret = baseline["returns"]
    best_name = "baseline"
    best_oos = baseline["summary"]["oos_sharpe"]

    for name, kwargs in experiments:
        cfg = HarvestConfig(**{**base.__dict__})
        if name.startswith("short_only"):
            cfg = HarvestConfig(**{**cfg.__dict__, "long_short": False})
        res = run_enhanced(close, funding, oi, cfg, **kwargs)
        row = {"name": name, **res["summary"], **kwargs}
        rows.append(row)
        if res["summary"]["oos_sharpe"] > best_oos:
            best_oos = res["summary"]["oos_sharpe"]
            best_ret = res["returns"]
            best_name = name
        print(
            f"{name:22s} OOS Sharpe {res['summary']['oos_sharpe']:.3f}  "
            f"CAGR {res['summary']['oos_cagr']*100:5.1f}%  "
            f"MaxDD {res['summary']['oos_maxdd']*100:5.1f}%"
        )

    # OI-weighted funding variant
    oi_fund = load_coinglass_panel(
        "futures_funding_rate_oi_weight_binance_1d.parquet", "close"
    ) * (1.0 / 100.0)
    close2, oi_fund2, oi2 = align_universe(close, oi_fund, oi)
    oi_res = run_config(close2, oi_fund2, oi2, base)
    rows.append(
        {
            "name": "oi_weighted_funding",
            **oi_res["summary"],
            "signal_mode": "oi_weight",
        }
    )
    print(
        f"{'oi_weighted_funding':22s} OOS Sharpe {oi_res['summary']['oos_sharpe']:.3f}  "
        f"CAGR {oi_res['summary']['oos_cagr']*100:5.1f}%  "
        f"MaxDD {oi_res['summary']['oos_maxdd']*100:5.1f}%"
    )
    if oi_res["summary"]["oos_sharpe"] > best_oos:
        best_oos = oi_res["summary"]["oos_sharpe"]
        best_ret = oi_res["returns"]
        best_name = "oi_weighted_funding"

    df = pd.DataFrame(rows).sort_values("oos_sharpe", ascending=False)
    write_json(RUN / "artifacts" / "enhancement_results.json", df.to_dict(orient="records"))
    save_equity_chart(
        best_ret,
        RUN / "charts" / "best_enhanced_equity.png",
        f"Best enhanced: {best_name} (OOS Sharpe {best_oos:.2f})",
    )

    report = [
        "# Enhancement experiments",
        "",
        "| Variant | OOS Sharpe | OOS CAGR | OOS MaxDD |",
        "|---------|------------|----------|-----------|",
    ]
    for _, r in df.iterrows():
        report.append(
            f"| {r['name']} | {r['oos_sharpe']:.2f} | {r['oos_cagr']*100:.1f}% | {r['oos_maxdd']*100:.1f}% |"
        )
    report.append(f"\n**Best:** {best_name} (OOS Sharpe {best_oos:.2f})")
    (RUN / "report_enhancements.md").write_text("\n".join(report), encoding="utf-8")
    print(f"\nBest: {best_name} (OOS Sharpe {best_oos:.3f})")


if __name__ == "__main__":
    main()
