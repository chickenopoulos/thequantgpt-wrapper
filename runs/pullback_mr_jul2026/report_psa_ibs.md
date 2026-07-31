# PSA — normalized IBS + RSI (cross-asset)

**Run:** pullback_mr_jul2026  
**Sample:** in-sample only (before 2025-01-01)  
**Grid:** oversold [5.0, 8.0, 10.0, 12.0, 15.0, 18.0, 20.0] × ibs_thr [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55]  
**Stability:** Sharpe ≥ baseline−0.05, PF ≥ 1.2, ≥50 equity / ≥25 crypto trades, ≥5 plateau cells

## Stable representative per asset

| Asset | Stable? | Baseline in plateau? | Plateau cells | Rec. oversold | Rec. IBS | Rec. Sharpe | Rec. PF |
|-------|---------|----------------------|---------------|---------------|----------|-------------|---------|
| QQQ | Yes | Yes | 29 | 10 | 0.20 | 0.77 | 3.46 |
| SPY | Yes | Yes | 42 | 15 | 0.35 | 0.65 | 2.08 |
| IWM | Yes | Yes | 36 | 10 | 0.25 | 0.46 | 1.71 |
| GLD | No | No | 0 | — | — | — | — |
| BTC | Yes | No | 40 | 5 | 0.20 | 0.54 | 2.18 |
| ETH | Yes | No | 10 | 20 | 0.35 | 0.36 | 1.31 |

## Baseline params (oversold=10, ibs_thr=0.45) in-sample

| Asset | Sharpe | PF | Trades | Win% | CAGR |
|-------|--------|-----|--------|------|------|
| QQQ | 0.79 | 2.39 | 364 | 73% | 11.8% |
| SPY | 0.58 | 1.88 | 446 | 72% | 5.5% |
| IWM | 0.23 | 1.24 | 330 | 67% | 2.2% |
| GLD | -0.23 | 0.79 | 250 | 57% | -2.3% |
| BTC | 0.27 | 1.16 | 105 | 67% | 2.0% |
| ETH | 0.21 | 1.09 | 105 | 70% | -3.7% |

Charts: `charts/psa_ibs_heatmap.png`, `charts/psa_ibs_<symbol>_heatmap.png`
