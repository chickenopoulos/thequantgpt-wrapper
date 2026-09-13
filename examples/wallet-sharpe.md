# Wallet / account Sharpe (Hyperliquid first)

Measure **Sharpe per wallet** from venue tapes, not from leaderboard ROI and not from naive equity percent-change.

Hyperliquid is the right first venue: every account is a public `0x` address, the info API exposes NAV / ledger / fills / funding, and a public leaderboard exists at `https://stats-data.hyperliquid.xyz/Mainnet/leaderboard`. True L1 replay (every wallet, full history) is S3 `node_fills_by_block` + `misc_events_by_block`; the API path is enough to prototype.

## Do not do this

- Rank on `windowPerformances.roi`. That is a window return, not Sharpe, and it is contaminated by deposits.
- `equity.pct_change()`. A deposit looks like a winning day.
- Treat BTC PnL / account equity as isolated-margin BTC Sharpe. Cross-margin shares capital.

## Pipeline

```text
universe          leaderboard | coin fills | watchlist
     │
     ▼
ingest (network)  scripts/hl_wallet_ingest.py  →  parquet under data/ or runs/<id>/inputs/
     │            portfolio NAV, ledger CF, fills, funding
     ▼
TWR               r_t = V_t / (V_{t-1} + CF_t) - 1
     │            CF = deposit/withdraw/transfer/vault/class-transfer
     ▼
rank (IS only)    min bars, min equity, optional coin filter
     ▼
copy-top-k        freeze names, report OOS TWR Sharpe of the EW book
```

OOS default: `2025-01-01`. N = wallets ranked. DSR is not an OOS forecast.

## Commands

```bash
cd /root/thequantgpt-wrapper && source .venv/bin/activate

# correctness (no network)
python scripts/tqg_test_wallet_sharpe.py
python scripts/tqg_wallet_sharpe.py --synthetic --oos-start 2025-01-01

# live sample → local parquet (rate-limit with --sleep)
python scripts/hl_wallet_ingest.py \
  --out data/hyperliquid/wallets \
  --n-wallets 20 --coin BTC --sleep 0.2

# weekly TWR on sparse perpAllTime NAV
python scripts/tqg_wallet_sharpe.py \
  --data-dir data/hyperliquid/wallets \
  --nav-kind perpAllTime --freq 1W --annualization 52 \
  --min-is-bars 20 --oos-start 2025-01-01
```

Lab demo run (synthetic book so the harness has IS/OOS metrics):

```bash
python scripts/tqg_run_backtest.py hl_wallet_sharpe
```

## API surfaces used

| Need | Endpoint |
|------|----------|
| Universe | `GET https://stats-data.hyperliquid.xyz/Mainnet/leaderboard` |
| NAV history | `POST /info` `{"type":"portfolio","user":"0x…"}` windows `perpMonth` / `perpAllTime` |
| Capital flows | `{"type":"userNonFundingLedgerUpdates","user":"0x…"}` |
| Coin PnL | `{"type":"userFills","user":"0x…"}` (≤2000) + `{"type":"userFunding","user":"0x…"}` |

`perpAllTime` snapshots are roughly weekly. Daily Sharpe needs either the month window, your own snapshot job, or S3 replay.

## Coin-level Sharpe

For Hyperliquid BTC (coin `BTC`, not `BTCUSDT`):

1. Sum `closedPnl - fee` + funding `usdc` for that coin each day.
2. Divide by **prior account equity** → contribution return.
3. Report wallet TWR Sharpe *and* coin contribution Sharpe. They answer different questions.

Isolated-margin accounts can replace the denominator with isolated margin; the library does not infer that from fills alone.

## Scale-up

| Stage | What you store | Cost |
|-------|----------------|------|
| Prototype | Top-N leaderboard wallets, API NAV + ledger | minutes, 4 info calls / wallet |
| Production API | Daily snapshot of `clearinghouseState` for a watchlist | cheap going forward, short history |
| Full venue | S3 fills + misc events + clearinghouse snapshot replay | honest all-wallet, all-time, heavy |
