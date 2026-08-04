# Beta-hedged funding harvest

**Run ID:** 9  
**Root:** `runs/9`

## Strategy

Short alt perps with the highest smoothed funding (receive carry from crowded longs), hedge BTC beta with `BTCUSDT` perp.

## Run

```bash
cd /root/thequantgpt-wrapper && source .venv/bin/activate
python scripts/tqg_run_backtest.py 9 --code code/beta_funding_harvest.py
```

## Research scripts

| Script | Purpose |
|--------|---------|
| `code/data_core.py` | Data loading, beta hedge PnL engine |
| `code/beta_funding_harvest.py` | Final backtest + artifacts |
| `code/beta_funding_enhancements.py` | Variant experiments (L/S, filters, signals) |
| `code/beta_funding_short_sweep.py` | Short-only parameter sweep |

## OOS

Default `2025-01-01` (see `strategy_spec.json`).
