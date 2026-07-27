#!/usr/bin/env python3
"""Fetch Binance daily klines for USDT spot and USDT-M perpetual futures.

Writes long-format parquet files under data/binance/:
  - binance_futures_ohlcv_1d.parquet  (USDT-M perpetuals)
  - binance_spot_ohlcv_1d.parquet     (USDT spot)

Public endpoints only — no API key required.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
DATA_DIR = _REPO / "data" / "binance"

Market = Literal["futures", "spot"]

FUTURES_BASE = "https://fapi.binance.com"
SPOT_BASE = "https://api.binance.com"

OUTPUT_PATHS: dict[Market, Path] = {
    "futures": DATA_DIR / "binance_futures_ohlcv_1d.parquet",
    "spot": DATA_DIR / "binance_spot_ohlcv_1d.parquet",
}

KLINE_COLUMNS = [
    "open_time_ms",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time_ms",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "ignore",
]

OHLCV_SCHEMA = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_asset_volume",
    "number_of_trades",
    "asset",
    "time",
]


@dataclass(frozen=True)
class MarketConfig:
    name: Market
    base_url: str
    exchange_info_path: str
    klines_path: str


MARKETS: dict[Market, MarketConfig] = {
    "futures": MarketConfig(
        name="futures",
        base_url=FUTURES_BASE,
        exchange_info_path="/fapi/v1/exchangeInfo",
        klines_path="/fapi/v1/klines",
    ),
    "spot": MarketConfig(
        name="spot",
        base_url=SPOT_BASE,
        exchange_info_path="/api/v3/exchangeInfo",
        klines_path="/api/v3/klines",
    ),
}

# Binance kline API max `limit` per request (spot=1000, USDT-M futures=1500).
KLINE_PAGE_LIMIT: dict[Market, int] = {"futures": 1500, "spot": 1000}


def _utc_ms(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Binance daily OHLCV klines to parquet.")
    parser.add_argument(
        "--market",
        choices=("futures", "spot", "both"),
        default="both",
        help="Which market(s) to fetch (default: both).",
    )
    parser.add_argument(
        "--start",
        default="2020-01-01",
        help="History start date (UTC, YYYY-MM-DD). Ignored per-symbol when incremental data exists.",
    )
    parser.add_argument(
        "--symbols",
        nargs="*",
        help="Optional explicit symbol list (e.g. BTCUSDT ETHUSDT). Default: full exchange universe.",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=None,
        help="Cap symbol count (useful for smoke tests).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.12,
        help="Seconds to sleep between kline requests (rate-limit cushion).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=5,
        help="HTTP retries on transient errors / 429.",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Ignore existing parquet and refetch full history for each symbol.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List symbols and planned fetches without writing parquet.",
    )
    return parser.parse_args()


def _request_json(client: httpx.Client, url: str, *, params: dict[str, Any], retries: int) -> Any:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = client.get(url, params=params)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 2 ** attempt))
                time.sleep(retry_after)
                continue
            if resp.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"request failed after {retries} attempts: {url} params={params}") from last_err


def list_symbols(client: httpx.Client, market: Market, *, retries: int) -> list[str]:
    cfg = MARKETS[market]
    url = f"{cfg.base_url}{cfg.exchange_info_path}"
    payload = _request_json(client, url, params={}, retries=retries)

    symbols: list[str] = []
    for item in payload.get("symbols", []):
        if item.get("status") != "TRADING":
            continue
        if item.get("quoteAsset") != "USDT":
            continue
        if market == "futures":
            if item.get("contractType") != "PERPETUAL":
                continue
        else:
            permissions = set(item.get("permissions") or [])
            if permissions and "SPOT" not in permissions:
                continue
        symbols.append(str(item["symbol"]).upper())

    return sorted(set(symbols))


def _klines_to_frame(symbol: str, rows: list[list[Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=OHLCV_SCHEMA)

    df = pd.DataFrame(rows, columns=KLINE_COLUMNS)
    out = pd.DataFrame(
        {
            "open": pd.to_numeric(df["open"], errors="coerce"),
            "high": pd.to_numeric(df["high"], errors="coerce"),
            "low": pd.to_numeric(df["low"], errors="coerce"),
            "close": pd.to_numeric(df["close"], errors="coerce"),
            "volume": pd.to_numeric(df["volume"], errors="coerce"),
            "quote_asset_volume": pd.to_numeric(df["quote_asset_volume"], errors="coerce"),
            "number_of_trades": pd.to_numeric(df["number_of_trades"], errors="coerce").astype("Int64"),
            "asset": symbol,
            "time": pd.to_datetime(df["open_time_ms"], unit="ms", utc=True),
        }
    )
    return out[OHLCV_SCHEMA]


def fetch_symbol_klines(
    client: httpx.Client,
    market: Market,
    symbol: str,
    *,
    start_ms: int,
    end_ms: int | None,
    retries: int,
    sleep_s: float,
) -> pd.DataFrame:
    cfg = MARKETS[market]
    url = f"{cfg.base_url}{cfg.klines_path}"
    page_limit = KLINE_PAGE_LIMIT[market]
    all_rows: list[list[Any]] = []
    cursor = start_ms

    while True:
        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": "1d",
            "startTime": cursor,
            "limit": page_limit,
        }
        if end_ms is not None:
            params["endTime"] = end_ms

        batch = _request_json(client, url, params=params, retries=retries)
        if not batch:
            break

        all_rows.extend(batch)
        last_open = int(batch[-1][0])
        next_cursor = last_open + 86_400_000  # next UTC day
        if len(batch) < page_limit:
            break
        if end_ms is not None and next_cursor > end_ms:
            break
        cursor = next_cursor
        time.sleep(sleep_s)

    frame = _klines_to_frame(symbol, all_rows)
    if not frame.empty:
        frame = frame.drop_duplicates(subset=["asset", "time"], keep="last")
    return frame


def load_existing(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df["asset"] = df["asset"].astype(str).str.upper()
    return df


def symbol_start_ms(
    existing: pd.DataFrame | None,
    symbol: str,
    default_start_ms: int,
    *,
    full_refresh: bool,
) -> int:
    if full_refresh or existing is None or existing.empty:
        return default_start_ms
    sub = existing.loc[existing["asset"] == symbol]
    if sub.empty:
        return default_start_ms
    last_ts = sub["time"].max()
    # Refetch from last bar to refresh partial / updated candle, then dedupe.
    return int(last_ts.timestamp() * 1000)


def merge_frames(existing: pd.DataFrame | None, new_rows: list[pd.DataFrame]) -> pd.DataFrame:
    parts = [df for df in ([existing] if existing is not None else []) + new_rows if df is not None and not df.empty]
    if not parts:
        return pd.DataFrame(columns=OHLCV_SCHEMA)

    out = pd.concat(parts, ignore_index=True)
    out["asset"] = out["asset"].astype(str).str.upper()
    out["time"] = pd.to_datetime(out["time"], utc=True)
    out = out.drop_duplicates(subset=["asset", "time"], keep="last")
    out = out.sort_values(["asset", "time"]).reset_index(drop=True)
    out["number_of_trades"] = out["number_of_trades"].astype("int64")
    return out[OHLCV_SCHEMA]


def write_manifest(path: Path, meta: dict[str, Any]) -> None:
    manifest = path.with_suffix(".manifest.json")
    manifest.write_text(json.dumps(meta, indent=2, default=str) + "\n")


def run_market(
    market: Market,
    *,
    symbols: list[str] | None,
    start_date: str,
    max_symbols: int | None,
    sleep_s: float,
    retries: int,
    full_refresh: bool,
    dry_run: bool,
) -> dict[str, Any]:
    out_path = OUTPUT_PATHS[market]
    default_start_ms = _utc_ms(datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc))
    end_ms = _utc_ms(datetime.now(timezone.utc))

    existing = None if full_refresh else load_existing(out_path)

    with httpx.Client(timeout=30.0) as client:
        universe = symbols or list_symbols(client, market, retries=retries)
        if max_symbols is not None:
            universe = universe[:max_symbols]

        print(f"\n[{market}] symbols={len(universe)} output={out_path}")
        if dry_run:
            preview = universe[:10]
            print(f"  preview: {preview}{' ...' if len(universe) > 10 else ''}")
            return {
                "market": market,
                "symbols": len(universe),
                "output": str(out_path),
                "dry_run": True,
            }

        fetched: list[pd.DataFrame] = []
        skipped = 0
        for i, symbol in enumerate(universe, start=1):
            start_ms = symbol_start_ms(existing, symbol, default_start_ms, full_refresh=full_refresh)
            if start_ms > end_ms:
                skipped += 1
                continue

            print(f"  [{i}/{len(universe)}] {symbol} from {pd.to_datetime(start_ms, unit='ms', utc=True).date()}", flush=True)
            frame = fetch_symbol_klines(
                client,
                market,
                symbol,
                start_ms=start_ms,
                end_ms=end_ms,
                retries=retries,
                sleep_s=sleep_s,
            )
            if not frame.empty:
                fetched.append(frame)
            time.sleep(sleep_s)

    merged = merge_frames(existing, fetched)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(out_path, index=False)

    meta = {
        "market": market,
        "symbols_requested": len(universe),
        "symbols_skipped_up_to_date": skipped,
        "rows": int(len(merged)),
        "assets": int(merged["asset"].nunique()) if not merged.empty else 0,
        "start": str(merged["time"].min()) if not merged.empty else None,
        "end": str(merged["time"].max()) if not merged.empty else None,
        "output": str(out_path),
        "full_refresh": full_refresh,
        "history_start_default": start_date,
    }
    write_manifest(out_path, meta)
    print(f"  wrote {out_path} rows={meta['rows']} assets={meta['assets']}")
    return meta


def main() -> int:
    args = _parse_args()
    markets: list[Market]
    if args.market == "both":
        markets = ["futures", "spot"]
    else:
        markets = [args.market]  # type: ignore[list-item]

    summary: list[dict[str, Any]] = []
    for market in markets:
        try:
            summary.append(
                run_market(
                    market,
                    symbols=[s.upper() for s in args.symbols] if args.symbols else None,
                    start_date=args.start,
                    max_symbols=args.max_symbols,
                    sleep_s=args.sleep,
                    retries=args.retries,
                    full_refresh=args.full_refresh,
                    dry_run=args.dry_run,
                )
            )
        except Exception as exc:
            print(f"[{market}] ERROR: {exc}", file=sys.stderr)
            return 1

    if not args.dry_run:
        print("\nDone.")
        for item in summary:
            print(f"  {item['market']}: {item['rows']} rows, {item['assets']} assets -> {item['output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
