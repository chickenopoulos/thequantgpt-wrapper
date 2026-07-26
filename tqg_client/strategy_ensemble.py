"""Extract per-strategy positions and build per-asset ensembles."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import vectorbt as vbt

from tqg_client.market_data import default_annualization, load_market_data
from tqg_client.strategy_sweep_core import (
    DATA,
    FEE,
    OOS,
    SLIPPAGE,
    load_close,
    load_ohlcv,
    result_from_returns,
    run_signal_backtest,
    SkipStrategy,
    SweepResult,
    _ann_factor,
    _metrics_from_returns,
)

_CAPTURED: list["CapturedStrategy"] = []
_PATCHED = False


@dataclass
class CapturedStrategy:
    id: str
    name: str
    symbol: str
    interval: str
    asset_class: str
    close: pd.Series
    position: pd.Series
    universe: str = ""


@dataclass
class EnsembleResult:
    symbol: str
    interval: str
    asset_class: str
    n_strategies: int
    strategy_ids: list[str]
    sharpe: float
    max_dd: float
    cagr: float
    trades: int
    sharpe_is: float
    sharpe_oos: float


def position_from_signals(
    entries: pd.Series,
    exits: pd.Series,
    short_entries: pd.Series | None = None,
    short_exits: pd.Series | None = None,
) -> pd.Series:
    """Daily position in [-1, 0, 1] from entry/exit booleans."""
    idx = entries.index
    pos = pd.Series(0.0, index=idx)
    state = 0.0
    se = short_entries.fillna(False).astype(bool) if short_entries is not None else pd.Series(False, index=idx)
    sx = short_exits.fillna(False).astype(bool) if short_exits is not None else pd.Series(False, index=idx)
    en = entries.fillna(False).astype(bool)
    ex = exits.fillna(False).astype(bool)

    for t in idx:
        if state == 0.0:
            if en.loc[t]:
                state = 1.0
            elif se.loc[t]:
                state = -1.0
        elif state > 0:
            if ex.loc[t]:
                state = 0.0
        else:
            if sx.loc[t]:
                state = 0.0
        pos.loc[t] = state
    return pos


def _returns_to_position(returns: pd.Series, close: pd.Series) -> pd.Series:
    asset = close.reindex(returns.index).pct_change()
    raw = returns / asset.replace(0, np.nan)
    return raw.fillna(0).clip(-2, 2)


def _patch_capture() -> None:
    global _PATCHED
    if _PATCHED:
        return

    import tqg_client.strategy_catalog_runners_a as ra
    import tqg_client.strategy_catalog_runners_b as rb
    import tqg_client.strategy_sweep_core as core

    _m_orig = ra._m
    _rfr_orig = core.result_from_returns

    def _m_capture(
        rid: str,
        name: str,
        universe: str,
        ac: str,
        close: pd.Series,
        entries: pd.Series,
        exits: pd.Series,
        interval: str = "1d",
        short_entries: pd.Series | None = None,
        short_exits: pd.Series | None = None,
        symbol: str = "BTCUSDT",
    ) -> SweepResult:
        pos = position_from_signals(entries, exits, short_entries, short_exits)
        _CAPTURED.append(
            CapturedStrategy(
                id=rid,
                name=name,
                symbol=_normalize_symbol(symbol),
                interval=interval,
                asset_class=ac,
                close=close.astype(float),
                position=pos.reindex(close.index).fillna(0),
                universe=universe,
            )
        )
        return _m_orig(
            rid, name, universe, ac, close, entries, exits,
            interval=interval,
            short_entries=short_entries,
            short_exits=short_exits,
            symbol=symbol,
        )

    def _rfr_capture(
        rid: str,
        name: str,
        universe: str,
        asset_class: str,
        returns: pd.Series,
        symbol: str = "UNIVERSE",
        interval: str = "1d",
        trades: int | None = None,
    ) -> SweepResult:
        if symbol in ("UNIVERSE", "BTC") and rid.startswith("XS"):
            return _rfr_orig(rid, name, universe, asset_class, returns, symbol, interval, trades)
        try:
            if interval == "1h":
                close = load_ohlcv(symbol if symbol != "BTC" else "BTCUSDT", "1h")[0]["close"].astype(float)
            elif symbol == "BTC":
                close = load_close("BTCUSDT")
                symbol = "BTCUSDT"
            elif symbol == "VIX":
                close = load_equity_close("^VIX")
                symbol = "^VIX"
            else:
                close = _load_close_for_symbol(symbol)
        except Exception:
            return _rfr_orig(rid, name, universe, asset_class, returns, symbol, interval, trades)

        pos = _returns_to_position(returns.astype(float), close)
        _CAPTURED.append(
            CapturedStrategy(
                id=rid,
                name=name,
                symbol=_normalize_symbol(symbol),
                interval=interval,
                asset_class=asset_class,
                close=close.reindex(returns.index).ffill(),
                position=pos,
                universe=universe,
            )
        )
        return _rfr_orig(rid, name, universe, asset_class, returns, symbol, interval, trades)

    ra._m = _m_capture
    rb._m = _m_capture
    core.result_from_returns = _rfr_capture
    _PATCHED = True


def load_equity_close(symbol: str) -> pd.Series:
    df, _ = load_market_data(symbol, data_dir=DATA, interval="1d")
    return df["close"].astype(float)


def _normalize_symbol(symbol: str) -> str:
    if symbol == "BTC":
        return "BTCUSDT"
    if symbol == "VIX":
        return "^VIX"
    return symbol


def _master_close(symbol: str, interval: str) -> pd.Series:
    sym = _normalize_symbol(symbol)
    if interval == "1h":
        df, _ = load_ohlcv(sym, "1h")
        return df["close"].astype(float)
    if sym.endswith("USDT"):
        return load_close(sym)
    return _load_close_for_symbol(sym)


def capture_all_strategies() -> list[CapturedStrategy]:
    """Run catalog runners and collect per-strategy positions."""
    global _CAPTURED
    _CAPTURED = []
    _patch_capture()

    import importlib
    import re

    ra = importlib.import_module("tqg_client.strategy_catalog_runners_a")
    rb = importlib.import_module("tqg_client.strategy_catalog_runners_b")
    pat = re.compile(r"^run_[A-Z]+_\d+$")

    for mod in (ra, rb):
        for name in sorted(dir(mod)):
            if not pat.match(name):
                continue
            fn = getattr(mod, name)
            try:
                fn()
            except SkipStrategy:
                continue
            except Exception:
                continue

    return list(_CAPTURED)


def _asset_key(c: CapturedStrategy) -> str:
    return f"{_normalize_symbol(c.symbol)}|{c.interval}"


def _load_close_for_symbol(symbol: str) -> pd.Series:
    sym = _normalize_symbol(symbol)
    if sym.endswith("USDT"):
        return load_close(sym)
    return load_equity_close(sym)


def ensemble_positions(positions: list[pd.Series], index: pd.DatetimeIndex) -> pd.Series:
    """Equal-weight mean of member positions, clipped to [-1, 1]."""
    df = pd.DataFrame({str(i): s.reindex(index).fillna(0) for i, s in enumerate(positions)})
    return df.mean(axis=1).clip(-1.0, 1.0)


def _ensemble_metrics(close: pd.Series, position: pd.Series, symbol: str, asset_class: str, interval: str) -> dict:
    asset_rets = close.pct_change().fillna(0)
    pos = position.reindex(close.index).fillna(0)
    gross = pos.shift(1).fillna(0) * asset_rets
    turnover = pos.diff().abs().fillna(0)
    net = gross - turnover * (FEE + SLIPPAGE)
    ann = _ann_factor(symbol, asset_class, interval)
    m = _metrics_from_returns(net, ann)
    r = net.dropna()
    r_is = r.loc[r.index < OOS]
    r_oos = r.loc[r.index >= OOS]

    def _sharpe(s: pd.Series) -> float:
        if s.empty or s.std() == 0:
            return 0.0
        return float(np.sqrt(ann) * s.mean() / s.std())

    return {
        "Sharpe": m["Sharpe"],
        "MaxDD": m["MaxDD"],
        "CAGR": m["CAGR"],
        "trades": int(turnover[turnover > 0].count()),
        "sharpe_is": _sharpe(r_is),
        "sharpe_oos": _sharpe(r_oos),
    }


def run_asset_ensembles(captured: list[CapturedStrategy] | None = None) -> list[EnsembleResult]:
    captured = captured or capture_all_strategies()

    # Skip cross-section / multi-asset portfolio returns
    skip_symbols = {"UNIVERSE"}
    skip_ids_prefix = ("XS-",)

    groups: dict[str, list[CapturedStrategy]] = {}
    for c in captured:
        if c.symbol in skip_symbols or any(c.id.startswith(p) for p in skip_ids_prefix):
            continue
        if c.id in ("TAA-04", "IA-07", "CG-19"):
            continue
        groups.setdefault(_asset_key(c), []).append(c)

    results: list[EnsembleResult] = []
    for key, items in sorted(groups.items()):
        if len(items) < 2:
            continue
        symbol, interval = key.split("|", 1)
        try:
            close = _master_close(symbol, interval)
        except Exception:
            continue
        idx = close.index
        positions = [it.position.reindex(idx).fillna(0) for it in items]
        ensemble_pos = ensemble_positions(positions, idx)
        ac = items[0].asset_class
        if symbol.endswith("USDT"):
            ac = "crypto"
        m = _ensemble_metrics(close, ensemble_pos, symbol, ac, interval)
        results.append(
            EnsembleResult(
                symbol=symbol,
                interval=interval,
                asset_class=items[0].asset_class,
                n_strategies=len(items),
                strategy_ids=[it.id for it in items],
                sharpe=m["Sharpe"],
                max_dd=m["MaxDD"],
                cagr=m["CAGR"],
                trades=m["trades"],
                sharpe_is=m["sharpe_is"],
                sharpe_oos=m["sharpe_oos"],
            )
        )

    results.sort(key=lambda r: r.sharpe, reverse=True)
    return results


def format_ensemble_table(results: list[EnsembleResult]) -> str:
    lines = [
        "| Asset | Interval | N Strats | Sharpe | IS Sharpe | OOS Sharpe | MaxDD | CAGR | Trades |",
        "|-------|----------|----------|--------|-----------|------------|-------|------|--------|",
    ]
    for r in results:
        lines.append(
            f"| {r.symbol} | {r.interval} | {r.n_strategies} | {r.sharpe:.2f} | {r.sharpe_is:.2f} | {r.sharpe_oos:.2f} | {r.max_dd:.1%} | {r.cagr:.1%} | {r.trades} |"
        )
    return "\n".join(lines)


def format_strategy_lists(results: list[EnsembleResult]) -> str:
    lines = ["## Strategies per ensemble\n"]
    for r in results:
        ids = ", ".join(r.strategy_ids)
        lines.append(f"### {r.symbol} ({r.interval}) — {r.n_strategies} strategies\n{ids}\n")
    return "\n".join(lines)
