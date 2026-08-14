"""TQG-compliant triangular pairs engine (imports research core, IS-safe selection)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
RESEARCH = REPO / "research" / "triangular-pairs-trading"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

from src.backtest import backtest_triangles, compute_metrics  # noqa: E402
from src.config import ANCHORS, COST_PER_LEG, OOS_START  # noqa: E402
from src.data import load_close_panel, log_prices  # noqa: E402
from src.triangles import Triangle, enumerate_triangles, score_triangle_in_sample  # noqa: E402

RUN = REPO / "runs" / "triangular_pairs"
OOS = pd.Timestamp(OOS_START, tz="UTC")
ANN = 365
FEE = 0.00045
SLIPPAGE = 0.0005


def liquid_assets(close: pd.DataFrame, top_n: int = 80) -> list[str]:
    counts = close.notna().sum().sort_values(ascending=False)
    liquid = counts.head(top_n).index.tolist()
    for a in ANCHORS:
        if a in close.columns and a not in liquid:
            liquid.append(a)
    return liquid


def discover_triangles_is(
    close: pd.DataFrame,
    *,
    oos_start: pd.Timestamp = OOS,
    adf_max: float = 0.05,
    n_triangles: int = 10,
    window: int = 120,
    min_periods: int = 90,
    ranked_cache: pd.DataFrame | None = None,
) -> tuple[list[Triangle], pd.DataFrame]:
    """Rank triangles on pre-OOS data only. Reuse ranked_cache when sweeping params."""
    if ranked_cache is not None:
        ranked = ranked_cache[ranked_cache["adf_p"] < adf_max]
        triangles = [
            Triangle(target=r.target, leg1=r.leg1, leg2=r.leg2)
            for r in ranked.head(n_triangles).itertuples()
        ]
        return triangles, ranked_cache

    liquid = liquid_assets(close)
    log_panel = log_prices(close[liquid])
    candidates = enumerate_triangles(liquid, ANCHORS)
    rows = [
        score_triangle_in_sample(
            log_panel,
            tri,
            oos_start=oos_start,
            window=window,
            min_periods=min_periods,
        )
        for tri in candidates
    ]
    ranked = pd.DataFrame(rows).sort_values("score", ascending=False)
    ranked = ranked[ranked["adf_p"] < adf_max]
    triangles = [
        Triangle(target=r.target, leg1=r.leg1, leg2=r.leg2)
        for r in ranked.head(n_triangles).itertuples()
    ]
    return triangles, ranked


def run_backtest(
    close: pd.DataFrame,
    triangles: list[Triangle],
    *,
    window: int = 120,
    min_periods: int = 90,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
    weight_cap: float = 0.20,
    max_gross_exposure: float = 1.0,
) -> pd.Series:
    """Return daily strategy returns (research engine; 1-bar execution lag)."""
    assets = sorted({a for t in triangles for a in (t.target, t.leg1, t.leg2)})
    panel = close[[c for c in assets if c in close.columns]]
    result = backtest_triangles(
        panel,
        triangles,
        window=window,
        min_periods=min_periods,
        entry_z=entry_z,
        exit_z=exit_z,
        weight_cap=weight_cap,
        max_gross_exposure=max_gross_exposure,
    )
    return result.daily_returns


def is_metrics(returns: pd.Series, oos_start: pd.Timestamp = OOS) -> dict:
    """Metrics on in-sample segment only."""
    is_ret = returns.loc[returns.index < oos_start].dropna()
    m = compute_metrics(is_ret, oos_start)
    return {
        "Sharpe": m["Sharpe"],
        "CAGR": m["CAGR"],
        "MaxDD": m["MaxDD"],
        "n_days": m["n_days"],
        "vol_ann": m.get("vol_ann", np.nan),
    }


def full_metrics(returns: pd.Series, oos_start: pd.Timestamp = OOS) -> dict:
    m = compute_metrics(returns.dropna(), oos_start)
    return {
        "in_sample": m["in_sample"],
        "out_of_sample": m["out_of_sample"],
        "full": {
            "Sharpe": m["Sharpe"],
            "CAGR": m["CAGR"],
            "MaxDD": m["MaxDD"],
            "n_days": m["n_days"],
        },
    }


def yearly_sharpes(returns: pd.Series, oos_start: pd.Timestamp = OOS) -> dict[int, float]:
    """In-sample yearly Sharpe ratios."""
    is_ret = returns.loc[returns.index < oos_start].dropna()
    out: dict[int, float] = {}
    for year, grp in is_ret.groupby(is_ret.index.year):
        vol = grp.std()
        out[int(year)] = float(grp.mean() / vol * np.sqrt(ANN)) if vol > 0 else float("nan")
    return out


def robust_score(is_m: dict, yearly: dict[int, float]) -> float:
    """Rank configs by IS edge + subperiod stability (not OOS)."""
    sharpes = [v for v in yearly.values() if np.isfinite(v)]
    if not sharpes or is_m["n_days"] < 252:
        return float("-inf")
    min_y = min(sharpes)
    mean_y = float(np.mean(sharpes))
    std_y = float(np.std(sharpes))
    stability = mean_y - 0.5 * std_y  # penalize volatile years
    dd_penalty = 0.0 if is_m["MaxDD"] > -0.35 else (is_m["MaxDD"] + 0.35) * 2
    return is_m["Sharpe"] * 0.55 + stability * 0.30 + min_y * 0.15 + dd_penalty


def strategy_snapshot(params: dict, triangles: list[Triangle]) -> dict:
    return {
        "spec_version": 2,
        "workflow": "multi_asset_triangular_pairs",
        "execution_mode": "custom_engine",
        "symbol": "UNIVERSE",
        "oos_start_ts": str(OOS),
        "strategy_type": "MEAN_REVERSION",
        "params": params,
        "triangles": [t.key for t in triangles],
        "costs": {"fee": FEE, "slippage": SLIPPAGE, "cost_per_leg": COST_PER_LEG},
        "signal_lag_bars": 1,
    }


def save_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")
