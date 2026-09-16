"""Equity-only factor attribution vs Ken French factors (Newey–West HAC).

Not for strategy code. Fetch lives in this lab helper so runs/*/code stays offline.
Skip crypto/FX unless --force.
"""

from __future__ import annotations

import io
import math
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FILES = {
    ("ff3", "monthly"): "F-F_Research_Data_Factors_CSV.zip",
    ("ff5", "monthly"): "F-F_Research_Data_5_Factors_2x3_CSV.zip",
    ("mom", "monthly"): "F-F_Momentum_Factor_CSV.zip",
    ("ff3", "daily"): "F-F_Research_Data_Factors_daily_CSV.zip",
    ("ff5", "daily"): "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
    ("mom", "daily"): "F-F_Momentum_Factor_daily_CSV.zip",
}
MODELS = {
    "capm": ["Mkt-RF"],
    "ff3": ["Mkt-RF", "SMB", "HML"],
    "carhart4": ["Mkt-RF", "SMB", "HML", "Mom"],
    "ff5": ["Mkt-RF", "SMB", "HML", "RMW", "CMA"],
    "ff5+mom": ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"],
}

EQUITY_ASSET_CLASSES = {"equity", "etf", "stock", "index"}


def auto_lags(n: int) -> int:
    return int(np.floor(4.0 * (n / 100.0) ** (2.0 / 9.0)))


def _norm_sf(x: np.ndarray) -> np.ndarray:
    from math import erfc, sqrt

    flat = np.atleast_1d(np.asarray(x, dtype=float))
    out = np.array([0.5 * erfc(v / sqrt(2.0)) if np.isfinite(v) else np.nan for v in flat])
    return out.reshape(np.shape(x)) if np.shape(x) else out[0]


def ols_hac(y: np.ndarray, x: np.ndarray, lags: int | None = None) -> dict[str, Any]:
    y = np.asarray(y, dtype=float).ravel()
    x = np.asarray(x, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    n, k = x.shape
    if n <= k:
        raise ValueError(f"need more observations than regressors (n={n}, k={k})")
    if lags is None:
        lags = auto_lags(n)
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    xtx_inv = np.linalg.inv(x.T @ x)
    h = x * resid[:, None]
    s = h.T @ h
    for lag in range(1, lags + 1):
        w = 1.0 - lag / (lags + 1.0)
        g = h[lag:].T @ h[:-lag]
        s += w * (g + g.T)
    cov = xtx_inv @ s @ xtx_inv
    se = np.sqrt(np.maximum(np.diag(cov), 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(se > 0, beta / se, np.nan)
    tss = float(((y - y.mean()) ** 2).sum())
    rss = float((resid**2).sum())
    r2 = 1.0 - rss / tss if tss > 0 else float("nan")
    return {"beta": beta, "se": se, "t": t, "p": 2.0 * _norm_sf(np.abs(t)),
            "resid": resid, "r2": r2, "n": n, "lags": lags}


def _cache_dir(repo_root: Path) -> Path:
    d = repo_root / "data" / "ken_french"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _download(name: str, cache: Path) -> bytes:
    cached = cache / name
    if cached.exists() and cached.stat().st_size > 0:
        return cached.read_bytes()
    import urllib.request

    with urllib.request.urlopen(BASE + name, timeout=60) as resp:
        blob = resp.read()
    cached.write_bytes(blob)
    return blob


def _parse(blob: bytes, freq: str) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        raw = zf.read(zf.namelist()[0]).decode("latin-1")
    rows, header = [], None
    width = 8 if freq == "daily" else 6
    for line in raw.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        key = parts[0]
        if not (key.isdigit() and len(key) == width):
            if header is None and key == "" and any(parts[1:]):
                header = [p for p in parts[1:] if p]
            continue
        try:
            vals = [float(p) for p in parts[1:] if p != ""]
        except ValueError:
            continue
        rows.append([key] + vals)
    if not rows or header is None:
        raise ValueError("could not parse Ken French CSV layout")
    ncol = min(len(header), min(len(r) - 1 for r in rows))
    df = pd.DataFrame([r[: ncol + 1] for r in rows], columns=["date"] + header[:ncol])
    fmt = "%Y%m%d" if freq == "daily" else "%Y%m"
    df["date"] = pd.to_datetime(df["date"], format=fmt)
    for c in df.columns[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce") / 100.0
    return df.set_index("date").sort_index()


def load_factors(model: str, freq: str, cache: Path) -> pd.DataFrame:
    model = model.lower()
    if model not in MODELS:
        raise ValueError(f"model must be one of {sorted(MODELS)}")
    wanted = MODELS[model]
    base_key = "ff5" if model.startswith("ff5") else "ff3"
    df = _parse(_download(FILES[(base_key, freq)], cache), freq)
    if "Mom" in wanted:
        mom = _parse(_download(FILES[("mom", freq)], cache), freq)
        mom.columns = ["Mom"] + list(mom.columns[1:])
        df = df.join(mom[["Mom"]], how="inner")
    keep = [c for c in wanted + ["RF"] if c in df.columns]
    return df[keep].dropna(how="any")


def attribute(
    rets: pd.Series,
    *,
    model: str,
    freq: str,
    cache: Path,
    excess: bool = False,
) -> dict[str, Any]:
    fac = load_factors(model, freq, cache)
    if freq == "monthly":
        idx = rets.index.to_period("M").to_timestamp()
        fac = fac.copy()
        fac.index = fac.index.to_period("M").to_timestamp()
    else:
        idx = rets.index
    aligned = pd.DataFrame({"ret": rets.to_numpy()}, index=idx).join(fac, how="inner").dropna()
    if len(aligned) < 24:
        raise ValueError(f"only {len(aligned)} overlapping periods with factor data")
    rf = aligned["RF"].to_numpy() if ("RF" in aligned.columns and not excess) else 0.0
    y = aligned["ret"].to_numpy() - rf
    names = MODELS[model.lower()]
    x = np.column_stack([np.ones(len(aligned))] + [aligned[c].to_numpy() for c in names])
    fit = ols_hac(y, x)
    ppy = 12 if freq == "monthly" else 252
    loadings = {
        n: {"beta": float(fit["beta"][i + 1]), "t": float(fit["t"][i + 1])}
        for i, n in enumerate(names)
    }
    return {
        "model": model,
        "n": int(fit["n"]),
        "lags": int(fit["lags"]),
        "r2": float(fit["r2"]),
        "alpha_ann": float(fit["beta"][0] * ppy),
        "alpha_t": float(fit["t"][0]),
        "alpha_p": float(fit["p"][0]),
        "loadings": loadings,
        "start": str(aligned.index[0].date()),
        "end": str(aligned.index[-1].date()),
        "resid_vol_ann": float(np.std(fit["resid"], ddof=1) * math.sqrt(ppy)),
    }


def asset_class_allows(asset_class: str | None, force: bool) -> bool:
    if force:
        return True
    ac = str(asset_class or "").lower()
    return ac in EQUITY_ASSET_CLASSES
