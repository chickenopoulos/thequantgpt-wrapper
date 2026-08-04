"""Shared configuration for triangular pairs trading research."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAB_ROOT = PROJECT_ROOT.parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"

# Lab data under repo root; override with TRIANGULAR_DATA_DIR if needed.
DATA_DIR = Path(__import__("os").environ.get("TRIANGULAR_DATA_DIR", str(LAB_ROOT / "data")))
FUTURES_DAILY = DATA_DIR / "binance" / "binance_futures_ohlcv_1d.parquet"
FUTURES_HOURLY = DATA_DIR / "binance" / "binance_futures_ohlcv_1h.parquet"

OOS_START = "2025-01-01"
ANN_FACTOR = 365  # crypto 24/7
LAG_BARS = 1

# Binance USDT-M perp taker fee (approx) + slippage per leg.
FEE_PER_LEG = 0.00045
SLIPPAGE_PER_LEG = 0.0005
COST_PER_LEG = FEE_PER_LEG + SLIPPAGE_PER_LEG

# Liquid majors used as triangle anchors.
ANCHORS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT")

# Per-interval defaults (window/min_periods in bars of that interval).
INTERVAL_PROFILES: dict[str, dict] = {
    "1d": {
        "ann_factor": 365,
        "window": 120,
        "min_periods": 90,
        "min_history": 500,
        "refresh_freq": "90D",
        "lookback_days": 365,
        "liquid_top_n": 40,
    },
    "1h": {
        "ann_factor": 365 * 24,
        "window": 720,       # ~30 days
        "min_periods": 360,  # ~15 days
        "min_history": 2_000,
        "refresh_freq": "30D",
        "lookback_days": 90,
        "liquid_top_n": 30,
    },
}


def profile(interval: str) -> dict:
    if interval not in INTERVAL_PROFILES:
        raise ValueError(f"unknown interval {interval!r}; expected one of {list(INTERVAL_PROFILES)}")
    return INTERVAL_PROFILES[interval]
