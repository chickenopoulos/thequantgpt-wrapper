# Run 5 — BTC Five-Strategy Ensemble

**Symbol:** BTCUSDT (daily, one symbol only)  
**OOS:** 2025-01-01  
**Status:** baseline_complete

## Execute

```bash
cd /root/thequantgpt-wrapper && source .venv/bin/activate
PYTHONPATH=. python runs/5/code/btc_five_strategy_ensemble.py
```

## Outputs

- `report.md` — summary and strategy definitions
- `artifacts/btc_five_strategy_ensemble.json` — full metrics payload
- `artifacts/metrics.json` — IS/OOS metrics
- `charts/ensemble_equity.png`, `charts/strategy_equities.png`
