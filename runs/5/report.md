# BTC Five-Strategy Ensemble Research

**Run:** `runs/5` | **Symbol:** BTCUSDT (one symbol only) | **OOS:** 2025-01-01
**Data:** local:/root/thequantgpt-wrapper/data/talos/cm_BTCUSDT_market_candles_1d.parquet | 2019-09-08 → 2026-05-08

## Executive summary

After sweeping **1,300+** pure-signal configurations (trend, mean-reversion, on-chain,
microstructure, intermarket) plus the full 130-strategy catalog, **no single daily BTC
strategy with ≥5 round-trips simultaneously achieves Sharpe ≥ 1.0 and max drawdown < 25%**
after 9.5bps round-trip costs on this sample.

The five strategies below are the **best diverse, literature-motivated sleeves** — each
from a different signal family. Several are close to the Sharpe/DD target or strong OOS.

## Five strategies

| ID | Family | Name | Sharpe | IS | OOS | MaxDD | CAGR | Trades |
|----|--------|------|--------|----|-----|-------|------|--------|
| S1 | onchain_value | Puell value + 200DMA gate | 0.94 | 1.04 | 0.34 | -24.5% | 22.2% | 6 |
| S2 | mean_reversion | IBS + RSI pullback in uptrend | 0.80 | 0.72 | 1.90 | -6.9% | 5.2% | 54 |
| S3 | regime_mr | RSI oversold in low-efficiency chop | 0.64 | 0.81 | -0.03 | -18.3% | 10.5% | 26 |
| S4 | microstructure | Negative funding momentum | 0.48 | 0.56 | -0.03 | -21.9% | 5.5% | 168 |
| S5 | trend | CMMA(40) ATR-normalized trend | 1.27 | 1.41 | 0.49 | -58.5% | 56.2% | 151 |

### Signal definitions

- **S1** (onchain_value): Miner revenue stress (Puell) within uptrend; Liu/Tsyvinski MA timing. Params: `{'puell_entry': 0.7, 'puell_exit': 1.5, 'trend_ma': 200}`
- **S2** (mean_reversion): Internal bar strength + RSI oversold; Connors short-term MR. Params: `{'trend_ma': 125, 'ibs_entry': 0.35, 'rsi_entry': 35, 'ibs_exit': 0.5}`
- **S3** (regime_mr): Mean reversion when Kaufman ER > 0.5 (ranging market). Params: `{'er_min': 0.5, 'rsi_entry': 30, 'rsi_exit': 50}`
- **S4** (microstructure): Short-squeeze setup: negative perp funding + rising price. Params: `{'funding_thr': 0.0, 'momentum_days': 5}`
- **S5** (trend): Cumulative MA normalized by ATR; Moskowitz/Ooi/Pedersen TSMOM variant. Params: `{'cmma_window': 40}`

## Ensemble (equal-weight positions, clipped ±1)

- Sharpe: **1.57** (target > 2.0)
- Max drawdown: **-18.0%** (target < 15%)
- In-sample Sharpe: 1.74
- Out-of-sample Sharpe: 0.58

## Closest individual qualifiers

- **S1 Puell + 200DMA**: full Sharpe 0.94, DD −24.5% (IS Sharpe 1.04 — meets Sharpe in-sample)
- **S2 IBS pullback**: full Sharpe 0.80, DD −6.9% (OOS Sharpe 1.90 — strong recent validation)

## Artifacts

- `artifacts/btc_five_strategy_ensemble.json`
- `artifacts/metrics.json`
- `charts/ensemble_equity.png`
- `charts/strategy_equities.png`

## References consulted

- Liu & Tsyvinski (2018) — MA predictability in Bitcoin
- Gerritsen et al. (2020) — technical rules on daily BTC
- QuantPedia — multi-timeframe Elder filter on BTC
- Coinglass / Glassnode on-chain & microstructure conventions
