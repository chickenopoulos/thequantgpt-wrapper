#!/usr/bin/env python3
"""Unit tests for wallet TWR Sharpe: deposits are not skill, OOS is frozen."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.wallet_sharpe import (  # noqa: E402
    copy_topk_returns,
    ledger_to_cashflow,
    rank_wallets,
    signed_perp_cashflow,
    split_is_oos,
    synthetic_wallet_panel,
    twr_returns,
)


def test_deposit_is_not_a_return() -> None:
    idx = pd.date_range("2024-01-01", periods=5, freq="1D", tz="UTC")
    equity = pd.Series([100.0, 101.0, 201.0, 202.0, 203.0], index=idx)
    cf = pd.Series([0.0, 0.0, 100.0, 0.0, 0.0], index=idx)
    twr = twr_returns(equity, cf, timing="open")
    naive = equity.pct_change()
    # Day 2: 201 / (101 + 100) - 1 ≈ 0, not +99%.
    assert abs(float(twr.iloc[2])) < 0.02
    assert float(naive.iloc[2]) > 0.5


def test_withdraw_sign() -> None:
    user = "0xabc"
    assert signed_perp_cashflow(user, {"type": "deposit", "usdc": "50"}) == 50.0
    assert signed_perp_cashflow(user, {"type": "withdraw", "usdc": "20", "fee": "1"}) == -21.0
    assert (
        signed_perp_cashflow(
            user,
            {"type": "internalTransfer", "usdc": "10", "user": "0xdef", "destination": user},
        )
        == 10.0
    )
    assert signed_perp_cashflow(user, {"type": "accountClassTransfer", "usdc": "8", "toPerp": True}) == 8.0
    assert signed_perp_cashflow(user, {"type": "accountClassTransfer", "usdc": "8", "toPerp": False}) == -8.0
    assert signed_perp_cashflow(user, {"type": "liquidation", "accountValue": "1"}) == 0.0


def test_ledger_collapse() -> None:
    user = "0xabc"
    events = [
        {"time": 1_700_000_000_000, "delta": {"type": "deposit", "usdc": "100"}},
        {"time": 1_700_000_000_000, "delta": {"type": "withdraw", "usdc": "25", "fee": "0"}},
    ]
    s = ledger_to_cashflow(events, user)
    assert len(s) == 1
    assert float(s.iloc[0]) == 75.0


def test_faker_loses_to_skill_on_twr() -> None:
    recs = synthetic_wallet_panel(n_noise=8, seed=3)
    ranking = rank_wallets(
        recs,
        oos_start="2025-01-01",
        annualization=365,
        min_is_bars=30,
        coin="BTC",
    )
    by_name = ranking.set_index("wallet")
    assert bool(by_name.loc["skill_btc", "eligible"])
    assert not bool(by_name.loc["short_lived", "eligible"])
    assert float(by_name.loc["skill_btc", "sharpe_is_twr"]) > float(by_name.loc["deposit_faker", "sharpe_is_twr"])
    # Naive pct_change on the faker is a different (wrong) number than TWR.
    # Deposit days can inflate mean *or* vol, so naive Sharpe is not always larger.
    faker = recs["deposit_faker"]
    naive = faker.naive()
    twr = faker.twr()
    gap = (naive - twr).abs().max()
    assert float(gap) > 1.0
    assert float(by_name.loc["deposit_faker", "sharpe_is_naive"]) != float(by_name.loc["deposit_faker", "sharpe_is_twr"])
    # BTC specialist: coin contribution > wallet TWR (rest of book bleeds).
    assert float(by_name.loc["btc_specialist", "sharpe_is_coin"]) > float(by_name.loc["btc_specialist", "sharpe_is_twr"])


def test_copy_book_frozen_on_is() -> None:
    recs = synthetic_wallet_panel(n_noise=6, seed=11)
    ranking = rank_wallets(recs, oos_start="2025-01-01", annualization=365, min_is_bars=30)
    book, names = copy_topk_returns(recs, ranking, oos_start="2025-01-01", top_k=3)
    assert "skill_btc" in names
    assert "short_lived" not in names
    is_r, oos_r = split_is_oos(book, "2025-01-01")
    assert len(is_r.dropna()) > 200
    assert len(oos_r.dropna()) > 50
    # Re-rank using a leak would pick on OOS; names must match IS-only ranking.
    names_again = (
        ranking.loc[ranking["eligible"]]
        .sort_values("sharpe_is_twr", ascending=False)
        .head(3)["wallet"]
        .tolist()
    )
    assert names == names_again


def test_oos_not_in_rank_key() -> None:
    recs = synthetic_wallet_panel(n_noise=5, seed=1)
    ranking = rank_wallets(recs, oos_start="2025-01-01", annualization=365, min_is_bars=30)
    eligible = ranking.loc[ranking["eligible"]].copy()
    # Rank column is a monotone transform of IS TWR Sharpe, not OOS.
    is_order = eligible.sort_values("sharpe_is_twr", ascending=False)["wallet"].tolist()
    rank_order = eligible.sort_values("rank_is_twr")["wallet"].tolist()
    assert is_order == rank_order
    oos_order = eligible.sort_values("sharpe_oos_twr", ascending=False)["wallet"].tolist()
    # Extremely likely they differ with noise wallets; if equal, IS/OOS still both exist.
    assert "sharpe_oos_twr" in eligible.columns
    _ = oos_order


def main() -> int:
    tests = [
        test_deposit_is_not_a_return,
        test_withdraw_sign,
        test_ledger_collapse,
        test_faker_loses_to_skill_on_twr,
        test_copy_book_frozen_on_is,
        test_oos_not_in_rank_key,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"ok  {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
    if failed:
        print(f"{failed}/{len(tests)} failed")
        return 1
    print(f"{len(tests)}/{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
