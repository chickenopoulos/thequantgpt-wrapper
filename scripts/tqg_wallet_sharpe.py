#!/usr/bin/env python3
"""Rank wallets on IS TWR Sharpe from local Hyperliquid parquet (or synthetic)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.wallet_sharpe import (  # noqa: E402
    WalletRecord,
    copy_topk_returns,
    rank_wallets,
    segment_metrics,
    split_is_oos,
    synthetic_wallet_panel,
)


def records_from_parquet(data_dir: Path, *, nav_kind: str = "perpAllTime") -> dict[str, WalletRecord]:
    equity = pd.read_parquet(data_dir / "equity.parquet")
    cashflow = pd.read_parquet(data_dir / "cashflow.parquet")
    coin_path = data_dir / "coin_pnl.parquet"
    coin = pd.read_parquet(coin_path) if coin_path.exists() else pd.DataFrame()
    wallets_path = data_dir / "wallets.parquet"
    meta = pd.read_parquet(wallets_path) if wallets_path.exists() else pd.DataFrame()
    meta_map = {}
    if not meta.empty:
        for _, row in meta.iterrows():
            meta_map[str(row["wallet"])] = {k: row[k] for k in meta.columns if k != "wallet"}

    eq = equity[equity["kind"] == nav_kind].copy() if "kind" in equity.columns else equity
    recs: dict[str, WalletRecord] = {}
    for wallet, grp in eq.groupby("wallet"):
        s = grp.set_index(pd.to_datetime(grp["time"], utc=True))["value"].astype(float).sort_index()
        cf = cashflow[cashflow["wallet"] == wallet]
        if cf.empty:
            flow = pd.Series(0.0, index=s.index)
        else:
            flow = (
                cf.set_index(pd.to_datetime(cf["time"], utc=True))["value"]
                .astype(float)
                .groupby(level=0)
                .sum()
                .sort_index()
            )
        pnl_s = pd.Series(dtype=float)
        if not coin.empty:
            c = coin[coin["wallet"] == wallet]
            if not c.empty:
                pnl_s = (
                    c.set_index(pd.to_datetime(c["time"], utc=True))["value"]
                    .astype(float)
                    .groupby(level=0)
                    .sum()
                    .sort_index()
                )
        recs[str(wallet)] = WalletRecord(
            wallet=str(wallet),
            equity=s.rename("equity"),
            cashflow=flow.rename("cashflow"),
            coin_pnl=pnl_s,
            meta={k: v for k, v in meta_map.get(str(wallet), {}).items() if k in {"roi_month", "vlm_month", "traded_coin", "account_value"}},
        )
    return recs


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank wallet TWR Sharpe from local tapes")
    parser.add_argument("--data-dir", type=Path, help="Directory with equity/cashflow parquet from hl_wallet_ingest.py")
    parser.add_argument("--synthetic", action="store_true", help="Use the built-in controlled panel")
    parser.add_argument("--oos-start", default="2025-01-01")
    parser.add_argument("--freq", default="1D", help="1D for synthetic/month tapes; 1W for sparse allTime NAV")
    parser.add_argument("--nav-kind", default="perpAllTime")
    parser.add_argument("--annualization", type=float, default=0.0, help="0 = 365 daily / 52 weekly")
    parser.add_argument("--min-is-bars", type=int, default=30)
    parser.add_argument("--min-active-equity", type=float, default=100.0)
    parser.add_argument("--min-mean-equity", type=float, default=0.0)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--coin", default="BTC")
    parser.add_argument("--out", type=Path, help="Optional CSV path for the ranking")
    args = parser.parse_args()

    if args.synthetic:
        recs = synthetic_wallet_panel()
        freq = args.freq
    elif args.data_dir:
        recs = records_from_parquet(args.data_dir, nav_kind=args.nav_kind)
        freq = args.freq
    else:
        print("error: pass --synthetic or --data-dir", file=sys.stderr)
        return 2

    ann = args.annualization
    if ann <= 0:
        ann = 52.0 if str(freq).upper().startswith("W") or freq in {"1W", "W"} else 365.0

    ranking = rank_wallets(
        recs,
        oos_start=args.oos_start,
        annualization=ann,
        freq=freq,
        min_is_bars=args.min_is_bars,
        min_mean_equity=args.min_mean_equity,
        min_active_equity=args.min_active_equity,
        coin=args.coin,
    )
    book, names = copy_topk_returns(recs, ranking, oos_start=args.oos_start, top_k=args.top_k, freq=freq)
    is_r, oos_r = split_is_oos(book, args.oos_start)
    summary = {
        "n_wallets": int(len(recs)),
        "n_eligible": int(ranking["eligible"].sum()) if not ranking.empty else 0,
        "top_k": names,
        "copy_is": segment_metrics(is_r, annualization=ann),
        "copy_oos": segment_metrics(oos_r, annualization=ann),
        "annualization": ann,
        "freq": freq,
        "oos_start": args.oos_start,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        ranking.to_csv(args.out, index=False)
    print(ranking.head(12).to_string(index=False))
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
