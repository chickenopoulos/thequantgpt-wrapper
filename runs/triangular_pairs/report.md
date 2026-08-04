# Triangular pairs — baseline (IS-selected robust config)

## Selection
- Triangle universe: IS discovery only (pre-2025-01-01)
- Parameters: IS grid search ranked by **robust_score** (Sharpe + yearly stability + drawdown penalty)
- OOS segment: single holdout, **not used for tuning**

## Parameters
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

## Triangles (10)
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

## Metrics

| Segment | Sharpe | CAGR | MaxDD | Days |
|---------|--------|------|-------|------|
| Full | 0.673 | 10.79% | -29.38% | 2400 |
| In-sample | 0.637 | 11.27% | -29.38% | 1827 |
| **Out-of-sample** | **1.658** | **9.28%** | **-3.20%** | 573 |

## IS yearly Sharpe
- 2020: nan
- 2021: 0.98
- 2022: 0.75
- 2023: 0.90
- 2024: 0.46

## Caveats
- Multi-leg basket; ~0.29% round-trip cost at default assumptions
- Research only — not live trading advice

## vs prior research (OOS-tuned — not TQG-compliant)

The earlier `research/triangular-pairs-trading` "best" config was selected by **ranking grid sweeps on OOS Sharpe** (entry_z=3.0, exit_z=0.75, weight_cap=0.20), reporting OOS Sharpe 2.07 with full-sample Sharpe 0.49 — a classic selection-bias pattern.

| Config | Selection | IS Sharpe | OOS Sharpe | Full MaxDD | OOS MaxDD |
|--------|-----------|-----------|------------|------------|-----------|
| **IS-robust (this run)** | IS robust_score | 0.64 | **1.66** | -29.4% | **-3.2%** |
| Prior OOS-tuned | OOS Sharpe grid | ~0.49 | 2.07* | -35.3% | -2.3% |

\*OOS metric inflated by tuning on the holdout segment.

IS PSA (`charts/psa_heatmap.png`) shows a stable plateau at window 90–120 and entry_z 2.0–2.5; the selected (120, 2.5) sits in that region.

## Reproduce

```bash
cd /root/thequantgpt-wrapper && source .venv/bin/activate
python runs/triangular_pairs/code/is_param_sweep.py   # IS selection
python runs/triangular_pairs/code/baseline.py         # baseline + OOS holdout
python runs/triangular_pairs/code/psa.py              # IS PSA
python scripts/tqg_run_backtest.py triangular_pairs --code code/baseline.py
python scripts/tqg_package_artifacts.py triangular_pairs
```
