# Market-neutral correlation-regime portfolio

Dollar-neutral L/S book using correlation-regime insights. Baskets fixed from IS study; OOS is post-2025.

## Primary portfolio (liquid majors, regime_flip)

- **Long (dispersion winners):** SOLUSDT, AVAXUSDT, DOGEUSDT, NEARUSDT, RUNEUSDT, BNBUSDT, EGLDUSDT, QTUMUSDT, ZECUSDT, ENJUSDT
- **Short (cluster beneficiaries):** BELUSDT, SUPERUSDT, BIGTIMEUSDT, TNSRUSDT, C98USDT, MTLUSDT, LQTYUSDT, KASUSDT, MEWUSDT, ARKUSDT
- **Rules:** Q1–Q2 → long dispersion / short cluster; Q4–Q5 → reversed; Q3 → flat
- **Neutrality:** 50% gross long + 50% gross short when active; ~0 BTC beta

| Segment | Sharpe | CAGR | Max DD |
|---------|--------|------|--------|
| Full | 1.52 | 47.6% | -38.9% |
| In-sample | 1.73 | 61.8% | -38.9% |
| Out-of-sample | 0.60 | 10.1% | -30.0% |

BTC beta: 0.051

## Higher-Sharpe variant: low_corr_only

Trade only in Q1–Q2 (low correlation); flat in Q3–Q5. Improves Sharpe by avoiding noisy high-corr flips.

| Segment | Sharpe | CAGR | Max DD |
|---------|--------|------|--------|
| Full | 1.81 | 48.7% | -29.6% |
| In-sample | 1.99 | 59.5% | -29.6% |
| Out-of-sample | 1.09 | 18.9% | -23.1% |

## Best Sharpe variant: low_corr + market depth gate

Trade Q1–Q2 only when % pairs above 90d SMA is above its expanding median.

| Segment | Sharpe | CAGR | Max DD |
|---------|--------|------|--------|
| Full | 1.86 | 37.5% | -12.7% |
| In-sample | 1.92 | 44.8% | -12.7% |
| Out-of-sample | 2.39 | 16.6% | -2.7% |

## Exports

- Log equity: `charts/mn_equity_curve.png`
- **Linear equity:** `charts/mn_equity_curve_linear.png`
- **Linear CSV (best variant):** `artifacts/mn_equity_curve_linear.csv`
- Linear CSV (low_only): `artifacts/mn_equity_curve_low_only.csv`
- Sharpe sweep: `artifacts/sharpe_enhancement_sweep.json`
- **vs BTC linear:** `charts/recommended_vs_btc_linear.png`
- **vs BTC log:** `charts/recommended_vs_btc_log.png`
- **vs BTC CSV:** `artifacts/recommended_vs_btc.csv`

## IS-optimized basket variant (regime_flip)

| Segment | Sharpe | CAGR | Max DD |
|---------|--------|------|--------|
| In-sample | 1.09 | 25.2% | -19.1% |
| Out-of-sample | -0.93 | -17.5% | -35.7% |

![Equity curve](charts/mn_equity_curve.png)
