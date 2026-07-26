# Strategy Catalog Sweep Results

> **Generated:** batch sweep via `scripts/tqg_strategy_catalog_sweep.py`  
> **Note:** Research-only backtests; full history (not OOS-only). Costs: fee 4.5bps + slip 5bps.  
> **OK:** 104/130 strategies executed.

| ID | Strategy | Sharpe | MaxDD | CAGR | Trades | Universe | Asset Class | Status |
|----|----------|--------|-------|------|--------|----------|-------------|--------|
| CG-01 | Funding carry | 0.23 | -37.7% | 2.6% | 159 | BTCUSDT | crypto | OK |
| CG-02 | Funding extreme fade | 0.00 | 0.0% | 0.0% | 0 | BTCUSDT | crypto | OK |
| CG-03 | OI expansion breakout | 0.48 | -74.7% | 11.8% | 214 | BTCUSDT | crypto | OK |
| CG-04 | OI divergence fade | 0.00 | 0.0% | 0.0% | 0 | BTCUSDT | crypto | OK |
| CG-05 | Liquidation cascade fade | 0.67 | -33.9% | 12.7% | 82 | BTCUSDT | crypto | OK |
| CG-06 | Short squeeze setup | 0.48 | -21.9% | 5.5% | 84 | BTCUSDT | crypto | OK |
| CG-07 | Taker buy imbalance | -0.11 | -6.4% | -0.3% | 4 | BTCUSDT | crypto | OK |
| CG-08 | Orderbook imbalance | 0.54 | -18.2% | 6.7% | 117 | BTCUSDT | crypto | OK |
| CG-09 | Whale gate + trend | 0.88 | -68.8% | 32.0% | 131 | BTCUSDT | crypto | OK |
| CG-10 | run_CG_10 | — | — | — | — | — | — | SKIP (global L/S ratio file) |
| CG-11 | run_CG_11 | — | — | — | — | — | — | SKIP (net position v2 file) |
| CG-12 | ETF flow momentum | 0.47 | -44.7% | 8.6% | 26 | BTCUSDT | crypto | OK |
| CG-13 | ETF flow divergence | 0.49 | -39.5% | 8.7% | 23 | BTCUSDT | crypto | OK |
| CG-14 | ETF premium discount | 0.00 | 0.0% | 0.0% | 0 | BTCUSDT | crypto | OK |
| CG-15 | Exchange balance drain | 0.41 | -48.4% | 7.4% | 14 | BTCUSDT | crypto | OK |
| CG-16 | Puell multiple bottom | 0.67 | -35.4% | 14.6% | 4 | BTCUSDT | crypto | OK |
| CG-17 | Basis carry | 0.69 | -71.9% | 23.5% | 78 | BTCUSDT | crypto | OK |
| CG-18 | Multi-factor bottoming | 0.00 | 0.0% | 0.0% | 0 | BTCUSDT | crypto | OK |
| CG-19 | Funding-weighted CS mom | 0.44 | -92.2% | -3.7% | 2254 | Binance perps | cross-section | OK |
| CG-20 | Funding extreme MR | 0.00 | 0.0% | 0.0% | 0 | BTCUSDT | crypto | OK |
| DV-01 | Funding trend | 0.78 | -80.3% | 31.6% | 6 | BTC | crypto | OK |
| DV-02 | run_DV_02 | — | — | — | — | — | — | SKIP (OI/MCAP talos join) |
| DV-03 | run_DV_03 | — | — | — | — | — | — | SKIP (options OI put/call talos) |
| DV-04 | run_DV_04 | — | — | — | — | — | — | SKIP (vol term structure talos columns) |
| DV-05 | run_DV_05 | — | — | — | — | — | — | SKIP (perp/spot volume ratio) |
| EF-01 | Exchange net outflow | 0.49 | -48.4% | 9.6% | 40 | BTC | crypto | OK |
| EF-02 | run_EF_02 | — | — | — | — | — | — | SKIP (miner flows not mapped) |
| EF-03 | ETF + exchange combo | 0.50 | -45.8% | 9.2% | 25 | BTC | crypto | OK |
| EF-04 | run_EF_04 | — | — | — | — | — | — | SKIP (stablecoin flow upload required) |
| GF-01 | Deep value accumulator | 0.00 | 0.0% | 0.0% | 0 | BTC multi-layer | crypto | OK |
| GF-02 | Bear late-stage ETF | 0.20 | -36.6% | 1.9% | 84 | BTC | crypto | OK |
| GF-03 | Recovery confirmation | 0.00 | 0.0% | 0.0% | 0 | BTC | crypto | OK |
| GF-04 | Risk-off de-risk | 0.00 | 0.0% | 0.0% | 0 | BTC | crypto | OK |
| GF-05 | Macro liquidity BTC | 0.00 | 0.0% | 0.0% | 0 | BTC+DXY | multi-asset | OK |
| GF-06 | Dollar inverse sleeve | 0.81 | -30.7% | 11.1% | 1188 | BTC+DXY | multi-asset | OK |
| GF-07 | run_GF_07 | — | — | — | — | — | — | SKIP (options max pain strikes required) |
| GF-08 | Vol compression breakout | -0.20 | -56.0% | -4.6% | 14 | BTC | crypto | OK |
| GF-09 | STH resistance fade | 0.00 | 0.0% | 0.0% | 0 | BTC | crypto | OK |
| GF-10 | Week 28 scorecard | 0.65 | -25.9% | 11.8% | 5 | BTC multi-layer | crypto | OK |
| IA-01 | BTC leads ETH | 1.03 | -73.0% | 53.4% | 628 | ETHUSDT | crypto | OK |
| IA-02 | SPY leads BTC | 0.00 | 0.0% | 0.0% | 0 | BTCUSDT | crypto | OK |
| IA-03 | Gold/BTC ratio MR | -0.67 | -46.2% | -24.3% | 2 | PAXG/BTC | crypto | OK |
| IA-04 | Copper/gold risk-on | 0.00 | 0.0% | 0.0% | 0 | BTC | crypto | OK |
| IA-05 | Oil shock risk-off | 0.81 | -76.7% | 35.8% | 1 | BTCUSDT | crypto | OK |
| IA-06 | run_IA_06 | — | — | — | — | — | — | ERROR (No data found for NVDAUSDT after checking local data; yfinance returned no data for NVDAUSDT.) |
| IA-07 | run_IA_07 | — | — | — | — | — | — | ERROR (No data found for SPYUSDT after checking local data; yfinance returned no data for SPYUSDT.) |
| IA-08 | ETH/BTC rotation | 0.59 | -67.2% | 17.8% | 107 | ETHUSDT | crypto | OK |
| IA-09 | DXY risk filter | 0.66 | -56.8% | 19.5% | 779 | BTCUSDT | crypto | OK |
| IA-10 | Intermarket divergence | 0.40 | -20.8% | 4.9% | 20 | ETH lag BTC | crypto | OK |
| MR-01 | Bollinger fade | 0.26 | -51.4% | 2.6% | 39 | BTCUSDT | crypto | OK |
| MR-02 | RSI oversold bounce | 0.47 | -51.4% | 10.6% | 44 | BTCUSDT | crypto | OK |
| MR-03 | RSI + ER gate | 0.64 | -18.3% | 10.5% | 13 | BTCUSDT | crypto | OK |
| MR-04 | Z-score vs MA | 0.26 | -51.4% | 2.6% | 39 | BTCUSDT | crypto | OK |
| MR-05 | Intraday gap fade | 0.00 | 0.0% | 0.0% | 0 | BTCUSDT 1h | crypto | OK |
| MR-06 | Short-term reversal | -0.51 | -68.4% | -13.0% | 59 | BTCUSDT | crypto | OK |
| MR-07 | Turnaround Tuesday | -0.04 | -49.5% | -0.6% | 700 | SPY | equity | OK |
| MR-08 | Turn-of-month | 0.00 | 0.0% | 0.0% | 0 | SPY | equity | OK |
| MR-09 | run_MR_09 | — | — | — | — | — | — | ERROR ('numpy.ndarray' object has no attribute 'shift') |
| MR-10 | Pairs ratio MR | -0.48 | -83.1% | -21.6% | 13 | BTC/ETH | crypto | OK |
| MR-11 | RSI on detrended | 0.46 | -66.8% | 10.8% | 303 | BTCUSDT | crypto | OK |
| MR-12 | Overnight reversal | 0.00 | 0.0% | 0.0% | 0 | BTCUSDT 1h | crypto | OK |
| MR-13 | 24h ticker fade | 0.04 | -80.4% | -4.7% | 343 | BTCUSDT 1h | crypto | OK |
| MR-14 | Low-volume fade | 0.98 | -30.5% | 16.6% | 87 | BTCUSDT | crypto | OK |
| MR-15 | QQQ RSI MR | 0.23 | -36.5% | 2.0% | 295 | QQQ | equity | OK |
| NA-01 | Active address momentum | 0.13 | -71.2% | -4.9% | 477 | BTC | crypto | OK |
| NA-02 | Tx count breakout | 0.21 | -76.3% | -0.5% | 336 | BTC | crypto | OK |
| NA-03 | run_NA_03 | — | — | — | — | — | — | SKIP (TxTfrValAdjUSD not verified) |
| NA-04 | run_NA_04 | — | — | — | — | — | — | SKIP (FeeMeanUSD not in btc metrics) |
| NA-05 | New address divergence | -0.07 | -74.5% | -12.5% | 321 | BTC | crypto | OK |
| ON-01 | MVRV Z-score | 0.00 | 0.0% | 0.0% | 0 | BTC | crypto | OK |
| ON-02 | NUPL regime | 0.90 | -76.7% | 42.9% | 1 | BTC | crypto | OK |
| ON-03 | Realized price support | 0.81 | -76.7% | 36.0% | 1 | BTC | crypto | OK |
| ON-04 | MVRV < 1 value | 1.19 | -49.6% | 53.0% | 2 | BTC | crypto | OK |
| ON-05 | run_ON_05 | — | — | — | — | — | — | SKIP (NVTAdj not in btc metrics file) |
| ON-06 | SOPR capitulation | 0.43 | -57.3% | 9.3% | 30 | BTC | crypto | OK |
| ON-07 | STH cost reclaim | 0.00 | 0.0% | 0.0% | 0 | BTC | crypto | OK |
| ON-08 | run_ON_08 | — | — | — | — | — | — | SKIP (SplyLTH not in btc metrics) |
| ON-09 | Accumulation proxy | 0.13 | -71.2% | -4.9% | 477 | BTC | crypto | OK |
| ON-10 | run_ON_10 | — | — | — | — | — | — | SKIP (realized loss metric not mapped) |
| Q-01 | run_Q_01 | — | — | — | — | — | — | SKIP (fundamentals required) |
| Q-02 | run_Q_02 | — | — | — | — | — | — | SKIP (earnings data required) |
| Q-03 | run_Q_03 | — | — | — | — | — | — | SKIP (fundamentals required) |
| Q-04 | run_Q_04 | — | — | — | — | — | — | SKIP (short interest/options required) |
| Q-05 | run_Q_05 | — | — | — | — | — | — | SKIP (crack spread data required) |
| Q-06 | VIX risk premium | -1.24 | -100.0% | -68.1% | 5219 | ^VIX | vol | OK |
| Q-07 | run_Q_07 | — | — | — | — | — | — | SKIP (intraday SPY upload required) |
| Q-08 | Recursive LS proxy | 0.75 | -69.9% | 26.1% | 121 | BTCUSDT | crypto | OK |
| Q-09 | Regime overlay proxy | 0.36 | -60.7% | 6.4% | 73 | BTCUSDT | crypto | OK |
| Q-10 | run_Q_10 | — | — | — | — | — | — | SKIP (margin debt/GDP macro upload required) |
| T-01 | Dual MA crossover | 0.94 | -54.9% | 37.8% | 13 | BTCUSDT | crypto | OK |
| T-02 | CMMA trend | 1.27 | -58.5% | 56.2% | 76 | BTCUSDT | crypto | OK |
| T-03 | Donchian breakout | 0.97 | -59.7% | 36.5% | 33 | BTCUSDT | crypto | OK |
| T-04 | Donchian + ER gate | 1.03 | -51.7% | 36.0% | 26 | BTCUSDT | crypto | OK |
| T-05 | TSMOM | 1.04 | -53.3% | 46.7% | 22 | BTCUSDT | crypto | OK |
| T-06 | Percentile-rank momentum | 0.63 | -62.8% | 16.3% | 30 | BTCUSDT | crypto | OK |
| T-07 | Multi-horizon momentum ensemble | 0.88 | -73.6% | 34.1% | 164 | BTCUSDT | crypto | OK |
| T-08 | Vol-filtered trend | 0.00 | 0.0% | 0.0% | 0 | BTCUSDT | crypto | OK |
| T-09 | 52-week high breakout | 0.84 | -39.8% | 22.4% | 24 | BTCUSDT | crypto | OK |
| T-10 | QQQ/BTC Donchian rotation | -1.53 | -1.8% | -14.2% | 3 | QQQUSDT+BTCUSDT | crypto | OK |
| T-11 | Session volume momentum | -2.86 | -98.1% | -36.7% | 1790 | BTCUSDT 1h | crypto | OK |
| T-12 | Hour-of-day vol tilt | -0.19 | -50.4% | -5.4% | 18689 | BTCUSDT 1h | crypto | OK |
| T-13 | Network momentum hub | 0.89 | -68.4% | 42.1% | 130 | ETHUSDT (BTC signal) | crypto | OK |
| T-14 | FX trend MA | 0.04 | -27.1% | 0.0% | 16 | EURUSD | fx | OK |
| T-15 | Commodity dual momentum | 0.59 | -33.4% | 8.0% | 78 | GLD vs USO | commodity | OK |
| TAA-01 | Faber 10M SMA | 0.70 | -24.9% | 8.0% | 108 | SPY | equity | OK |
| TAA-02 | Dual momentum TAA | 0.00 | 0.0% | 0.0% | 0 | SPY+GLD | equity | OK |
| TAA-03 | run_TAA_03 | — | — | — | — | — | — | SKIP (requires strategy return panel) |
| TAA-04 | Risk parity lite | 0.80 | -47.5% | 9.6% | 8330 | SPY+GLD+TLT | multi-asset | OK |
| TAA-05 | Bond filter equities | 0.46 | -47.6% | 6.1% | 178 | SPY+TLT | equity | OK |
| TAA-06 | Gold/rates triangle | 0.31 | -40.7% | 3.3% | 241 | GLD+TLT | commodity | OK |
| TAA-07 | Crypto vs equity rotation | 0.87 | -75.1% | 40.4% | 62 | BTC+SPY | multi-asset | OK |
| TAA-08 | Crisis convexity | -0.37 | -100.0% | -30.3% | 1125 | ^VIX | vol | OK |
| V-01 | Realized vol breakout | 0.54 | -52.8% | 14.9% | 1024 | BTCUSDT | crypto | OK |
| V-02 | Vol targeting overlay | 0.95 | -18.3% | 13.3% | 1660 | BTCUSDT | crypto | OK |
| V-03 | Vol regime switch | -0.07 | -66.6% | -5.9% | 34 | BTCUSDT | crypto | OK |
| V-04 | SAR vol forecast sizing | 0.41 | -95.4% | 0.9% | 38740 | BTCUSDT 1h | crypto | OK |
| V-05 | VIX term structure | -1.24 | -100.0% | -68.1% | 5219 | ^VIX | vol | OK |
| V-06 | DVOL proxy spike | -0.81 | -35.0% | -6.0% | 365 | BTCUSDT | crypto | OK |
| V-07 | GARCH vol gate | 1.00 | -45.8% | 28.5% | 176 | BTCUSDT | crypto | OK |
| V-08 | Entropy chop filter | 0.00 | 0.0% | 0.0% | 0 | BTCUSDT | crypto | OK |
| XS-01 | CS momentum | 0.44 | -92.2% | -3.7% | 2254 | Binance perps | cross-section | OK |
| XS-02 | RSI rank L/S | 1.36 | -58.3% | 101.5% | 2260 | Binance perps | cross-section | OK |
| XS-03 | Vol-scaled momentum | 0.78 | -90.4% | 23.8% | 2254 | Binance perps | cross-section | OK |
| XS-04 | STR CS | 0.79 | -81.2% | 30.7% | 2269 | Binance perps | cross-section | OK |
| XS-05 | Path convexity | 1.05 | -83.1% | 56.3% | 2255 | Binance perps | cross-section | OK |
| XS-06 | Network momentum CS | 0.44 | -92.2% | -3.7% | 2254 | Binance perps | cross-section | OK |
| XS-07 | Dollar vol filter mom | 0.86 | -98.0% | 32.8% | 2254 | Top 50 liq perps | cross-section | OK |
| XS-08 | run_XS_08 | — | — | — | — | — | — | SKIP (funding cross-section join not in sweep v1) |
| XS-09 | Beta-neutral mom | 0.08 | -95.7% | -30.5% | 2319 | Binance perps | cross-section | OK |
| XS-10 | Demeaned return target | -0.32 | -97.8% | -38.6% | 2273 | Binance perps | cross-section | OK |
