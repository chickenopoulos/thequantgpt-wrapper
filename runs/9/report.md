# Beta-hedged funding harvest

## Summary
Cross-sectional **short-only** funding carry on liquid alt perps, beta-hedged with BTC perp.
Long/short funding arbitrage was weak OOS; the short-high-funding sleeve dominates.

## Final configuration
- Signal: 7d mean daily funding (decimal), lag 1 bar
- Basket: top 15% highest funding, |f| ≥ 3e-05
- Liquidity: top 75 by open interest
- Beta hedge: 120d rolling β to BTCUSDT, per-leg
- Rebalance: every 5d

## Performance (OOS from 2025-01-01)

| Segment | Sharpe | CAGR | MaxDD | Days |
|---------|--------|------|-------|------|
| In-sample | 0.85 | 23.5% | -29.6% | 1737 |
| Out-of-sample | 1.35 | 46.2% | -19.4% | 326 |
| Full | 0.93 | 26.9% | -29.6% | 2063 |

## Calendar-year stability

| Year | Sharpe | CAGR | MaxDD |
|------|--------|------|-------|
| 2020 | 1.08 | 35.3% | -21.2% |
| 2021 | 0.15 | -1.5% | -27.6% |
| 2022 | 0.93 | 22.6% | -25.1% |
| 2023 | 0.75 | 17.2% | -24.1% |
| 2024 | 1.59 | 53.6% | -18.3% |
| 2025 | 1.35 | 46.2% | -19.4% |

## Research iterations
1. **Baseline L/S funding deciles + beta hedge** — OOS Sharpe 0.29, weak carry after costs.
2. **Fixed funding units** — Coinglass rates are percent; PnL uses /100 and 8h payment sums.
3. **Short-only sleeve** — materially stronger; shorts crowded longs in alts.
4. **Rejected**: carry-spread vs BTC, momentum filter, OI-weighted funding.
5. **Final params** — broader basket (15%), 120d β, top-75 liquidity.

## Risks
- OOS 2025 has been favorable for short-alts / long-BTC-hedge; IS/OOS gap varies by config.
- Funding regimes compress in bear markets; 2023 L/S baseline was flat.
- Single-exchange Binance data; basis/funding divergence vs other venues not modeled.

## Artifacts
- `code/data_core.py` — shared engine
- `code/beta_funding_enhancements.py` — variant tests
- `artifacts/enhancement_results.json`
- `charts/equity_curve.png`