# BTC HF Ensemble — Run 6 (v2, IS-only selection)

**Symbol:** BTCUSDT | **OOS cut-off:** 2025-01-01 | **Selection:** in-sample only

## Methodology change (v2)

All sleeve pooling, cluster representatives, correlation screening, and ensemble ranking use **in-sample metrics only** (pre-2025-01-01). OOS is reported **once** post-hoc and was **not** used in any selection or optimization.

v1 incorrectly ranked sleeves on full-sample Sharpe (leaky). v1 results are kept in `v1_fullsample_reference` for comparison only.

## IS-selected ensemble (4 sleeves, equal weight)

| ID | Interval | Cluster | IS Sharpe | OOS Sharpe (post-hoc) |
|----|----------|---------|-----------|------------------------|
| daily_S1 | 1d | quantile_alt | 1.76 | 0.25 |
| rsi_lo_8h_20_0.08 | 8h | rsi_mr | 1.50 | −0.74 |
| daily_S4 | 1d | liquidation | 1.36 | −0.89 |
| vspike_8h_96 | 8h | vol_spike | 0.87 | 0.23 |

### Ensemble metrics

| Segment | Sharpe | Max DD |
|---------|--------|--------|
| **In-sample (selection)** | **2.01** | **−20.2%** |
| Out-of-sample (validation) | −0.39 | −15.1% |
| Full sample | 1.71 | −20.2% |

- IS pairwise corr max: **0.22**
- Avg trades/year: **17.1**
- IS Sharpe target (≥2.0): **met**
- IS DD target (<15%): **not met**
- OOS validation: **failed** (Sharpe −0.39)

## Interpretation

IS-only discipline does not rescue OOS — the selected ensemble still degrades post-2025, driven by the same IS-strong / OOS-weak sleeves (S4 liq fade, RSI-8h MR). This is consistent with **in-sample overfitting** to pre-2025 regimes, not with OOS peeking.

Proper next steps (IS-only):
1. **PSA in-sample** on locked sleeves (one robustness test per turn)
2. **IS subperiod stability** — require positive Sharpe in multiple IS windows before inclusion
3. **Simpler sleeves** — fewer parameters, stronger priors
4. **Accept OOS failure** — do not re-tune after seeing OOS

## Reproduce

```bash
PYTHONPATH=/root/thequantgpt-wrapper python runs/6/code/btc_hf_ensemble.py
```
