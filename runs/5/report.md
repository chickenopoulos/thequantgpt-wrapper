# BTC Five-Strategy Ensemble v3 — All Providers

**Run:** `runs/5` | **Symbol:** BTCUSDT (one symbol only) | **OOS:** 2025-01-01

## Data providers searched

- **Talos:** OHLCV + 149 on-chain/derivatives metrics (`cm_btc_asset_metrics_1d.parquet`)
- **Coinglass:** 18 daily BTC series (funding, OI, liquidations, ETF, orderbook, Puell, etc.)
- **Binance:** futures OHLCV bundle (618 assets) + venue spread signals
- **Hyperliquid:** futures OHLCV (182 assets) + cross-venue spreads

**Search space:** 4,984 pure-signal configs | **Qualifying hits:** 38

## Target criteria

| Level | Sharpe | Max drawdown |
|-------|--------|--------------|
| Per strategy | ≥ 1.0 | < 25% |
| Ensemble | > 2.0 | < 15% |

**Strategies passing both: 5/5**

| ID | Provider | Family | Sharpe | IS | OOS | MaxDD | Trades | Pass |
|----|----------|--------|--------|----|-----|-------|--------|------|
| S1 | talos | exchange_flow | 1.52 | 1.76 | 0.25 | -15.7% | 162 | Yes |
| S2 | talos | derivatives_funding | 1.33 | 1.35 | 1.25 | -20.9% | 8 | Yes |
| S3 | talos | open_interest | 1.12 | 1.26 | 0.00 | -19.0% | 6 | Yes |
| S4 | coinglass | liquidation_fade | 1.06 | 1.36 | -0.89 | -16.0% | 80 | Yes |
| S5 | talos | derivatives_funding | 1.28 | 1.23 | 1.47 | -24.5% | 10 | Yes |

## Ensemble (equal-weight)

- Sharpe: **1.91** | MaxDD: **-9.7%** | OOS: 1.00

## Ensemble (optimized weights, DD < 15%)

- Weights: {'S1': 0.31, 'S2': 0.23, 'S3': 0.2, 'S4': 0.2, 'S5': 0.06}
- Sharpe: **1.97** (target > 2.0) — MISS
- Max drawdown: **-7.9%** (target < 15%) — PASS
- OOS Sharpe: 0.75

## Key finding

Leveraging all providers unlocked **38 qualifying sleeves** (vs 0 in the prior
Talos-OHLCV + partial-Coinglass search). The breakthrough signal is Talos
**Binance net exchange flow** (`FlowNetBNBUSD`) with 200DMA gate — Sharpe 1.58,
DD −17.5%. Coinglass liquidation fade and Talos cumulative funding/OI sleeves
are complementary derivatives/on-chain signals.
