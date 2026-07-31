# Walk-forward top-10 IBS + RSI — Binance USDT-M

**Run:** pullback_mr_jul2026  
**Universe:** Top 50 liquid USDT perpetuals per fold (from Binance futures daily)  
**WF:** 18m rolling IS → 3m OOS, first OOS 2021-07-01  
**Selection:** Global top 10 by in-sample Sharpe, min 25 IS trades, **one combo per asset (deduped)**  
**Portfolio:** Equal weight across selected sleeves (~10% each when 10 fill)  
**Stats below:** stitched OOS only (17 folds)

## OOS performance (walk-forward stitched)

| Metric | Value |
|--------|-------|
| Sharpe | 0.25 |
| CAGR | 2.7% |
| Max DD | -33.1% |
| Total return | 12% |
| OOS days | 1553 |
| Period | 2022-07-01 → 2026-09-30 |

## Most selected assets (across folds)

| Asset | Times in top-10 |
|-------|-----------------|
| UNIUSDT | 11 |
| DOTUSDT | 9 |
| DYDXUSDT | 8 |
| CRVUSDT | 8 |
| MASKUSDT | 7 |
| AAVEUSDT | 7 |
| RUNEUSDT | 6 |
| SNXUSDT | 5 |
| BCHUSDT | 5 |
| AVAXUSDT | 5 |
| ADAUSDT | 4 |
| ALICEUSDT | 4 |
| STXUSDT | 4 |
| XRPUSDT | 4 |
| XLMUSDT | 3 |

## Artifacts

- `artifacts/wf_ibs_top10_summary.json` — fold details + combo frequencies
- `charts/wf_ibs_top10_oos_equity.png`
- `charts/wf_ibs_top10_oos_drawdown.png`
