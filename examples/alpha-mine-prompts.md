# Formulaic alpha mining — example prompts

Use when you have a **universe panel** and a qualitative idea, not a named single-asset rule.

Requires the skill `tqg-alpha-mine` and `python scripts/tqg_alpha_mine.py`.

## Turn 1 — seeds (IS only)

```text
I have the Binance USDT-M daily panel in data/binance/binance_futures_ohlcv_1d.parquet.
I don’t have a rule. Mine formulaic alphas that are not just momentum.
Bias toward leftover mean reversion and volume-price confirmation.
OOS from 2025-01-01. Rank on in-sample Rank IC only. Keep the top 50 names by IS dollar volume.
```

Expect: a run folder, `artifacts/alphas.json` with `oos` null, a leaderboard, N = number of seeds.

## Turn 2 — steer

```text
Kill anything that is just lagged returns / tagged momentum_like.
Keep leftover and divergence. Neutralize with cs_demean (no sector map on this panel).
```

## Turn 3 — one mutation, then OOS

```text
Mutate the volume-divergence family once (windows 10, 20, 40), then stop fishing.
Do not promote the max in-sample child. Show OOS on a two-formula book of leftover + divergence.
```

## Turn 4 — package

```text
Package this run. If OOS Rank IC is dead, tag verdict no_edge.
```

## Custom formulas

Write `runs/<id>/inputs/alphas.json`:

```json
[
  {"id": "A01", "expr": "cs_zscore(intra)", "description": "Intraday leftover"},
  {"id": "A02", "expr": "-cs_zscore(ts_corr(close, volume, 20))", "description": "Price-volume divergence"}
]
```

Then: `python scripts/tqg_alpha_mine.py <run_id> --panel <parquet> --formulas runs/<id>/inputs/alphas.json`.
