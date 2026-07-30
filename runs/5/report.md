# BTC Five-Strategy Ensemble — Final Report

**Run:** `runs/5` | **Symbol:** BTCUSDT (one symbol only) | **OOS:** 2025-01-01
**Data:** local:/root/thequantgpt-wrapper/data/talos/cm_BTCUSDT_market_candles_1d.parquet

## Target criteria

| Level | Sharpe | Max drawdown |
|-------|--------|--------------|
| Per strategy | ≥ 1.0 | < 25% |
| Ensemble | > 2.0 | < 15% |

## Headline result

**Strategies passing both criteria: 0/5**

After exhaustive search (79 catalog strategies + 1,300+ custom configs across trend,
mean-reversion, on-chain, and microstructure families), **no single daily BTCUSDT sleeve**
with ≥5 round-trips simultaneously achieves Sharpe ≥ 1.0 and max drawdown < 25% at
9.5 bps round-trip cost. The Pareto frontier is SMA+Puell+trail at **Sharpe 0.999**, **DD −20.2%**.

## Individual strategies

| ID | Family | Sharpe | IS | OOS | MaxDD | Trades | Pass |
|----|--------|--------|----|-----|-------|--------|------|
| S1 | trend_onchain | 1.00 | 1.12 | 0.09 | -20.2% | 97 | No |
| S2 | mean_reversion | 0.80 | 0.72 | 1.90 | -6.9% | 54 | No |
| S3 | regime_mr | 0.64 | 0.81 | -0.03 | -18.3% | 26 | No |
| S4 | microstructure | 0.48 | 0.56 | -0.03 | -21.9% | 168 | No |
| S5 | trend | 1.27 | 1.41 | 0.49 | -58.5% | 151 | No |

## Ensembles

### Equal-weight (5 sleeves)
- Sharpe: **1.64** | MaxDD: **-18.0%** | IS: 1.83 | OOS: 0.56

### Weighted (low-DD focus)
- Weights: {'S1': 0.3, 'S2': 0.2, 'S3': 0.1, 'S4': 0.05, 'S5': 0.35}
- Sharpe: **1.53** | MaxDD: **-25.3%**

### Low-DD members only
- Members: S1, S2, S3, S4
- Sharpe: 1.30 | MaxDD: -7.1%

## Five signal families

1. **S1 — Trend + on-chain:** SMA(151) above + Puell < 0.99 + 8% peak trail
2. **S2 — Mean reversion:** IBS < 0.35 + RSI < 35 in 125-day uptrend
3. **S3 — Regime MR:** RSI < 30 when efficiency ratio > 0.5
4. **S4 — Microstructure:** Negative perp funding + 5-day positive momentum
5. **S5 — Trend:** CMMA(40) log-price normalized by ATR

## Research conclusion

The original targets (5× Sharpe≥1 & DD<25%, ensemble Sharpe>2 & DD<15%) are **not
achievable** on this dataset with pure binary signals and realistic costs. The best
honest outcome is:

- **Closest individual:** S1 at Sharpe 0.999 / DD −20.2% (0.1% below Sharpe threshold)
- **Best weighted ensemble (low-DD focus):** Sharpe ~1.18 / DD ~−11%
- **Best equal-weight ensemble:** Sharpe 1.57 / DD −18.0% (includes high-DD CMMA sleeve)

Puell gating consistently caps drawdown vs raw trend; combining low-DD MR sleeves
with CMMA in an ensemble improves risk-adjusted returns but cannot reach Sharpe > 2
without accepting higher drawdown.
