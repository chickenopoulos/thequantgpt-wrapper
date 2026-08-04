"""Shared data loading and portfolio math for beta-hedged funding harvest."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs" / "9"
DATA = REPO / "data"

OOS = pd.Timestamp("2025-01-01", tz="UTC")
ANN = 365
LAG = 1
FEE = 0.00045
SLIPPAGE = 0.0005
BTC_COL = "BTCUSDT"
MIN_UNIVERSE = 30
# Coinglass funding rates are stored in percent (0.01 = 0.01% per observation).
FUNDING_PCT_TO_DECIMAL = 1.0 / 100.0
FUNDING_PAYMENT_HOURS = (0, 8, 16)


def load_coinglass_panel(path_rel: str, value_col: str) -> pd.DataFrame:
    path = DATA / "coinglass" / path_rel
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    panel = (
        df.pivot_table(index="date", columns="symbol", values=value_col, aggfunc="last")
        .sort_index()
    )
    return panel.apply(pd.to_numeric, errors="coerce").astype(float)


def load_daily_funding_payments() -> pd.DataFrame:
    """Daily funding accrual in decimal return units (percent / 100).

  Prefer summing 8h payment observations from hourly Coinglass data; fill
  earlier history from the daily parquet (close * pct_to_decimal).
    """
    daily_fallback = load_coinglass_panel(
        "futures_funding_rate_binance_1d.parquet", "close"
    ) * FUNDING_PCT_TO_DECIMAL

    path = DATA / "coinglass" / "futures_funding_rate_binance_1h.parquet"
    if not path.exists():
        return daily_fallback

    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["hour"] = df["date"].dt.hour
    payments = df[df["hour"].isin(FUNDING_PAYMENT_HOURS)].copy()
    payments["day"] = payments["date"].dt.floor("D")
    hourly_daily = payments.pivot_table(
        index="day", columns="symbol", values="close", aggfunc="sum"
    ).sort_index() * FUNDING_PCT_TO_DECIMAL

    # Hourly file is partial; extend with daily fallback for missing dates/symbols.
    combined = hourly_daily.combine_first(daily_fallback)
    combined = combined.reindex(
        index=daily_fallback.index.union(hourly_daily.index).sort_values(),
        columns=daily_fallback.columns.union(hourly_daily.columns).sort_values(),
    )
    combined = combined.combine_first(daily_fallback)
    return combined.sort_index(axis=0).sort_index(axis=1)


def load_close_panel() -> pd.DataFrame:
    df = pd.read_parquet(
        DATA / "binance" / "binance_futures_ohlcv_1d.parquet",
        columns=["time", "asset", "close"],
    )
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return (
        df.pivot_table(index="time", columns="asset", values="close", aggfunc="last")
        .sort_index()
        .astype(float)
    )


def align_universe(*panels: pd.DataFrame) -> tuple[pd.DataFrame, ...]:
    symbols = panels[0].columns
    for panel in panels[1:]:
        symbols = symbols.intersection(panel.columns)
    symbols = symbols.sort_values()
    idx = panels[0].index
    for panel in panels[1:]:
        idx = idx.intersection(panel.index)
    idx = idx.sort_values()
    return tuple(panel.reindex(index=idx, columns=symbols) for panel in panels)


def rolling_beta_to_btc(returns: pd.DataFrame, window: int, btc_col: str = BTC_COL) -> pd.DataFrame:
    btc = returns[btc_col]
    betas: dict[str, pd.Series] = {}
    var = btc.rolling(window, min_periods=max(20, window // 3)).var()
    for col in returns.columns:
        if col == btc_col:
            continue
        cov = returns[col].rolling(window, min_periods=max(20, window // 3)).cov(btc)
        betas[col] = cov / var.replace(0, np.nan)
    return pd.DataFrame(betas)


def liquidity_mask(close: pd.DataFrame, oi: pd.DataFrame, top_n: int | None) -> pd.DataFrame:
    """True where symbol is in top-N OI cross-section for that date."""
    if top_n is None:
        return pd.DataFrame(True, index=close.index, columns=close.columns)
    rank = oi.rank(axis=1, ascending=False, method="first")
    return rank <= top_n


def smooth_funding(funding: pd.DataFrame, window: int) -> pd.DataFrame:
    return funding.rolling(window, min_periods=max(2, window // 2)).mean()


def metrics_from_returns(returns: pd.Series, oos: pd.Timestamp = OOS) -> dict:
    r = returns.dropna()
    if r.empty or len(r) < 30:
        return {"Sharpe": 0.0, "CAGR": 0.0, "MaxDD": 0.0, "n_days": int(len(r))}

    def _block(seg: pd.Series) -> dict:
        if seg.empty or len(seg) < 20:
            return {"Sharpe": 0.0, "CAGR": 0.0, "MaxDD": 0.0, "n_days": int(len(seg))}
        mu = seg.mean()
        sd = seg.std()
        sharpe = float(mu / sd * np.sqrt(ANN)) if sd > 0 else 0.0
        equity = (1 + seg).cumprod()
        cagr = float(equity.iloc[-1] ** (ANN / len(seg)) - 1) if len(seg) > 0 else 0.0
        dd = float((equity / equity.cummax() - 1).min())
        return {"Sharpe": sharpe, "CAGR": cagr, "MaxDD": dd, "n_days": int(len(seg))}

    is_mask = r.index < oos
    return {
        "full_sample": _block(r),
        "in_sample": _block(r.loc[is_mask]),
        "out_of_sample": _block(r.loc[~is_mask]),
    }


def split_metrics(metrics: dict) -> tuple[dict, dict, dict]:
    return metrics["full_sample"], metrics["in_sample"], metrics["out_of_sample"]


@dataclass(frozen=True)
class HarvestConfig:
    fund_window: int = 7
    beta_window: int = 90
    top_pct: float = 0.10
    min_abs_funding: float = 0.00003
    rebalance_days: int = 5
    liquidity_top_n: int | None = 50
    long_short: bool = True
    vol_adjust: bool = False
    portfolio_hedge: bool = False

    @property
    def name(self) -> str:
        ls = "ls" if self.long_short else "short_only"
        hedge = "port" if self.portfolio_hedge else "leg"
        liq = f"liq{self.liquidity_top_n}" if self.liquidity_top_n else "liqall"
        va = "voladj" if self.vol_adjust else "raw"
        return (
            f"fw{self.fund_window}_bw{self.beta_window}_{ls}_{hedge}_{liq}_"
            f"rb{self.rebalance_days}_{va}_mf{self.min_abs_funding:g}"
        )


def select_baskets(
    signal: pd.DataFrame,
    *,
    top_pct: float,
    min_abs_funding: float,
    long_short: bool,
    tradable: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return long (+1) and short (-1) basket indicators."""
    long_basket = pd.DataFrame(0.0, index=signal.index, columns=signal.columns)
    short_basket = pd.DataFrame(0.0, index=signal.index, columns=signal.columns)

    for t in signal.index:
        row = signal.loc[t]
        if tradable is not None:
            mask = tradable.loc[t].fillna(False)
            row = row.where(mask)
        row = row.dropna()
        if len(row) < MIN_UNIVERSE:
            continue
        if min_abs_funding > 0:
            row = row[row.abs() >= min_abs_funding]
        if len(row) < MIN_UNIVERSE:
            continue

        n = max(1, int(len(row) * top_pct))
        shorts = row.nlargest(n)
        short_basket.loc[t, shorts.index] = -1.0

        if long_short:
            longs = row.nsmallest(n)
            long_basket.loc[t, longs.index] = 1.0

    return long_basket, short_basket


