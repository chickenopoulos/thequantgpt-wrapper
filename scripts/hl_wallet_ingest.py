#!/usr/bin/env python3
"""Pull Hyperliquid wallet tapes into local parquet (not strategy code).

Lab strategy scripts cannot call the network. Run this first, then rank with
``scripts/tqg_wallet_sharpe.py`` or a run under ``runs/<id>/code/``.

Example:

    python scripts/hl_wallet_ingest.py \\
        --out data/hyperliquid/wallets \\
        --n-wallets 20 --coin BTC --sleep 0.2
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.wallet_sharpe import (  # noqa: E402
    fills_coin_pnl,
    funding_coin_pnl,
    history_pairs_to_series,
    ledger_to_cashflow,
    normalize_coin,
    portfolio_window,
)

INFO_URL = "https://api.hyperliquid.xyz/info"
LEADERBOARD_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
UA = "thequantgpt-lab-wallet-ingest/1.0"


def _get_json(url: str, timeout: float = 30.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _post_info(payload: dict[str, Any], timeout: float = 30.0) -> Any:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        INFO_URL,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": UA},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _window_roi(row: dict[str, Any], window: str) -> dict[str, float]:
    out = {"pnl": 0.0, "roi": 0.0, "vlm": 0.0}
    for item in row.get("windowPerformances") or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2 and item[0] == window:
            perf = item[1] or {}
            out = {
                "pnl": float(perf.get("pnl") or 0.0),
                "roi": float(perf.get("roi") or 0.0),
                "vlm": float(perf.get("vlm") or 0.0),
            }
    return out


def pick_leaderboard_wallets(
    rows: list[dict[str, Any]],
    *,
    n: int,
    min_account_value: float,
    max_account_value: float,
    min_month_vlm: float,
) -> pd.DataFrame:
    recs: list[dict[str, Any]] = []
    for row in rows:
        av = float(row.get("accountValue") or 0.0)
        if av < min_account_value or av > max_account_value:
            continue
        month = _window_roi(row, "month")
        if month["vlm"] < min_month_vlm:
            continue
        all_time = _window_roi(row, "allTime")
        recs.append(
            {
                "wallet": str(row.get("ethAddress") or "").lower(),
                "display_name": row.get("displayName"),
                "account_value": av,
                "roi_month": month["roi"],
                "pnl_month": month["pnl"],
                "vlm_month": month["vlm"],
                "roi_all": all_time["roi"],
                "pnl_all": all_time["pnl"],
                "vlm_all": all_time["vlm"],
            }
        )
    frame = pd.DataFrame(recs)
    if frame.empty:
        return frame
    frame = frame.drop_duplicates("wallet")
    # Prefer active mid-size accounts over the handful of inverted-basis desks.
    frame = frame.sort_values("vlm_month", ascending=False).head(int(n))
    return frame.reset_index(drop=True)


def ingest_wallet(addr: str, coin: str) -> dict[str, Any]:
    portfolio = _post_info({"type": "portfolio", "user": addr})
    ledger = _post_info({"type": "userNonFundingLedgerUpdates", "user": addr})
    fills = _post_info({"type": "userFills", "user": addr, "aggregateByTime": True})
    funding = _post_info({"type": "userFunding", "user": addr})
    windows: dict[str, pd.Series] = {}
    for window in ("perpAllTime", "perpMonth", "allTime", "month"):
        blob = portfolio_window(portfolio, window)
        windows[window] = history_pairs_to_series(blob.get("accountValueHistory") or [], name=window)
    cf = ledger_to_cashflow(ledger if isinstance(ledger, list) else [], addr)
    coin_pnl = fills_coin_pnl(fills if isinstance(fills, list) else [], coin)
    fund_pnl = funding_coin_pnl(funding if isinstance(funding, list) else [], coin)
    fill_coins: dict[str, int] = {}
    if isinstance(fills, list):
        for fill in fills:
            c = str((fill or {}).get("coin") or "")
            fill_coins[c] = fill_coins.get(c, 0) + 1
    return {
        "windows": windows,
        "cashflow": cf,
        "coin_pnl": (
            coin_pnl.add(fund_pnl, fill_value=0.0)
            if not coin_pnl.empty or not fund_pnl.empty
            else pd.Series(dtype=float)
        ),
        "n_fills": int(len(fills) if isinstance(fills, list) else 0),
        "n_ledger": int(len(ledger) if isinstance(ledger, list) else 0),
        "fill_coins": fill_coins,
        "traded_coin": any(normalize_coin(c) == normalize_coin(coin) for c in fill_coins),
    }


def _series_frame(wallet: str, series: pd.Series, kind: str) -> pd.DataFrame:
    if series is None or series.empty:
        return pd.DataFrame(columns=["time", "wallet", "kind", "value"])
    s = series.astype(float).sort_index()
    return pd.DataFrame(
        {
            "time": s.index,
            "wallet": wallet,
            "kind": kind,
            "value": s.to_numpy(),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest Hyperliquid wallet NAV/ledger/fills to parquet")
    parser.add_argument("--out", type=Path, required=True, help="Output directory")
    parser.add_argument("--n-wallets", type=int, default=20)
    parser.add_argument("--coin", default="BTC")
    parser.add_argument("--sleep", type=float, default=0.2, help="Seconds between info calls (per wallet burst)")
    parser.add_argument("--min-account-value", type=float, default=20_000.0)
    parser.add_argument("--max-account-value", type=float, default=2_000_000.0)
    parser.add_argument("--min-month-vlm", type=float, default=1_000_000.0)
    parser.add_argument("--wallets", nargs="*", help="Optional explicit 0x addresses (skips leaderboard filter)")
    args = parser.parse_args()

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    coin = normalize_coin(args.coin)

    if args.wallets:
        lb = pd.DataFrame({"wallet": [w.lower() for w in args.wallets]})
    else:
        raw = _get_json(LEADERBOARD_URL)
        rows = raw.get("leaderboardRows") or []
        lb = pick_leaderboard_wallets(
            rows,
            n=args.n_wallets,
            min_account_value=args.min_account_value,
            max_account_value=args.max_account_value,
            min_month_vlm=args.min_month_vlm,
        )
        if lb.empty:
            print("error: no leaderboard wallets matched filters", file=sys.stderr)
            return 1

    equity_parts: list[pd.DataFrame] = []
    flow_parts: list[pd.DataFrame] = []
    pnl_parts: list[pd.DataFrame] = []
    meta_rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for i, row in lb.iterrows():
        addr = str(row["wallet"])
        try:
            tape = ingest_wallet(addr, coin)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            errors.append({"wallet": addr, "error": f"{type(exc).__name__}: {exc}"})
            time.sleep(max(args.sleep, 0.0))
            continue
        for window, series in tape["windows"].items():
            equity_parts.append(_series_frame(addr, series, window))
        flow_parts.append(_series_frame(addr, tape["cashflow"], "perp_cf"))
        pnl_parts.append(_series_frame(addr, tape["coin_pnl"], f"pnl_{coin}"))
        meta_rows.append(
            {
                "wallet": addr,
                "n_fills": tape["n_fills"],
                "n_ledger": tape["n_ledger"],
                "traded_coin": tape["traded_coin"],
                "fill_coins": json.dumps(tape["fill_coins"]),
                "account_value": float(row["account_value"]) if "account_value" in row and pd.notna(row.get("account_value")) else None,
                "roi_month": float(row["roi_month"]) if "roi_month" in row and pd.notna(row.get("roi_month")) else None,
                "vlm_month": float(row["vlm_month"]) if "vlm_month" in row and pd.notna(row.get("vlm_month")) else None,
                "roi_all": float(row["roi_all"]) if "roi_all" in row and pd.notna(row.get("roi_all")) else None,
            }
        )
        print(f"[{i+1}/{len(lb)}] {addr} fills={tape['n_fills']} ledger={tape['n_ledger']} coin={tape['traded_coin']}")
        time.sleep(max(args.sleep, 0.0))

    equity = pd.concat(equity_parts, ignore_index=True) if equity_parts else pd.DataFrame()
    flows = pd.concat(flow_parts, ignore_index=True) if flow_parts else pd.DataFrame()
    pnls = pd.concat(pnl_parts, ignore_index=True) if pnl_parts else pd.DataFrame()
    meta = pd.DataFrame(meta_rows)

    equity.to_parquet(out / "equity.parquet", index=False)
    flows.to_parquet(out / "cashflow.parquet", index=False)
    pnls.to_parquet(out / "coin_pnl.parquet", index=False)
    meta.to_parquet(out / "wallets.parquet", index=False)
    if not lb.empty:
        lb.to_parquet(out / "leaderboard_sample.parquet", index=False)

    summary = {
        "venue": "hyperliquid",
        "coin": coin,
        "n_requested": int(len(lb)),
        "n_ok": int(len(meta)),
        "n_errors": int(len(errors)),
        "errors": errors,
        "info_url": INFO_URL,
        "leaderboard_url": LEADERBOARD_URL,
        "notes": [
            "portfolio allTime/perpAllTime NAV is sparse (≈weekly); month windows are denser.",
            "userFills returns at most 2000 recent fills (≈10k via userFillsByTime).",
            "TWR requires cashflow parquet; do not rank on leaderboard ROI.",
        ],
    }
    (out / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("n_ok", "n_errors", "coin")}, indent=2))
    return 0 if meta_rows else 2


if __name__ == "__main__":
    raise SystemExit(main())
