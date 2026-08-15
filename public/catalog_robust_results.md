# Catalog robust batch results

> Strategies: 130 · OK: 57 · STABLE PSA: 20 · RUNNER_ONLY: 38 · SKIP: 26

Primary Sharpe/MaxDD/CAGR columns are **out-of-sample** (cut-off 2025-01-01) when status=OK.
RUNNER_ONLY rows are full-sample fallback (no IS/OOS split) with confidence capped ≤25.

| Rank | ID | Strategy | Sharpe | MaxDD | CAGR | Conf | Mode | Status |
|------|-----|----------|--------|-------|------|------|------|--------|
| 1 | XS-02 | RSI rank L/S | 1.25 | -58.3% | 86.8% | 25 | catalog_runner_full_sample | RUNNER_ONLY |
| 2 | TAA-06 | Gold/rates triangle | 1.06 | -17.6% | 20.5% | 66 | soft_grid_max_robust_sharpe | OK |
| 3 | XS-05 | Price-path convexity | 1.01 | -83.1% | 51.7% | 25 | catalog_runner_full_sample | RUNNER_ONLY |
| 4 | V-02 | Vol targeting overlay | 0.95 | -18.3% | 13.3% | 25 | catalog_runner_full_sample | RUNNER_ONLY |
| 5 | IA-10 | Intermarket divergence | 0.88 | -14.9% | 20.9% | 63 | soft_grid_max_robust_sharpe | OK |
| 6 | T-07 | Multi-horizon ensemble | 0.88 | -73.6% | 34.1% | 25 | catalog_runner_full_sample | RUNNER_ONLY |
| 7 | T-02 | CMMA trend | 0.86 | -14.2% | 18.6% | 68 | soft_grid_max_robust_sharpe | OK |
| 8 | ON-03 | Realized price support | 0.81 | -76.7% | 36.0% | 20 | catalog_runner_full_sample | RUNNER_ONLY |
| 9 | GF-06 | Dollar inverse sleeve | 0.81 | -30.7% | 11.1% | 25 | catalog_runner_full_sample | RUNNER_ONLY |
| 10 | TAA-04 | Risk parity lite | 0.80 | -47.5% | 9.6% | 25 | catalog_runner_full_sample | RUNNER_ONLY |
| 11 | XS-03 | Vol-scaled momentum | 0.75 | -90.4% | 21.5% | 25 | catalog_runner_full_sample | RUNNER_ONLY |
| 12 | T-01 | Dual MA crossover | 0.74 | -16.6% | 15.9% | 50 | baseline_fallback | OK |
| 13 | XS-07 | Dollar volume filter | 0.73 | -99.4% | 10.7% | 25 | catalog_runner_full_sample | RUNNER_ONLY |
| 14 | XS-04 | Short-term reversal CS | 0.71 | -81.2% | 22.4% | 25 | catalog_runner_full_sample | RUNNER_ONLY |
| 15 | TAA-01 | Faber 10M SMA | 0.68 | -18.4% | 9.0% | 85 | psa_stable_plateau | OK |
| 16 | IA-09 | DXY risk filter | 0.66 | -56.8% | 19.5% | 25 | catalog_runner_full_sample | RUNNER_ONLY |
| 17 | T-15 | Commodity dual momentum | 0.59 | -33.4% | 7.9% | 25 | catalog_runner_full_sample | RUNNER_ONLY |
| 18 | MR-13 | 24h ticker fade | 0.59 | -13.0% | 5.3% | 68 | soft_grid_max_robust_sharpe | OK |
| 19 | Q-09 | Regime overlay proxy | 0.58 | -12.1% | 10.8% | 88 | psa_stable_plateau | OK |
| 20 | V-01 | Realized vol breakout | 0.54 | -52.8% | 14.9% | 25 | catalog_runner_full_sample | RUNNER_ONLY |
| 21 | V-04 | SAR seasonal vol forecast | 0.41 | -95.4% | 0.9% | 20 | catalog_runner_full_sample | RUNNER_ONLY |
| 22 | T-13 | Network momentum hub | 0.40 | -44.0% | 8.1% | 79 | psa_stable_plateau | OK |
| 23 | MR-11 | RSI on detrended | 0.40 | -33.0% | 7.7% | 62 | psa_stable_plateau | OK |
| 24 | Q-08 | Recursive LS proxy | 0.37 | -30.3% | 6.6% | 74 | psa_stable_plateau | OK |
| 25 | XS-01 | Cross-sectional momentum | 0.33 | -92.2% | -11.5% | 20 | catalog_runner_full_sample | RUNNER_ONLY |
| 26 | XS-06 | Network momentum CS | 0.33 | -92.2% | -11.5% | 20 | catalog_runner_full_sample | RUNNER_ONLY |
| 27 | CG-19 | Funding CS mom | 0.33 | -92.2% | -11.5% | 20 | catalog_runner_full_sample | RUNNER_ONLY |
| 28 | T-14 | FX trend MA | 0.30 | -4.9% | 1.8% | 38 | baseline_fallback | OK |
| 29 | T-04 | Donchian + ER gate | 0.26 | -30.2% | 3.3% | 56 | soft_grid_max_robust_sharpe | OK |
| 30 | GF-10 | Week 28 scorecard | 0.21 | -20.2% | 2.1% | 33 | baseline_fallback | OK |
| 31 | CG-15 | Exchange balance drain | 0.19 | -49.6% | -0.3% | 58 | soft_grid_max_robust_sharpe | OK |
| 32 | MR-14 | Low-volume fade | 0.19 | -13.5% | 1.6% | 44 | soft_grid_max_robust_sharpe | OK |
| 33 | T-05 | TSMOM | 0.14 | -32.0% | -1.3% | 48 | soft_grid_max_robust_sharpe | OK |
| 34 | EF-01 | Exchange net outflow | 0.13 | -45.6% | -3.4% | 51 | soft_grid_max_robust_sharpe | OK |
| 35 | MR-15 | QQQ RSI MR | 0.12 | -12.6% | 0.7% | 74 | psa_stable_plateau | OK |
| 36 | V-03 | Vol regime switch | 0.12 | -16.4% | 0.4% | 66 | psa_stable_plateau | OK |
| 37 | CG-13 | ETF flow divergence | 0.11 | -17.4% | 0.1% | 51 | soft_grid_max_robust_sharpe | OK |
| 38 | T-06 | Percentile-rank momentum | 0.03 | -27.2% | -1.2% | 36 | soft_grid_max_robust_sharpe | OK |
| 39 | CG-08 | Orderbook imbalance | 0.01 | -23.4% | -2.1% | 65 | psa_stable_plateau | OK |
| 40 | XS-09 | Beta-neutral momentum | 0.00 | -95.7% | -34.6% | 20 | catalog_runner_full_sample | RUNNER_ONLY |
| 41 | T-08 | Vol-filtered trend | 0.00 | 0.0% | 0.0% | 20 | baseline_fallback | NO_TRADES |
| 42 | MR-05 | Intraday gap fade | 0.00 | 0.0% | 0.0% | 20 | baseline_fallback | NO_TRADES |
| 43 | MR-12 | Overnight reversal | 0.00 | 0.0% | 0.0% | 20 | baseline_fallback | NO_TRADES |
| 44 | MR-08 | Turn-of-month | 0.00 | 0.0% | 0.0% | 10 | catalog_runner_full_sample | RUNNER_ONLY |
| 45 | V-08 | Entropy chop filter | 0.00 | 0.0% | 0.0% | 20 | baseline_fallback | NO_TRADES |
| 46 | TAA-02 | Dual momentum TAA | 0.00 | 0.0% | 0.0% | 10 | catalog_runner_full_sample | RUNNER_ONLY |
| 47 | CG-02 | Funding extreme fade | 0.00 | 0.0% | 0.0% | 20 | baseline_fallback | NO_TRADES |
| 48 | CG-04 | OI divergence fade | 0.00 | 0.0% | 0.0% | 20 | baseline_fallback | NO_TRADES |
| 49 | CG-16 | Puell multiple bottom | 0.00 | 0.0% | 0.0% | 35 | soft_grid_max_robust_sharpe | OK |
| 50 | CG-20 | Funding extreme MR | 0.00 | 0.0% | 0.0% | 20 | baseline_fallback | NO_TRADES |
| 51 | CG-14 | ETF premium discount | 0.00 | 0.0% | 0.0% | 10 | catalog_runner_full_sample | RUNNER_ONLY |
| 52 | CG-18 | Multi-factor BTC bottoming | 0.00 | 0.0% | 0.0% | 10 | catalog_runner_full_sample | RUNNER_ONLY |
| 53 | ON-01 | MVRV Z-score | 0.00 | 0.0% | 0.0% | 10 | catalog_runner_full_sample | RUNNER_ONLY |
| 54 | ON-07 | STH cost basis reclaim | 0.00 | 0.0% | 0.0% | 10 | catalog_runner_full_sample | RUNNER_ONLY |
| 55 | GF-01 | Deep value accumulator | 0.00 | 0.0% | 0.0% | 10 | catalog_runner_full_sample | RUNNER_ONLY |
| 56 | GF-03 | Recovery confirmation | 0.00 | 0.0% | 0.0% | 10 | catalog_runner_full_sample | RUNNER_ONLY |
| 57 | GF-04 | Risk-off de-risk | 0.00 | 0.0% | 0.0% | 10 | catalog_runner_full_sample | RUNNER_ONLY |
| 58 | GF-05 | Macro liquidity BTC | 0.00 | 0.0% | 0.0% | 10 | catalog_runner_full_sample | RUNNER_ONLY |
| 59 | GF-09 | STH resistance rejection | 0.00 | 0.0% | 0.0% | 10 | catalog_runner_full_sample | RUNNER_ONLY |
| 60 | IA-02 | SPY leads BTC | 0.00 | 0.0% | 0.0% | 20 | baseline_fallback | NO_TRADES |
| 61 | IA-04 | Copper/gold risk-on | 0.00 | 0.0% | 0.0% | 20 | baseline_fallback | NO_TRADES |
| 62 | NA-02 | Tx count breakout | -0.01 | -29.3% | -4.2% | 40 | soft_grid_max_robust_sharpe | OK |
| 63 | CG-17 | Basis carry | -0.02 | -49.6% | -10.3% | 39 | psa_stable_plateau | OK |
| 64 | ON-02 | NUPL regime | -0.03 | -49.6% | -10.8% | 5 | baseline_fallback | OK |
| 65 | ON-04 | MVRV < 1 value | -0.03 | -49.6% | -10.8% | 0 | baseline_fallback | OK |
| 66 | IA-05 | Oil shock risk-off | -0.03 | -49.6% | -10.8% | 10 | baseline_fallback | OK |
| 67 | MR-07 | Turnaround Tuesday | -0.04 | -49.5% | -0.7% | 15 | catalog_runner_full_sample | RUNNER_ONLY |
| 68 | CG-09 | Whale gate + trend | -0.06 | -36.2% | -4.7% | 43 | psa_stable_plateau | OK |
| 69 | NA-05 | New address growth | -0.07 | -74.5% | -12.5% | 15 | catalog_runner_full_sample | RUNNER_ONLY |
| 70 | IA-01 | BTC leads ETH | -0.09 | -54.1% | -18.1% | 35 | soft_grid_max_robust_sharpe | OK |
| 71 | CG-05 | Liquidation cascade fade | -0.12 | -14.7% | -2.6% | 48 | psa_stable_plateau | OK |
| 72 | EF-03 | ETF + exchange combo | -0.16 | -42.9% | -11.2% | 31 | soft_grid_max_robust_sharpe | OK |
| 73 | DV-01 | Funding trend | -0.18 | -49.6% | -16.5% | 34 | psa_stable_plateau | OK |
| 74 | T-12 | Hour-of-day vol tilt | -0.19 | -50.4% | -5.4% | 15 | catalog_runner_full_sample | RUNNER_ONLY |
| 75 | CG-12 | ETF flow momentum | -0.19 | -20.1% | -6.7% | 28 | soft_grid_max_robust_sharpe | OK |
| 76 | IA-08 | ETH/BTC rotation | -0.21 | -42.4% | -19.3% | 45 | psa_stable_plateau | OK |
| 77 | MR-03 | RSI + ER gate | -0.22 | -17.8% | -6.2% | 42 | psa_stable_plateau | OK |
| 78 | MR-01 | Bollinger fade | -0.25 | -28.3% | -11.6% | 33 | soft_grid_max_robust_sharpe | OK |
| 79 | MR-04 | Z-score vs MA | -0.25 | -28.3% | -11.6% | 33 | soft_grid_max_robust_sharpe | OK |
| 80 | ON-09 | Accumulation proxy | -0.27 | -41.8% | -13.3% | 35 | soft_grid_max_robust_sharpe | OK |
| 81 | NA-01 | Active address momentum | -0.27 | -41.8% | -13.3% | 35 | soft_grid_max_robust_sharpe | OK |
| 82 | V-07 | GARCH vol gate | -0.28 | -26.1% | -6.1% | 35 | soft_grid_max_robust_sharpe | OK |
| 83 | TAA-05 | Bond filter equities | -0.32 | -17.1% | -5.1% | 61 | psa_stable_plateau | OK |
| 84 | GF-08 | Vol compression breakout | -0.33 | -10.3% | -3.3% | 30 | soft_grid_max_robust_sharpe | OK |
| 85 | MR-06 | Short-term reversal | -0.34 | -25.0% | -9.0% | 36 | soft_grid_max_robust_sharpe | OK |
| 86 | TAA-08 | Crisis convexity sleeve | -0.37 | -100.0% | -30.2% | 15 | catalog_runner_full_sample | RUNNER_ONLY |
| 87 | ON-06 | SOPR capitulation | -0.38 | -30.1% | -11.1% | 34 | psa_stable_plateau | OK |
| 88 | XS-10 | Target = demeaned return | -0.40 | -98.0% | -41.8% | 15 | catalog_runner_full_sample | RUNNER_ONLY |
| 89 | TAA-07 | Crypto vs equity rotation | -0.42 | -41.7% | -19.4% | 35 | psa_stable_plateau | OK |
| 90 | T-03 | Donchian breakout | -0.51 | -41.1% | -13.3% | 23 | soft_grid_max_robust_sharpe | OK |
| 91 | MR-02 | RSI oversold bounce | -0.58 | -42.7% | -20.3% | 31 | soft_grid_max_robust_sharpe | OK |
| 92 | MR-10 | Pairs ratio MR | -0.61 | -18.7% | -10.7% | 30 | soft_grid_max_robust_sharpe | OK |
| 93 | T-09 | 52-week high breakout | -0.61 | -21.8% | -13.6% | 23 | soft_grid_max_robust_sharpe | OK |
| 94 | CG-07 | Taker buy imbalance | -0.62 | -12.3% | -5.9% | 31 | soft_grid_max_robust_sharpe | OK |
| 95 | IA-03 | Gold/BTC ratio MR | -0.67 | -46.2% | -24.3% | 10 | baseline_fallback | OK |
| 96 | GF-02 | Bear late-stage ETF | -0.72 | -32.8% | -20.2% | 35 | soft_grid_max_robust_sharpe | OK |
| 97 | V-06 | Intraday straddle proxy | -0.81 | -34.9% | -6.0% | 15 | catalog_runner_full_sample | RUNNER_ONLY |
| 98 | CG-01 | Funding carry | -0.94 | -16.7% | -11.0% | 60 | psa_stable_plateau | OK |
| 99 | CG-06 | Short squeeze setup | -1.07 | -7.9% | -5.9% | 51 | psa_stable_plateau | OK |
| 100 | V-05 | VIX term structure ⚠️ | -1.23 | -100.0% | -67.9% | 15 | catalog_runner_full_sample | RUNNER_ONLY |
| 101 | Q-06 | VIX risk premium | -1.23 | -100.0% | -67.9% | 15 | catalog_runner_full_sample | RUNNER_ONLY |
| 102 | CG-03 | OI expansion breakout | -1.44 | -38.6% | -28.3% | 43 | psa_stable_plateau | OK |
| 103 | T-10 | QQQ/BTC Donchian rotation | -1.53 | -1.8% | -14.2% | 0 | baseline_fallback | OK |
| 104 | T-11 | Session volume momentum | -2.86 | -98.1% | -36.8% | 15 | catalog_runner_full_sample | RUNNER_ONLY |
| 105 | MR-09 | Holiday effect | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 106 | TAA-03 | Distressed TAA rotation | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 107 | XS-08 | Funding carry rank | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 108 | CG-10 | Global long/short account fade | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 109 | CG-11 | Net position change momentum | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 110 | ON-05 | NVT high fade | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 111 | ON-08 | LTH supply expansion | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 112 | ON-10 | Realized loss exhaustion | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 113 | NA-03 | Transfer value surge | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 114 | NA-04 | Fee spike fade | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 115 | EF-02 | Miner to exchange | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 116 | EF-04 | Stablecoin flow ⚠️ | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 117 | DV-02 | OI / market cap ratio | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 118 | DV-03 | Options OI put/call | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 119 | DV-04 | Vol term structure | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 120 | DV-05 | Perp vs spot volume | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 121 | GF-07 | Max pain pin ⚠️ | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 122 | IA-06 | Rates proxy trend | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 123 | IA-07 | Equity perp basket | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 124 | Q-01 | Accrual anomaly ⚠️ | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 125 | Q-02 | PEAD ⚠️ | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 126 | Q-03 | Dividend premium ⚠️ | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 127 | Q-04 | Short interest / retail options ⚠️ | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 128 | Q-05 | Crack spread / refiner lag ⚠️ | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 129 | Q-07 | 0DTE intraday vol ⚠️ | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
| 130 | Q-10 | Margin debt risk-off ⚠️ | 0.00 | 0.0% | 0.0% | 0 | skipped | SKIP |
