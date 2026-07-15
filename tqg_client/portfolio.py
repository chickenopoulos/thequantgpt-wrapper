"""Minimal hybrid portfolio builder for Cursor Lab standalone runs.

Satisfies MCP validation patterns that expect build_portfolio_from_strategy_spec
without requiring the full thequantgpt package on the client server.
"""

from __future__ import annotations

import inspect
from typing import Any

import pandas as pd
import vectorbt as vbt

_SIGNAL_ALIASES = {
    "entries": ("entries", "long_entries", "long_entry", "long_entry_cond"),
    "exits": ("exits", "long_exits", "long_exit", "long_exit_cond"),
    "short_entries": ("short_entries", "short_entry", "short_entry_cond"),
    "short_exits": ("short_exits", "short_exit", "short_exit_cond"),
}


def _caller_locals(depth: int = 2) -> dict[str, Any]:
    frame = inspect.currentframe()
    try:
        current = frame.f_back if frame is not None else None
        for _ in range(depth):
            if current is None:
                return {}
            current = current.f_back
        return dict(current.f_locals) if current is not None else {}
    finally:
        del frame


def _resolve_signals(namespace: dict[str, Any]) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for canonical, aliases in _SIGNAL_ALIASES.items():
        for name in aliases:
            value = namespace.get(name)
            if isinstance(value, pd.Series):
                out[canonical] = value.fillna(False).astype(bool)
                break
            if isinstance(value, pd.DataFrame):
                out[canonical] = value.fillna(False).astype(bool)
                break
    return out


def build_portfolio_from_strategy_spec(
    strategy_spec: dict[str, Any],
    close: pd.Series,
    **kwargs: Any,
) -> vbt.Portfolio:
    """Build pf from precomputed entries/exits in the caller namespace."""
    signals: dict[str, pd.Series] = {}
    for depth in range(1, 10):
        signals = _resolve_signals(_caller_locals(depth=depth))
        if "entries" in signals and "exits" in signals:
            break
    if "entries" not in signals or "exits" not in signals:
        raise ValueError(
            "build_portfolio_from_strategy_spec requires entries/exits in the caller namespace"
        )

    params = (strategy_spec or {}).get("params") or {}
    costs = (strategy_spec or {}).get("costs") or {}
    fee = float(kwargs.get("fee", costs.get("fee", params.get("fee", 0.00045))))
    slippage = float(kwargs.get("slippage", costs.get("slippage", params.get("slippage", 0.0005))))

    short_entries = signals.get("short_entries")
    short_exits = signals.get("short_exits")

    return vbt.Portfolio.from_signals(
        close,
        entries=signals["entries"],
        exits=signals["exits"],
        short_entries=short_entries if short_entries is not None else False,
        short_exits=short_exits if short_exits is not None else False,
        fees=fee,
        slippage=slippage,
        freq="1D",
    )
