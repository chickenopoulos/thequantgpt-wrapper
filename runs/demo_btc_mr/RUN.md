# BTC mean reversion

**Run ID:** demo_btc_mr
**Created:** 2026-07-13T18:00:00+00:00
**Root:** `runs/demo_btc_mr`

## Strategy definition

```json
{
  "workflow": "single_asset_signals",
  "strategy_type": "MEAN_REVERSION",
  "symbol": "BTCUSDT",
  "oos_start_ts": "2025-01-01",
  "params": {
    "z_window": 30,
    "ma_window": 90,
    "entry_z": 1.5
  }
}
```

## Artifacts

- `artifacts/metrics.json`

## Charts

- `charts/drawdown.png`
- `charts/equity_curve.png`

## Code

- `code/btc_mean_reversion.py`
