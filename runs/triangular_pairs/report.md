# Triangular pairs — deep-dive champion

## Selection (IS only — OOS never used for tuning)

Screened **114 variants** across:
- 108 daily-static param combos (cached IS discovery)
- 5 hourly-exec + 6 hourly-native configs

**Hourly and hourly-native variants scored negative IS composite** (failed walk-forward fold stability). Daily static dominates.

Fine PSA (36 configs around winner) confirmed: `window=120, entry_z=2.5, exit_z=0.5, weight_cap=0.15`.

## Champion: `daily_static`

```json
{
  "n_triangles": 10,
  "window": 120,
  "entry_z": 2.5,
  "exit_z": 0.5,
  "weight_cap": 0.15,
  "adf_max": 0.05
}
```

### Triangles (10)
- SFPUSDT|BTCUSDT|BNBUSDT
- SFPUSDT|BNBUSDT|SOLUSDT
- SFPUSDT|BTCUSDT|ETHUSDT
- SFPUSDT|BTCUSDT|SOLUSDT
- DOGEUSDT|BNBUSDT|SOLUSDT
- DOGEUSDT|ETHUSDT|SOLUSDT
- DOGEUSDT|BTCUSDT|BNBUSDT
- DOGEUSDT|BTCUSDT|SOLUSDT
- SFPUSDT|ETHUSDT|BNBUSDT
- SFPUSDT|ETHUSDT|SOLUSDT

## Performance

| Segment | Sharpe | CAGR | MaxDD |
|---------|--------|------|-------|
| In-sample | 0.637 | 11.27% | -29.38% |
| **Out-of-sample** | **1.658** | **9.28%** | **-3.20%** |
| Full | 0.673 | 10.79% | -29.38% |

## IS robustness

| Test | Sharpe |
|------|--------|
| Baseline IS | 0.637 |
| +1 bar lag shift | 0.637 |
| Cost stress (+1bp turnover) | 0.636 |
| Bootstrap IS p5/median/p95 | -0.04 / 0.65 / 1.30 |
| Walk-forward min fold | 0.461 |

### IS yearly Sharpe
- 2021: 0.98
- 2022: 0.75
- 2023: 0.90
- 2024: 0.46

## Variants considered but not selected

| Variant | Why rejected |
|---------|-------------|
| Hourly exec / hourly native | Negative IS composite; walk-forward folds unstable |
| Daily rolling 180D | Lower IS composite (0.42945943595131875) vs static |
| Layered refresh (hourly) | IS Sharpe 0.46 vs 0.64; refreshes fire only in OOS; not IS-validated |

## Optional OOS booster (not canonical)

Hourly layered refresh with same params achieved OOS Sharpe **2.67** vs static **1.66**, but IS Sharpe is **0.46** and refresh rules never triggered in-sample. Treat as experimental overlay, not the robust core.

Research only — not live trading advice.