def weights_from_baskets(
    long_basket: pd.DataFrame,
    short_basket: pd.DataFrame,
    rebalance_days: int,
) -> pd.DataFrame:
    """Equal-weight L/S weights, held between rebalance days."""
    raw = long_basket.add(short_basket, fill_value=0.0)
    n_long = long_basket.abs().sum(axis=1).replace(0, np.nan)
    n_short = short_basket.abs().sum(axis=1).replace(0, np.nan)

    weights = pd.DataFrame(0.0, index=raw.index, columns=raw.columns)
    for t in raw.index:
        longs = long_basket.loc[t]
        shorts = short_basket.loc[t]
        n_l = (longs != 0).sum()
        n_s = (shorts != 0).sum()
        if n_l == 0 and n_s == 0:
            continue
        if n_l > 0:
            weights.loc[t, longs != 0] = 0.5 / n_l
        if n_s > 0:
            weights.loc[t, shorts != 0] = -0.5 / n_s

    if rebalance_days <= 1:
        return weights

    held = weights.copy()
    last_reb = None
    for i, t in enumerate(weights.index):
        if last_reb is None or i % rebalance_days == 0:
            held.loc[t] = weights.loc[t]
            last_reb = t
        else:
            held.loc[t] = held.loc[last_reb]
    return held


