"""Asset-class-agnostic OHLCV loaders for the Cursor Lab wrapper."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .alpha_ops import OPERATORS

OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")

YF_SYMBOL_MAP = {
    "BTCUSDT": "BTC-USD",
    "ETHUSDT": "ETH-USD",
    "SOLUSDT": "SOL-USD",
    "BNBUSDT": "BNB-USD",
    "DAX": "^GDAXI",
    "GDAXI": "^GDAXI",
}

_EQUITY_LOCAL_MIN_BARS = 50


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "time" in out.columns:
        out["time"] = pd.to_datetime(out["time"], utc=True)
        out = out.set_index("time")
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index, utc=True)
    if out.index.tz is None:
        out.index = out.index.tz_localize("UTC")
    else:
        out.index = out.index.tz_convert("UTC")
    out.columns = [str(c).lower() for c in out.columns]
    missing = [c for c in OHLCV_COLUMNS if c not in out.columns]
    if missing:
        raise ValueError(f"OHLCV frame missing columns: {missing}")
    return out.sort_index()


def _is_crypto_market_symbol(symbol: str) -> bool:
    sym = str(symbol or "").upper()
    return sym.endswith("USDT") or (sym.endswith("USD") and sym != "USD")


def _is_equity_market_symbol(symbol: str) -> bool:
    sym = str(symbol or "").upper()
    if not sym or _is_crypto_market_symbol(sym):
        return False
    return bool(re.fullmatch(r"[A-Z]{1,5}", sym))


def _asset_match_variants(symbol: str) -> set[str]:
    sym_u = symbol.upper()
    sym_l = symbol.lower()
    variants = {sym_u, sym_l}
    if _is_crypto_market_symbol(sym_u) and sym_u.endswith("USDT"):
        base = sym_u[:-4]
        if base:
            variants.update({base, base.lower()})
    return variants


def _load_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _glob_market_candidates(symbol: str, data_dir: Path) -> list[Path]:
    symbol_u = symbol.upper()
    symbol_l = symbol.lower()
    base_l = symbol_l[:-4] if symbol_l.endswith("usdt") else symbol_l
    paths: list[Path] = []
    for path in sorted([*data_dir.glob("**/*.csv"), *data_dir.glob("**/*.parquet")]):
        stem_u = path.stem.upper()
        stem_l = path.stem.lower()
        if symbol_u in stem_u or symbol_l in stem_l:
            paths.append(path)
        elif not _is_equity_market_symbol(symbol_u) and base_l and base_l in stem_l:
            paths.append(path)
    return paths


def _local_symbol_data(symbol: str, data_dir: Path, interval: str = "1d") -> tuple[pd.DataFrame | None, str | None]:
    symbol_variants = _asset_match_variants(symbol)
    for path in _glob_market_candidates(symbol, data_dir):
        if not path.exists():
            continue
        try:
            df = _load_file(path)
            cols_lower = {str(c).lower(): c for c in df.columns}
            if "asset" in cols_lower or "symbol" in cols_lower:
                asset_col = cols_lower.get("asset") or cols_lower["symbol"]
                matched = df[df[asset_col].astype(str).str.upper().isin({v.upper() for v in symbol_variants})]
                if matched.empty:
                    continue
                df = matched
            if "interval" in cols_lower and interval:
                interval_col = cols_lower["interval"]
                df = df.loc[df[interval_col].astype(str) == interval]
            if {"open", "high", "low", "close"}.issubset(cols_lower) and not df.empty:
                return _normalize_ohlcv(df), str(path)
        except Exception:
            continue
    return None, None


def _yfinance_symbol(symbol: str) -> str:
    return YF_SYMBOL_MAP.get(symbol.upper(), symbol)


def default_annualization(symbol: str, *, asset_class: str | None = None) -> int:
    """Return a sensible default annualization factor for daily bars."""
    if asset_class:
        lowered = asset_class.lower()
        if lowered in {"equity", "equities", "bond", "bonds", "rates"}:
            return 252
        if lowered in {"crypto", "fx", "forex", "metal", "metals", "commodity", "commodities"}:
            return 365
    if _is_equity_market_symbol(symbol):
        return 252
    return 365


def load_symbol_from_parquet(
    path: Path | str,
    symbol: str,
    *,
    interval: str | None = None,
) -> pd.DataFrame:
    """Load one symbol from a long-format parquet file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    df = pd.read_parquet(p)
    if "asset" in df.columns:
        mask = df["asset"].astype(str).str.upper() == symbol.upper()
        df = df.loc[mask]
    elif "symbol" in df.columns:
        mask = df["symbol"].astype(str).str.upper() == symbol.upper()
        df = df.loc[mask]
    else:
        raise ValueError(f"{p} has no asset/symbol column for filtering")
    if interval and "interval" in df.columns:
        df = df.loc[df["interval"].astype(str) == interval]
    if df.empty:
        raise ValueError(f"No rows for {symbol} in {p}")
    return _normalize_ohlcv(df)


