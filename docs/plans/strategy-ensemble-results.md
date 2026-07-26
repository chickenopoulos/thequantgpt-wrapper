# Strategy Catalog — Per-Asset Ensemble Results

> **Generated:** 2026-07-26 17:47 UTC via `scripts/tqg_strategy_ensemble_sweep.py`  
> **Method:** equal-weight mean of daily positions (−1…+1), clipped, across catalog strategies trading the same asset  
> **Costs:** fee 4.5bps + slip 5bps on position changes  
> **Ensembles:** 5 assets with ≥2 strategies

| Asset | Interval | N Strats | Sharpe | IS Sharpe | OOS Sharpe | MaxDD | CAGR | Trades |
|-------|----------|----------|--------|-----------|------------|-------|------|--------|
| ETHUSDT | 1d | 4 | 1.08 | 1.30 | 0.12 | -41.1% | 39.0% | 1337 |
| BTCUSDT | 1d | 66 | 0.92 | 1.13 | -0.07 | -32.1% | 15.4% | 2112 |
| GLD | 1d | 2 | 0.52 | 0.29 | 2.36 | -30.5% | 5.6% | 623 |
| SPY | 1d | 5 | 0.16 | 0.15 | 0.42 | -23.2% | 0.8% | 4262 |
| BTCUSDT | 1h | 4 | -1.06 | -1.04 | -1.49 | -62.2% | -10.6% | 4202 |

## Strategies per ensemble

### ETHUSDT (1d) — 4 strategies
T-13, IA-01, IA-08, IA-10

### BTCUSDT (1d) — 66 strategies
CG-01, CG-02, CG-03, CG-04, CG-05, CG-06, CG-07, CG-08, CG-09, CG-12, CG-13, CG-14, CG-15, CG-16, CG-17, CG-18, CG-20, MR-01, MR-02, MR-03, MR-04, MR-06, MR-10, MR-11, MR-14, TAA-07, T-01, T-02, T-03, T-04, T-05, T-06, T-07, T-08, T-09, T-10, V-03, V-07, V-08, DV-01, EF-01, EF-03, GF-01, GF-02, GF-03, GF-04, GF-05, GF-08, GF-09, GF-10, IA-02, IA-03, IA-04, IA-05, NA-01, NA-02, NA-05, ON-01, ON-02, ON-03, ON-04, ON-06, ON-07, ON-09, Q-08, Q-09

### GLD (1d) — 2 strategies
TAA-06, T-15

### SPY (1d) — 5 strategies
MR-07, MR-08, TAA-01, TAA-02, TAA-05

### BTCUSDT (1h) — 4 strategies
MR-05, MR-12, MR-13, T-11
