"""Batch backtest helpers for strategy catalog sweep (research only)."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import vectorbt as vbt

from tqg_client.market_data import default_annualization, load_market_data

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
OOS = pd.Timestamp("2025-01-01", tz="UTC")
FEE = 0.00045
SLIPPAGE = 0.0005
LAG = 1

warnings.filterwarnings("ignore", category=FutureWarning)


@dataclass
class SweepResult:
    id: str
    name: str
    universe: str
    asset_class: str
    sharpe: float | None = None
    max_dd: float | None = None
    cagr: float | None = None
    trades: int | None = None
    status: str = "OK"
    note: str = ""


class SkipStrategy(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _ann_factor(symbol: str, asset_class: str, interval: str) -> int:
    base = default_annualization(symbol, asset_class=asset_class)
    if interval == "1h":
        return base * 24
    return base


def _metrics_from_returns(returns: pd.Series, ann: int, trades: int | None = None) -> dict:
    r = returns.dropna()
    if r.empty or len(r) < 30:
        return {"Sharpe": 0.0, "MaxDD": 0.0, "CAGR": 0.0, "trades": trades or 0}
    cum = (1 + r).cumprod()
    dd = cum / cum.cummax() - 1
    vol = r.std()
    sharpe = float(np.sqrt(ann) * r.mean() / vol) if vol > 0 else 0.0
    cagr = float(cum.iloc[-1] ** (ann / len(r)) - 1) if len(r) > 0 else 0.0
    return {
        "Sharpe": sharpe,
        "MaxDD": float(dd.min()),
        "CAGR": cagr,
        "trades": trades or int((r != 0).sum()),
    }


def run_signal_backtest(
    close: pd.Series,
    entries: pd.Series,
    exits: pd.Series,
    *,
    symbol: str = "BTCUSDT",
    asset_class: str = "crypto",
    interval: str = "1d",
    short_entries: pd.Series | None = None,
    short_exits: pd.Series | None = None,
    freq: str | None = None,
) -> dict:
    ann = _ann_factor(symbol, asset_class, interval)
    freq = freq or ("1H" if interval == "1h" else "1D")
    pf = vbt.Portfolio.from_signals(
        close.astype(float),
        entries=entries.fillna(False).astype(bool),
        exits=exits.fillna(False).astype(bool),
        short_entries=short_entries.fillna(False).astype(bool) if short_entries is not None else False,
        short_exits=short_exits.fillna(False).astype(bool) if short_exits is not None else False,
        fees=FEE,
        slippage=SLIPPAGE,
        freq=freq,
    )
    try:
        n_trades = int(pf.trades.count())
    except Exception:
        n_trades = 0
    return _metrics_from_returns(pf.returns(), ann, n_trades)


def load_ohlcv(symbol: str, interval: str = "1d") -> tuple[pd.DataFrame, str]:
    df, src = load_market_data(symbol, data_dir=DATA, interval=interval)
    return df, src


def load_close(symbol: str, interval: str = "1d") -> pd.Series:
    return load_ohlcv(symbol, interval)[0]["close"].astype(float)


def load_equity_close(symbol: str) -> pd.Series:
    return load_market_data(symbol, data_dir=DATA, interval="1d")[0]["close"].astype(float)


def load_universe_daily() -> pd.DataFrame:
    path = DATA / "binance" / "binance_futures_ohlcv_1d.parquet"
    df = pd.read_parquet(path)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df


def universe_close_panel(min_bars: int = 200) -> pd.DataFrame:
    df = load_universe_daily()
    counts = df.groupby("asset").size()
    valid = counts[counts >= min_bars].index
    df = df[df["asset"].isin(valid)]
    wide = df.pivot_table(index="time", columns="asset", values="close", aggfunc="last").sort_index()
    return wide.astype(float)


def efficiency_ratio(close: pd.Series, window: int = 20) -> pd.Series:
    change = close.diff(window).abs()
    path = close.diff().abs().rolling(window).sum()
    return (change / path).replace([np.inf, -np.inf], np.nan)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    tr = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window).mean()


def load_coinglass_daily(path_rel: str, value_col: str = "close", symbol: str | None = "BTCUSDT") -> pd.Series:
    path = DATA / "coinglass" / path_rel
    if not path.exists():
        raise SkipStrategy(f"missing {path_rel}")
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_parquet(path)
    if "date" in df.columns:
        idx = pd.to_datetime(df["date"], utc=True)
    elif "time" in df.columns:
        idx = pd.to_datetime(df["time"], utc=True)
    else:
        idx = pd.to_datetime(df.index, utc=True)
    df = df.copy()
    df.index = idx
    if symbol and "symbol" in df.columns:
        sym = df["symbol"].astype(str).str.upper()
        if symbol.upper() in sym.values:
            df = df[sym == symbol.upper()]
        elif "BTC" in symbol.upper():
            df = df[sym.str.contains("BTC", na=False)]
    if path_rel.startswith("exchange_balance"):
        num = df.select_dtypes(include="number")
        s = num.sum(axis=1).astype(float)
        return s.groupby(s.index).last().sort_index()
    if value_col not in df.columns:
        for c in ("close", "close_basis", "flow_usd", "value", "long_liquidation_usd"):
            if c in df.columns:
                value_col = c
                break
        else:
            num = df.select_dtypes(include="number")
            if num.empty:
                raise SkipStrategy(f"no numeric column in {path_rel}")
            s = num.iloc[:, 0].astype(float)
            return s.groupby(s.index).last().sort_index()
    s = df[value_col].astype(float).sort_index()
    return s.groupby(s.index).last()


def load_btc_talos_metrics() -> pd.DataFrame:
    path = DATA / "talos" / "cm_btc_asset_metrics_1d.parquet"
    if not path.exists():
        raise SkipStrategy("missing cm_btc_asset_metrics_1d.parquet")
    df = pd.read_parquet(path)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df.set_index("time").sort_index()


def align_to_close(series: pd.Series, close_index: pd.DatetimeIndex) -> pd.Series:
    s = series.reindex(close_index, method="ffill").shift(LAG)
    return s


def cross_section_ls_returns(
    wide_close: pd.DataFrame,
    signal: pd.DataFrame,
    *,
    top_pct: float = 0.1,
    bottom_pct: float = 0.1,
    long_only: bool = False,
) -> pd.Series:
    rets = wide_close.pct_change()
    fwd = rets.shift(-1)
    port = pd.Series(0.0, index=wide_close.index)
    for t in signal.index:
        if t not in fwd.index:
            continue
        row = signal.loc[t].dropna()
        if len(row) < 20:
            continue
        n_top = max(1, int(len(row) * top_pct))
        n_bot = max(1, int(len(row) * bottom_pct))
        top = row.nlargest(n_top).index
        bot = row.nsmallest(n_bot).index
        f = fwd.loc[t].reindex(row.index).dropna()
        if f.empty:
            continue
        if long_only:
            port.loc[t] = f.reindex(top).mean()
        else:
            port.loc[t] = f.reindex(top).mean() - f.reindex(bot).mean()
    return port.dropna()


def result_from_returns(
    rid: str,
    name: str,
    universe: str,
    asset_class: str,
    returns: pd.Series,
    symbol: str = "UNIVERSE",
    interval: str = "1d",
    trades: int | None = None,
) -> SweepResult:
    ann = _ann_factor(symbol, asset_class, interval)
    m = _metrics_from_returns(returns, ann, trades)
    return SweepResult(
        id=rid,
        name=name,
        universe=universe,
        asset_class=asset_class,
        sharpe=m["Sharpe"],
        max_dd=m["MaxDD"],
        cagr=m["CAGR"],
        trades=m["trades"],
    )


def wrap(fn: Callable[[], SweepResult]) -> Callable[[], SweepResult]:
    def _inner() -> SweepResult:
        try:
            return fn()
        except SkipStrategy as e:
            return SweepResult(
                id=fn.__name__.replace("s_", "").replace("_", "-").upper()[:10],
                name=fn.__name__,
                universe="—",
                asset_class="—",
                status="SKIP",
                note=str(e.reason),
            )
        except Exception as e:
            return SweepResult(
                id=fn.__name__,
                name=fn.__name__,
                universe="—",
                asset_class="—",
                status="ERROR",
                note=str(e)[:120],
            )
    return _inner