def load_symbol_close(
    path: Path | str,
    symbol: str,
    *,
    interval: str | None = "1d",
) -> pd.Series:
    frame = load_symbol_from_parquet(path, symbol, interval=interval)
    return frame["close"].astype(float)


def load_market_data(
    symbol: str,
    data_dir: str | Path = "./data",
    start: str | None = None,
    end: str | None = None,
    interval: str = "1d",
    prefer_local: bool = True,
) -> tuple[pd.DataFrame, str]:
    """Load OHLCV data for any supported asset class.

    Lookup order when prefer_local=True:
    1. Recursive search under data_dir for matching parquet/CSV
    2. yfinance fallback (public market data only — never upload client files)
    """
    data_dir = Path(data_dir)

    if prefer_local:
        local_df, local_path = _local_symbol_data(symbol, data_dir, interval=interval)
        if local_df is not None:
            if _is_equity_market_symbol(symbol) and len(local_df) < _EQUITY_LOCAL_MIN_BARS:
                local_df, local_path = None, None
            else:
                return local_df, f"local:{local_path}"

    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError(
            f"Symbol {symbol} was not found under {data_dir} and yfinance is not installed."
        ) from exc

    yf_symbol = _yfinance_symbol(symbol)
    interval_period_map = {
        "1m": "7d",
        "2m": "60d",
        "5m": "60d",
        "15m": "60d",
        "30m": "60d",
        "60m": "730d",
        "90m": "60d",
        "1h": "730d",
        "1d": "max",
        "5d": "max",
        "1wk": "max",
        "1mo": "max",
        "3mo": "max",
    }
    if interval not in interval_period_map:
        raise ValueError(
            f"Unsupported yfinance interval '{interval}'. Supported: {sorted(interval_period_map)}"
        )

    download_kwargs: dict = {
        "tickers": yf_symbol,
        "interval": interval,
        "auto_adjust": True,
        "progress": False,
        "multi_level_index": False,
    }
    if start is not None or end is not None:
        download_kwargs["start"] = start
        download_kwargs["end"] = end
    else:
        download_kwargs["period"] = interval_period_map[interval]

    yf_df = yf.download(**download_kwargs)
    if yf_df is None or yf_df.empty:
        local_msg = " after checking local data" if prefer_local else ""
        raise ValueError(
            f"No data found for {symbol}{local_msg}; yfinance returned no data for {yf_symbol}."
        )
    return _normalize_ohlcv(yf_df), f"yfinance:{yf_symbol}"


def _long_asset_column(df: pd.DataFrame) -> str | None:
    cols = {str(c).lower(): c for c in df.columns}
    for name in ("asset", "symbol", "ticker"):
        if name in cols:
            return cols[name]
    return None


