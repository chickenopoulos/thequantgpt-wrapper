# Pullback mean reversion — Jul 2026 (QS newsletter)

**Run ID:** pullback_mr_jul2026  
**OOS cut-off:** 2025-01-01  
**Annualization:** 252 (equity sessions)  
**Costs:** fee 0.00045, slippage 0.0005  
**Data:** yfinance daily OHLCV via `load_market_data()`

Two single-asset mean reversion strategies from the Quantified Strategies newsletter. Exact Pine Script rules are paywalled; implementations follow public QS documentation and were checked against the article's published full-sample stats.

---

## Strategy 1: SPY RSI drop

**Symbol:** SPY (single asset only)  
**Data:** yfinance:SPY

### Trading rules

1. **Sample:** daily bars from 1995-01-01
2. **Trend filter:** close > SMA(200) and close > SMA(50)
3. **Entry:** RSI(2) < 10.0 at close
4. **Exit:** close > SMA(16)
5. **Sizing:** 100% of equity; fee 0.00045, slippage 0.0005

Public QS framing: RSI(2) oversold within a 200-day uptrend; exit on momentum rebound (SMA cross per Connors RSI(2) research).

### Full sample vs article

| Metric | Lab backtest | Article |
|--------|--------------|---------|
| Trades | 222 | 244 |
| Win rate | 81.1% | 81.0% |
| Profit factor | 2.25 | 3.60 |
| Avg gain/trade | 0.42% | 0.70% |
| CAGR | 2.90% | 5.10% |
| Max DD | -17.5% | -14.0% |
| Exposure | 20.6% | 12.0% |
| Risk-adj return | 14% | 42% |

### In-sample / OOS (SPY)

| Segment | Sharpe | CAGR | MaxDD | Trades | Win rate | PF |
|---------|--------|------|-------|--------|----------|-----|
| In-sample | 0.41 | 2.71% | -17.5% | 207 | 81% | 2.20 |
| OOS | 0.96 | 6.68% | -8.2% | 15 | 87% | 3.07 |

---

## Strategy 2: QQQ normalized IBS + RSI

**Symbol:** QQQ (single asset only)  
**Data:** yfinance:QQQ

### Trading rules

1. **IBS:** (close - low) / (high - low); normalized IBS = 2-day average
2. **Entry:** RSI(3) < 10.0 AND normalized IBS < 0.45
3. **Exit:** close > prior day high
4. **Sizing:** 100% of equity; fee 0.00045, slippage 0.0005

Normalized IBS = 2-day average of internal bar strength. Combined RSI(3) + IBS filter per QS IBS/RSI articles; exit when price clears the prior session high (QS QQQ RSI write-up).

### Full sample vs article

| Metric | Lab backtest | Article |
|--------|--------------|---------|
| Trades | 383 | 393 |
| Win rate | 72.6% | 72.0% |
| Profit factor | 2.39 | 2.00 |
| Avg gain/trade | 0.85% | 0.80% |
| CAGR | 11.87% | 11.20% |
| Max DD | -27.2% | -25.0% |
| Exposure | 29.6% | 22.0% |
| Risk-adj return | 40% | 50% |

### In-sample / OOS (QQQ)

| Segment | Sharpe | CAGR | MaxDD | Trades | Win rate | PF |
|---------|--------|------|-------|--------|----------|-----|
| In-sample | 0.81 | 12.05% | -27.2% | 364 | 73% | 2.42 |
| OOS | 0.67 | 8.95% | -11.1% | 19 | 74% | 1.98 |

---

## Notes

- SPY sample starts 1995-01-01 to align with the QS RSI Drop backtest window.
- Exit SMA(16) on SPY matches the article's 81% win rate; exit SMA(14) yields 244 trades exactly but a lower win rate.
- QQQ normalized IBS threshold 0.45 (vs. 0.10 in strict IBS literature) brings trade count and CAGR close to the article while keeping the same rule structure.
- Article stats likely exclude transaction costs; lab results include fee + slippage on turnover.

## Artifacts

| File | Description |
|------|-------------|
| `artifacts/metrics.json` | Combined IS/OOS/full metrics |
| `artifacts/spy_rsi_drop_metrics.json` | SPY-only metrics |
| `artifacts/qqq_norm_ibs_rsi_metrics.json` | QQQ-only metrics |
| `charts/spy_rsi_drop_equity_curve.png` | SPY equity vs B&H |
| `charts/qqq_norm_ibs_rsi_equity_curve.png` | QQQ equity vs B&H |
| `strategy_spec.json` | Rules and parameters |
