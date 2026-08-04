# Enhancement experiments

| Variant | OOS Sharpe | OOS CAGR | OOS MaxDD |
|---------|------------|----------|-----------|
| short_only | 2.43 | 124.3% | -20.5% |
| short_only+mom | 2.03 | 85.2% | -20.5% |
| baseline | 0.29 | 3.6% | -44.7% |
| regime_gate | 0.29 | 3.6% | -44.7% |
| carry_spread_signal | 0.05 | -5.4% | -41.9% |
| carry_spread+gate | 0.05 | -5.4% | -41.9% |
| momentum_filter | -0.17 | -14.8% | -45.5% |
| carry_spread+mom | -0.40 | -21.0% | -41.4% |
| oi_weighted_funding | -1.00 | -51.1% | -59.7% |

**Best:** short_only (OOS Sharpe 2.43)