def _ensure_time_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    cols = {str(c).lower(): c for c in out.columns}
    if "time" in cols and not isinstance(out.index, pd.DatetimeIndex):
        out["time"] = pd.to_datetime(out[cols["time"]], utc=True)
        out = out.set_index("time")
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index, utc=True)
    if out.index.tz is None:
        out.index = out.index.tz_localize("UTC")
    else:
        out.index = out.index.tz_convert("UTC")
    out.columns = [str(c).lower() for c in out.columns]
    return out.sort_index()


def _reserved_panel_names() -> set[str]:
    return set(OHLCV_COLUMNS) | set(OPERATORS) | {
        "time",
        "date",
        "interval",
        "asset",
        "symbol",
        "ticker",
        "_asset",
    }


def _pivot_numeric_field(timed: pd.DataFrame, field: str) -> pd.DataFrame:
    wide = timed.pivot_table(index=timed.index, columns="_asset", values=field, aggfunc="last")
    return wide.sort_index().sort_index(axis=1).astype(float)


def load_ohlcv_panel(
    path: Path | str,
    *,
    interval: str | None = None,
    min_bars: int = 60,
    top_n: int | None = None,
    liquidity_end: str | pd.Timestamp | None = None,
) -> dict[str, pd.DataFrame]:
    """Load a long-format OHLCV file into field panels (index=time, columns=asset).

    ``top_n`` keeps the most liquid names by median dollar volume on dates
    strictly before ``liquidity_end`` (the OOS start, when provided).

    Extra numeric columns (Python identifiers that are not operators or OHLCV
    fields) are pivoted as additional operands so formulaic mining can use
    joined panels (funding, OI, on-chain metrics, …).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    raw = _load_file(p)
    asset_col = _long_asset_column(raw)
    if asset_col is None:
        raise ValueError(f"{p} has no asset/symbol column — need a universe panel, not a single name")
    cols = {str(c).lower(): c for c in raw.columns}
    if interval and "interval" in cols:
        raw = raw.loc[raw[cols["interval"]].astype(str) == str(interval)]
    raw = raw.copy()
    raw["_asset"] = raw[asset_col].astype(str).str.upper()
    timed = _ensure_time_index(raw)
    missing = [c for c in OHLCV_COLUMNS if c not in timed.columns]
    if missing:
        raise ValueError(f"{p} missing OHLCV columns: {missing}")

    fields: dict[str, pd.DataFrame] = {}
    for field in OHLCV_COLUMNS:
        fields[field] = _pivot_numeric_field(timed, field)

    reserved = _reserved_panel_names()
    for col in list(timed.columns):
        name = str(col)
        if name in reserved or not name.isidentifier() or name.startswith("_"):
            continue
        timed[name] = pd.to_numeric(timed[name], errors="coerce")
        if int(timed[name].notna().sum()) < 3:
            continue
        fields[name] = _pivot_numeric_field(timed, name)

    close = fields["close"]
    counts = close.notna().sum(axis=0)
    keep = [c for c in close.columns if int(counts.get(c, 0)) >= int(min_bars)]
    if len(keep) < 3:
        raise ValueError(
            f"Panel too small after min_bars={min_bars}: {len(keep)} names in {p}"
        )
    for key in list(fields):
        fields[key] = fields[key].reindex(columns=keep)

    if top_n is not None and int(top_n) > 0:
        dv = fields["close"] * fields["volume"]
        if liquidity_end is not None:
            ts = pd.Timestamp(liquidity_end)
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            else:
                ts = ts.tz_convert("UTC")
            dv = dv.loc[dv.index < ts]
        med = dv.median(axis=0, skipna=True).sort_values(ascending=False)
        liquid = [c for c in med.index if pd.notna(med[c])][: int(top_n)]
        if len(liquid) < 2:
            raise ValueError(f"top_n={top_n} left fewer than 2 names in {p}")
        for key in list(fields):
            fields[key] = fields[key].reindex(columns=liquid)

    return fields

