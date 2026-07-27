# Normalized IBS + RSI — cross-asset sweep

**Run:** pullback_mr_jul2026  
**OOS cut-off:** 2025-01-01  
**Rules:** RSI(3) < 10.0, 2-day avg IBS < 0.45, exit when close > prior day high  
**Costs:** fee 0.00045, slippage 0.0005; 100% equity per trade

Same parameters as the QQQ baseline (no per-asset tuning).

## Full-sample comparison

| Asset | Data | Ann. | Trades | Win% | PF | Avg/trade | CAGR | MaxDD | Exposure |
|-------|------|------|--------|------|-----|-----------|------|-------|----------|
| Nasdaq-100 (QQQ) | yfinance:QQQ | 252 | 383 | 73% | 2.36 | 0.83% | 11.6% | -27.2% | 29% |
| S&P 500 (SPY) | yfinance:SPY | 252 | 462 | 71% | 1.86 | 0.40% | 5.4% | -22.1% | 29% |
| Russell 2000 (IWM) | yfinance:IWM | 252 | 345 | 68% | 1.29 | 0.25% | 2.7% | -38.0% | 31% |
| Gold (GLD ETF) | yfinance:GLD | 252 | 263 | 58% | 0.80 | -0.16% | -2.2% | -43.4% | 26% |
| Bitcoin (BTC-USD) | local:/root/thequantgpt-wrapper/data/talos/cm_BTCUSDT_market_candles_1d.parquet | 365 | 139 | 67% | 1.14 | 0.29% | 1.8% | -47.7% | 26% |
| Ethereum (ETH-USD) | local:/root/thequantgpt-wrapper/data/talos/cm_ETHUSDT_market_candles_1d.parquet | 365 | 138 | 72% | 1.23 | 0.61% | 4.7% | -67.8% | 29% |

## Out-of-sample (from 2025-01-01)

| Asset | Sharpe | CAGR | MaxDD | Trades | Win% | PF |
|-------|--------|------|-------|--------|------|-----|
| Nasdaq-100 (QQQ) | 0.67 | 8.9% | -11.1% | 19 | 74% | 1.98 |
| S&P 500 (SPY) | 0.32 | 3.2% | -8.2% | 17 | 59% | 1.42 |
| Russell 2000 (IWM) | 1.00 | 11.4% | -9.4% | 16 | 75% | 2.85 |
| Gold (GLD ETF) | -0.12 | -1.8% | -17.5% | 13 | 69% | 0.89 |
| Bitcoin (BTC-USD) | 0.17 | 0.7% | -35.5% | 34 | 68% | 1.08 |
| Ethereum (ETH-USD) | 1.01 | 43.6% | -32.6% | 33 | 79% | 1.77 |

## Notes

- IBS mean reversion is documented by QS primarily on broad equity indices; crypto/metals may behave differently.
- BTC/ETH use 365-day annualization; ETFs use 252.
- Charts: `charts/ibs_cross_asset_equity.png` and per-asset `charts/ibs_<symbol>_equity.png`.
