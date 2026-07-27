# Walk-forward top-10 IBS + RSI — Binance USDT-M

**Run:** pullback_mr_jul2026  
**Universe:** Top 100 liquid USDT perpetuals per fold (from Binance futures daily)  
**WF:** 18m rolling IS → 3m OOS, first OOS 2021-07-01  
**Selection:** Global top 10 (asset × oversold × IBS) by in-sample Sharpe, min 12 IS trades  
**Portfolio:** Equal weight (10% per sleeve)  
**Stats below:** stitched OOS only (21 folds)

## OOS performance (walk-forward stitched)

| Metric | Value |
|--------|-------|
| Sharpe | 0.48 |
| CAGR | 11.7% |
| Max DD | -52.5% |
| Total return | 79% |
| OOS days | 1918 |
| Period | 2021-07-01 → 2026-09-30 |

## Most selected assets (across folds)

| Asset | Times in top-10 |
|-------|-----------------|
| STXUSDT | 43 |
| CELRUSDT | 21 |
| SKLUSDT | 20 |
| ZROUSDT | 14 |
| FARTCOINUSDT | 13 |
| IMXUSDT | 10 |
| ARKMUSDT | 8 |
| BCHUSDT | 7 |
| DYDXUSDT | 7 |
| BATUSDT | 6 |
| TAOUSDT | 6 |
| ADAUSDT | 5 |
| ZECUSDT | 4 |
| AUCTIONUSDT | 4 |
| ENAUSDT | 4 |

## Artifacts

- `artifacts/wf_ibs_top10_summary.json` — fold details + combo frequencies
- `charts/wf_ibs_top10_oos_equity.png`
- `charts/wf_ibs_top10_oos_drawdown.png`
