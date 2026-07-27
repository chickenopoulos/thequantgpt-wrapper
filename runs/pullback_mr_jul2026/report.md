# Pullback mean reversion — Jul 2026 (QS newsletter)

**Run ID:** pullback_mr_jul2026  
**OOS cut-off:** 2025-01-01  
**Annualization:** 252 (equity sessions)  
**Costs:** fee 0.00045, slippage 0.0005

Two single-asset mean reversion strategies inferred from Quantified Strategies newsletter stats and public QS articles. Paywalled Pine Script rules were not available; parameters were calibrated against published full-sample benchmarks.

---

## Strategy 1: SPY RSI drop

**Symbol:** SPY (single asset only)  
**Data:** yfinance:SPY

### Calibrated rules

1. **Trend filter:** close > SMA(200) and close > SMA(50)
2. **Entry:** RSI(2) < 3.0 (RSI must cross below threshold)
3. **Exit:** close > SMA(10)
4. **Sizing:** 30% of equity per trade; fees 0.00045, slippage 0.0005

**Initial inference:** RSI(2) < 10, close > SMA(200), exit RSI(2) > 65 (10% sizing).  
**Inferred-only full sample:** 697 trades, 64.8% win, PF 1.17, CAGR 0.15%.

### Full sample vs article

| Metric | Lab backtest | Article |
|--------|--------------|---------|
| Trades | 233 | 244 |
| Win rate | 77.3% | 81.0% |
| Profit factor | 1.61 | 3.60 |
| Avg gain/trade | 0.26% | 0.70% |
| CAGR | 0.53% | 5.10% |
| Max DD | -12.6% | -14.0% |
| Exposure | 17.3% | 12.0% |
| Risk-adj return | 3% | 42% |

### In-sample / OOS (SPY)

| Segment | Sharpe | CAGR | MaxDD | Trades | Win rate | PF |
|---------|--------|------|-------|--------|----------|-----|
| In-sample | 0.25 | 0.50% | -12.6% | 220 | 77% | 1.61 |
| OOS | 0.58 | 1.12% | -2.5% | 13 | 77% | 1.68 |

---

## Strategy 2: QQQ normalized IBS + RSI

**Symbol:** QQQ (single asset only)  
**Data:** yfinance:QQQ

### Calibrated rules

1. **IBS:** (close - low) / (high - low); normalized IBS = 2-day average
2. **Entry:** RSI(3) < 15.0 AND normalized IBS < 0.4
3. **Exit:** close > prior day high
4. **Sizing:** 100% of equity per trade; fees 0.00045, slippage 0.0005

**Initial inference:** RSI(3) < 10, 2-day avg IBS < 0.1, exit close > prior day high (10% sizing).  
**Inferred-only full sample:** 67 trades, 68.7% win, PF 2.86, CAGR 0.34%.

### Full sample vs article

| Metric | Lab backtest | Article |
|--------|--------------|---------|
| Trades | 385 | 393 |
| Win rate | 72.5% | 72.0% |
| Profit factor | 2.29 | 2.00 |
| Avg gain/trade | 0.82% | 0.80% |
| CAGR | 11.45% | 11.20% |
| Max DD | -25.0% | -25.0% |
| Exposure | 30.0% | 22.0% |
| Risk-adj return | 38% | 50% |

### In-sample / OOS (QQQ)

| Segment | Sharpe | CAGR | MaxDD | Trades | Win rate | PF |
|---------|--------|------|-------|--------|----------|-----|
| In-sample | 0.77 | 11.50% | -25.0% | 366 | 72% | 2.30 |
| OOS | 0.79 | 10.76% | -11.1% | 19 | 79% | 2.18 |

---

## Notes

- SPY article stats (244 trades, 81% win, PF 3.6) likely include a paywalled extra filter; public QS RSI-on-SPY articles report ~470 trades at 75% win.
- QQQ calibration required a looser normalized IBS threshold than the 0.10 inference to approach 393 trades; 100% position sizing aligns CAGR with the article.
- Segment exposure is computed from trade durations within each return window.

## Artifacts

| File | Description |
|------|-------------|
| `artifacts/metrics.json` | Combined metrics + calibration |
| `artifacts/spy_rsi_drop_metrics.json` | SPY-only metrics |
| `artifacts/qqq_norm_ibs_rsi_metrics.json` | QQQ-only metrics |
| `charts/spy_rsi_drop_equity_curve.png` | SPY equity vs B&H |
| `charts/qqq_norm_ibs_rsi_equity_curve.png` | QQQ equity vs B&H |
| `strategy_spec.json` | Rules and calibrated parameters |
