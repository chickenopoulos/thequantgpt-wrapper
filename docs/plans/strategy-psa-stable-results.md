# Strategy PSA — Stable Plateau Results

> **Generated:** 2026-07-26 16:55 UTC via `scripts/tqg_strategy_psa_sweep.py`  
> **Sample:** in-sample only (before 2025-01-01)  
> **Stable criteria:** Sharpe ≥ baseline − 0.05, PF ≥ 1.2, trades ≥ spec min; ≥3 stable cells (2 for rare-event specs)  
> **Rep Sharpe:** plateau center (score = Sharpe + 0.25×PF), not grid peak  
> **Summary:** NO_STABLE: 46, SKIP: 64, STABLE: 20 — **20** strategies with stable regions

| Rank | ID | Strategy | Rep Sharpe | Rep PF | Rep Trades | Stable Cells | Rep Params | Universe | Asset Class |
|------|-----|----------|------------|--------|------------|--------------|------------|----------|-------------|
| 1 | T-13 | Network momentum hub | 1.64 | 7.37 | 49 | 6/6 | lookback=40 | ETHUSDT | crypto |
| 2 | Q-08 | Recursive LS proxy | 1.42 | 3.79 | 72 | 6/6 | window=30 | BTCUSDT | crypto |
| 3 | TAA-07 | Crypto vs equity rotation | 1.36 | 2.90 | 59 | 3/5 | spy_window=15 | BTC+SPY | multi-asset |
| 4 | CG-09 | Whale gate + trend | 1.29 | 4.51 | 50 | 4/6 | mom_window=40 | BTCUSDT | crypto |
| 5 | DV-01 | Funding trend | 1.03 | 7.53 | 10 | 3/5 | cum_window=21 | BTC | crypto |
| 6 | CG-03 | OI expansion breakout | 0.95 | 1.94 | 108 | 4/5 | oi_diff=14 | BTCUSDT | crypto |
| 7 | CG-17 | Basis carry | 0.89 | 2.31 | 78 | 3/5 | median_window=20 | BTCUSDT | crypto |
| 8 | CG-06 | Short squeeze setup | 0.87 | 2.78 | 50 | 5/5 | price_window=7 | BTCUSDT | crypto |
| 9 | MR-03 | RSI + ER gate | 0.87 | 74.59 | 11 | 4/5 | rsi_window=18 | BTCUSDT | crypto |
| 10 | ON-06 | SOPR capitulation | 0.85 | 5.17 | 23 | 3/5 | streak_min=6 | BTC | crypto |
| 11 | CG-05 | Liquidation cascade fade | 0.80 | 2.17 | 68 | 3/4 | spike_q=0.95 | BTCUSDT | crypto |
| 12 | V-03 | Vol regime switch | 0.76 | 3.29 | 30 | 3/4 | vol_window=120 | BTCUSDT | crypto |
| 13 | IA-08 | ETH/BTC rotation | 0.74 | 1.82 | 81 | 3/5 | mom_window=20 | ETHUSDT | crypto |
| 14 | CG-08 | Orderbook imbalance | 0.66 | 1.92 | 62 | 4/5 | entry_imb=0.05 | BTCUSDT | crypto |
| 15 | TAA-01 | Faber 10M SMA | 0.65 | 4.11 | 81 | 4/5 | ma_window=250 | SPY | equity |
| 16 | MR-11 | RSI on detrended | 0.63 | 1.33 | 248 | 3/5 | detrend_window=15 | BTCUSDT | crypto |
| 17 | Q-09 | Regime overlay proxy | 0.60 | 1.79 | 50 | 4/5 | mom_window=40 | BTCUSDT | crypto |
| 18 | TAA-05 | Bond filter equities | 0.57 | 2.48 | 196 | 5/5 | bond_window=40 | SPY+TLT | equity |
| 19 | MR-15 | QQQ RSI MR | 0.47 | 1.96 | 194 | 5/5 | rsi_window=5 | QQQ | equity |
| 20 | CG-01 | Funding carry | 0.41 | 1.30 | 128 | 5/5 | fund_thr=-3e-05 | BTCUSDT | crypto |
