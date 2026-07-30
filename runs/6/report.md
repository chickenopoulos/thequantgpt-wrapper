# BTC Higher-Frequency Low-Correlation Ensemble — Run 6

**Symbol:** BTCUSDT (single asset)  
**OOS cut-off:** 2025-01-01  
**Costs:** 4.5 bps fee + 5 bps slippage per turnover  
**Lag:** 1 bar on all signals; alt-data via `align_to_close`

## Objective

Find Bitcoin strategies that:
1. Trade more frequently than the daily run-5 sleeves
2. Achieve **equal-weight ensemble Sharpe ≥ 2.0** and **max DD < 15%**
3. Have **no signal/style overlap** and low return correlation

## Result: target not fully met

After sweeping **66 sleeves** across **2h / 4h / 6h / 8h / 12h** OHLCV plus the five validated daily alt-data sleeves from run 5, the best **cluster-unique** equal-weight ensemble is:

| Metric | Value | Target |
|--------|-------|--------|
| Sharpe (full) | **1.81** | ≥ 2.0 |
| Max DD | **−15.3%** | < −15% |
| Max pairwise corr | **0.41** | < 0.30 ideal |
| Avg trades/year | **14.7** | > daily (~5–10/sleeve) |
| HF sleeves | **3 of 5** | — |

IS/OOS: see `artifacts/hf_ensemble_result.json`.

## Selected ensemble (5 sleeves, equal weight)

| ID | Interval | Cluster | Family | Sharpe | Trades/yr |
|----|----------|---------|--------|--------|-----------|
| daily_S1 | 1d | quantile_alt | Talos flow quantile | 1.52 | 24 |
| daily_S4 | 1d | liquidation | Coinglass liq fade | 1.06 | 12 |
| rsi_lo_8h_20_0.08 | 8h | rsi_mr | RSI pullback + 8% trail | 1.25 | 5 |
| ermom_4h_40_0.08 | 4h | momentum | ER regime + mom trail | 1.16 | 5 |
| vspike_8h_96 | 8h | vol_spike | Volume spike fade | 0.78 | 28 |

**Qualitative diversity:** one quantile alt-data sleeve, one liquidation sleeve, three intraday OHLCV sleeves (MR, momentum, microstructure). Only one quantile strategy included.

**Correlation matrix (daily returns):**

| | S1 | S4 | RSI 8h | ER mom 4h | Vol spike |
|--|-----|-----|--------|-----------|-----------|
| S1 | 1.00 | 0.20 | 0.22 | 0.26 | 0.10 |
| S4 | | 1.00 | 0.18 | 0.27 | 0.14 |
| RSI 8h | | | 1.00 | **0.41** | 0.04 |
| ER mom | | | | 1.00 | 0.04 |
| Vol spike | | | | | 1.00 |

The RSI↔momentum pair at 0.41 is the binding correlation; removing either drops ensemble Sharpe below 1.7.

## Why Sharpe 2+ was not reached

1. **Transaction costs:** 9.5 bps round-trip dominates on 4h/8h sleeves with 30–50 trades/year. Pure 1h OHLCV grids produced **zero** qualifying sleeves at lab costs.
2. **Coinglass 1h alt-data:** only ~5 months of history (Jun–Nov 2025) — insufficient for full-sample HF derivatives search.
3. **Alpha concentration:** the highest-Sharpe intraday sleeves are RSI mean-reversion variants (same economic idea). Forcing cluster diversity caps single-sleeve Sharpe.
4. **Daily alt-data still carries the book:** removing daily_S1 drops ensemble Sharpe to ~1.4 despite higher trade frequency from HF sleeves.

## Files

- `code/btc_hf_data.py` — lag-safe 1h/4h feature loader
- `code/btc_hf_search.py` / `btc_hf_search_v2.py` — grid searches
- `code/btc_hf_ensemble.py` — canonical ensemble builder
- `artifacts/hf_ensemble_result.json` — metrics
- `charts/hf_ensemble_equity.png` — equity curve

## Reproduce

```bash
cd /root/thequantgpt-wrapper && source .venv/bin/activate
PYTHONPATH=/root/thequantgpt-wrapper python runs/6/code/btc_hf_ensemble.py
```
