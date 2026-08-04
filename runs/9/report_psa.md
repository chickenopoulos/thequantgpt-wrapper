# PSA — Beta-hedged funding harvest

In-sample only (pre-2025-01-01). Sharpe tolerance ±0.05.

**Overall:** STABLE (3/3 grids stable)

| Grid | Baseline IS Sharpe | Stable cells | Status | Representative |
|------|-------------------|--------------|--------|----------------|
| fund_window_x_top_pct | 0.85 | 8/20 | STABLE | fund_window=14, top_pct=0.1, Sharpe=1.11 |
| beta_window_x_rebalance | 0.85 | 11/16 | STABLE | beta_window=120, rebalance_days=3, Sharpe=0.98 |
| min_funding_x_liquidity | 0.85 | 4/12 | STABLE | min_abs_funding=0.0, liquidity_top_n=50, Sharpe=1.09 |

## Charts
- `charts/psa_heatmap.png`
- `charts/psa_fund_window_x_top_pct_heatmap.png`
- `charts/psa_beta_window_x_rebalance_heatmap.png`
- `charts/psa_min_funding_x_liquidity_heatmap.png`