def beta_hedged_funding_returns(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    betas: pd.DataFrame,
    alt_weights: pd.DataFrame,
    *,
    portfolio_hedge: bool = False,
    apply_costs: bool = True,
) -> tuple[pd.Series, pd.DataFrame]:
    """
    Daily returns for beta-hedged funding harvest.

    alt_weights: signed fraction of portfolio in each alt (+ long, - short).
    BTC hedge per leg: -direction * beta * alt_weight.
    Funding received: -direction * funding * |alt_weight|.
    """
    rets = close.pct_change()
    btc_ret = rets[BTC_COL]
    symbols = [c for c in alt_weights.columns if c != BTC_COL]

    alt_w = alt_weights[symbols].fillna(0.0)
    beta_aligned = betas.reindex(index=alt_w.index, columns=symbols).shift(LAG).fillna(1.0).clip(-3, 3)

    # Price PnL on alt legs
    alt_price = (alt_w.shift(LAG) * rets[symbols].shift(0)).sum(axis=1)

    # BTC hedge
    if portfolio_hedge:
        net_beta = (alt_w.shift(LAG) * beta_aligned).sum(axis=1)
        btc_hedge_w = -net_beta
    else:
        btc_hedge_w = -(alt_w.shift(LAG) * beta_aligned).sum(axis=1)
    btc_hedge_pnl = btc_hedge_w * btc_ret

    # Funding already in decimal (sum of 8h payments); signal uses same units.
    fund_aligned = funding.reindex(index=alt_w.index, columns=symbols).shift(LAG)
    funding_pnl = (-alt_w.shift(LAG) * fund_aligned).sum(axis=1)

    gross = alt_price + btc_hedge_pnl + funding_pnl

    if not apply_costs:
        return gross.dropna(), alt_w

    # Turnover costs on alt + btc hedge weight changes
    btc_w = btc_hedge_w.to_frame(BTC_COL)
    combined = pd.concat([alt_w, btc_w], axis=1).fillna(0.0)
    turnover = combined.diff().abs().sum(axis=1)
    costs = turnover * (FEE + SLIPPAGE)
    net = (gross - costs).dropna()
    return net, alt_w


def build_signal(
    funding: pd.DataFrame,
    close: pd.DataFrame,
    cfg: HarvestConfig,
) -> pd.DataFrame:
    sig = smooth_funding(funding, cfg.fund_window)
    if cfg.vol_adjust:
        vol = close.pct_change().rolling(20, min_periods=10).std()
        sig = sig.div(vol.replace(0, np.nan))
    return sig.shift(LAG)


def run_config(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    oi: pd.DataFrame,
    cfg: HarvestConfig,
) -> dict:
    rets = close.pct_change()
    betas = rolling_beta_to_btc(rets, cfg.beta_window)
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
    port_ret, weights = beta_hedged_funding_returns(
        close,
        funding,
        betas,
        alt_w,
        portfolio_hedge=cfg.portfolio_hedge,
    )
    metrics = metrics_from_returns(port_ret)
    full, is_m, oos_m = split_metrics(metrics)
    return {
        "config": cfg.name,
        "params": {
            "fund_window": cfg.fund_window,
            "beta_window": cfg.beta_window,
            "top_pct": cfg.top_pct,
            "min_abs_funding": cfg.min_abs_funding,
            "rebalance_days": cfg.rebalance_days,
            "liquidity_top_n": cfg.liquidity_top_n,
            "long_short": cfg.long_short,
            "vol_adjust": cfg.vol_adjust,
            "portfolio_hedge": cfg.portfolio_hedge,
        },
        "metrics": metrics,
        "returns": port_ret,
        "weights": weights,
        "summary": {
            "full_sharpe": full["Sharpe"],
            "is_sharpe": is_m["Sharpe"],
            "oos_sharpe": oos_m["Sharpe"],
            "full_cagr": full["CAGR"],
            "oos_cagr": oos_m["CAGR"],
            "full_maxdd": full["MaxDD"],
            "oos_maxdd": oos_m["MaxDD"],
        },
    }


def save_equity_chart(returns: pd.Series, path: Path, title: str) -> None:
    import matplotlib.pyplot as plt

    equity = (1 + returns).cumprod()
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    equity.plot(ax=axes[0], color="steelblue", lw=1.2)
    axes[0].set_title(title)
    axes[0].set_ylabel("Equity")
    axes[0].axvline(OOS, color="crimson", ls="--", alpha=0.7, label="OOS start")
    axes[0].legend()
    dd = equity / equity.cummax() - 1
    dd.plot(ax=axes[1], color="firebrick", lw=1.0)
    axes[1].set_ylabel("Drawdown")
    axes[1].set_xlabel("Date")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def _default(o: object) -> object:
        if isinstance(o, (pd.Timestamp, np.datetime64)):
            return str(o)
        if isinstance(o, (np.floating, np.integer)):
            return float(o)
        if isinstance(o, pd.Series):
            return {str(k): float(v) for k, v in o.dropna().items()}
        raise TypeError(type(o))

    path.write_text(json.dumps(obj, indent=2, default=_default), encoding="utf-8")
