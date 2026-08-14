"""Triangle discovery and residual modeling."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.regression.rolling import RollingOLS
from statsmodels.tsa.stattools import adfuller


@dataclass(frozen=True)
class Triangle:
    """Three USDT perp symbols: target vs two hedge legs."""

    target: str
    leg1: str
    leg2: str

    @property
    def key(self) -> str:
        return f"{self.target}|{self.leg1}|{self.leg2}"


def enumerate_triangles(
    assets: list[str],
    anchors: tuple[str, ...],
    *,
    max_triangles: int | None = None,
) -> list[Triangle]:
    """Build triangles: target alt hedged with two anchors/legs."""
    anchor_set = set(anchors)
    alts = [a for a in assets if a not in anchor_set and a.endswith("USDT")]
    legs = [a for a in assets if a in anchor_set]

    triangles: list[Triangle] = []
    for target in alts:
        for leg1, leg2 in combinations(legs, 2):
            triangles.append(Triangle(target=target, leg1=leg1, leg2=leg2))
            if max_triangles and len(triangles) >= max_triangles:
                return triangles
    return triangles


def rolling_triangle_residual(
    log_close: pd.DataFrame,
    triangle: Triangle,
    *,
    window: int,
    min_periods: int | None = None,
) -> pd.DataFrame:
    """Rolling OLS: log(target) ~ log(leg1) + log(leg2). Returns residual z-score."""
    if min_periods is None:
        min_periods = window

    cols = [triangle.target, triangle.leg1, triangle.leg2]
    frame = log_close[cols].dropna(how="any")
    if frame.empty:
        idx = log_close.index
        empty = pd.DataFrame(
            {"residual": np.nan, "beta1": np.nan, "beta2": np.nan, "zscore": np.nan},
            index=idx,
        )
        return empty

    y = frame[triangle.target]
    x = sm.add_constant(frame[[triangle.leg1, triangle.leg2]])
    model = RollingOLS(y, x, window=window, min_nobs=min_periods)
    fit = model.fit()
    params = fit.params.reindex(log_close.index)

    fitted = (
        params["const"]
        + params[triangle.leg1] * frame[triangle.leg1].reindex(log_close.index)
        + params[triangle.leg2] * frame[triangle.leg2].reindex(log_close.index)
    )
    resid = (y.reindex(log_close.index) - fitted).rename("residual")
    beta1 = params[triangle.leg1]
    beta2 = params[triangle.leg2]

    roll_mean = resid.rolling(window, min_periods=min_periods).mean()
    roll_std = resid.rolling(window, min_periods=min_periods).std()
    zscore = (resid - roll_mean) / roll_std.replace(0, np.nan)

    return pd.DataFrame(
        {"residual": resid, "beta1": beta1, "beta2": beta2, "zscore": zscore},
        index=log_close.index,
    )


def adf_pvalue(series: pd.Series) -> float:
    clean = series.dropna()
    if len(clean) < 60:
        return 1.0
    try:
        return float(adfuller(clean, autolag="AIC")[1])
    except Exception:
        return 1.0


def score_triangle_in_sample(
    log_close: pd.DataFrame,
    triangle: Triangle,
    *,
    oos_start: pd.Timestamp,
    window: int = 120,
    min_periods: int = 90,
    half_life_cap: float = 60.0,
    half_life_norm: float = 120.0,
) -> dict:
    """Rank triangles by residual stationarity and half-life on pre-OOS data."""
    is_idx = log_close.index[log_close.index < oos_start]
    panel_is = log_close.loc[is_idx, [triangle.target, triangle.leg1, triangle.leg2]].dropna(how="any")
    if len(panel_is) < min_periods + 30:
        return {
            "triangle": triangle.key,
            "target": triangle.target,
            "leg1": triangle.leg1,
            "leg2": triangle.leg2,
            "score": -np.inf,
            "adf_p": 1.0,
            "half_life": np.inf,
            "resid_std": 0.0,
            "n": 0,
        }

    stats = rolling_triangle_residual(panel_is, triangle, window=window, min_periods=min_periods)
    resid = stats["residual"].dropna()
    if len(resid) < 60:
        return {
            "triangle": triangle.key,
            "target": triangle.target,
            "leg1": triangle.leg1,
            "leg2": triangle.leg2,
            "score": -np.inf,
            "adf_p": 1.0,
            "half_life": np.inf,
            "n": len(resid),
        }

    adf_p = adf_pvalue(resid)
    r_lag = resid.shift(1)
    valid = pd.concat([resid, r_lag], axis=1).dropna()
    if len(valid) < 30:
        half_life = np.inf
    else:
        y = valid.iloc[:, 0].to_numpy()
        x = valid.iloc[:, 1].to_numpy()
        phi = np.linalg.lstsq(x.reshape(-1, 1), y, rcond=None)[0][0]
        if 0 < phi < 1:
            half_life = -np.log(2) / np.log(phi)
        else:
            half_life = np.inf

    resid_std = float(resid.std()) if len(resid) > 1 else 0.0
    score = -adf_p - min(half_life, half_life_cap) / half_life_norm
    return {
        "triangle": triangle.key,
        "target": triangle.target,
        "leg1": triangle.leg1,
        "leg2": triangle.leg2,
        "score": score,
        "adf_p": adf_p,
        "half_life": half_life,
        "resid_std": resid_std,
        "n": len(resid),
    }
