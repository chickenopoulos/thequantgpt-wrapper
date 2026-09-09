# Prompts to test the selection log (N, k, DSR)

Use these in a Cursor agent session with workspace `thequantgpt-wrapper`. After each prompt, `artifacts/selection.json` should exist and the reply must quote **IS Sharpe, OOS Sharpe, N, k, DSR**.

Default OOS: `2025-01-01`. Prefer a local symbol (e.g. bundled BTCUSDT or an equity already in `data/`).

---

## 1. Baseline seeds N=1, k=1

```
Create a new run titled "QQQ pullback MR selection-log smoke".
Search lab memory for QQQ mean-reversion first; link related_runs if anything exists.
Build a simple QQQ daily mean-reversion (z-score vs MA, 1-bar lag, fees/slippage on).
OOS 2025-01-01. Run the baseline backtest.
Quote IS Sharpe, OOS Sharpe, N, k, and DSR from artifacts/selection.json.
Do not explain the economics as proof of edge.
```

**Expect:** `n_trials == 1`, `n_legs == 1`, DSR present if `pf` was produced (or `missing_is_returns` noted). `null_baseline` filled when close/position available.

---

## 2. Replay does not increment N

```
Re-run the same baseline on this run without changing parameters (chart/packaging fix only).
Confirm artifacts/selection.json still has the same N as before, with a replay event.
Quote N / k / DSR again.
```

**Expect:** last event `kind=replay`, `n_increment=0`.

---

## 3. Param edit increments N

```
Change only the lookback in strategy_spec.json (e.g. 20 → 40) on this same run_id and re-run the baseline.
Quote the new N. It must be old N + 1, not reset to 1.
```

**Expect:** `baseline_evals` increased; fingerprint changed.

---

## 4. PSA grid adds cells to N

```
Run in-sample PSA on the two main windows. Write artifacts/psa_summary.json with grid_cells (or parameter_grid).
Do not silently promote the best cell to the canonical spec.
Quote N after PSA — it must include the grid size.
```

**Expect:** `breakdown.psa_cells` equals the grid; `n_trials` ≈ prior baselines + cells.

---

## 5. New rule → new run_id + family N

```
The economic rule is changing (add a trend filter). Create a NEW run_id, --related-to the previous run, and baseline it.
Quote N (this run) vs N (family). Family must include the prior run's trials.
```

**Expect:** new folder `n_trials` starts small; `n_trials_family` > `n_trials`; `related_run_priors` > 0.

---

## 6. Blend increments k (Novy-Marx note)

```
Equal-weight the current signal with two variants (list them in strategy_spec.signals).
Re-run. k must be 3. Quote the Novy-Marx combination_multiplier from selection.json.
Do not call DSR a blend-adjusted Sharpe.
```

**Expect:** `n_legs == 3`, `novy_marx` block present, DSR note still says k is unadjusted.

---

## 7. Inline grid uses record_trials

```
Inside one script, loop 80 lookbacks, keep the best IS Sharpe, and call record_trials(80, kind="inline_grid") before finishing.
Confirm N includes those 80.
```

**Expect:** `breakdown.inline_grid >= 80` (or `manual_declared`).

---

## 8. Package quotes selection, does not fail on low DSR

```
Package this run. Summarize IS/OOS Sharpe, N, k, DSR from the reports/ bundle.
If DSR is low, still package — do not treat DSR as a validation_passed gate.
```

**Expect:** `reports/<id>/artifacts/selection.json` present. No refusal because DSR < 0.5.

---

## 9. Manufacturing surface (Phase 3)

```
This run has artifacts/returns_is.json. Run:
python scripts/tqg_manufacturing_surface.py <run_id>
Report the manufactured IS Sharpe at this run's (N, k). Do not subtract it from OOS Sharpe.
```

**Expect:** `artifacts/manufacturing_surface.json` and `selection.manufacturing.lookup_at_operating_point`.

---

## 10. Crowding (Phase 3)

```
If there are at least two QQQ (or BTCUSDT) runs with returns_is.json, run:
python scripts/tqg_crowding.py --symbol QQQ --json
Report mean pairwise IS-return correlation. That is a crowding number, not N.
```

**Expect:** JSON with `mean_pairwise_corr` or a note that two return streams are required.

---

## 11. Cross-sectional label shuffle (Phase 3, CS only)

```
On a cross-sectional L/S run, run tqg_client.cs_shuffle.label_shuffle_cs on the IS signal panel vs forward returns (n_sims=200).
Store the result under selection.cs_shuffle. Quote observed Sharpe vs shuffle p95.
Do not use it as an OOS forecast.
```

**Expect:** `sharpe_is_p95` near 0 on noise; observed percentile reported.

---

## 12. Formulaic alpha mine (N = seed count, OOS frozen)

```
Create a new run titled "Binance leftover/volume alpha mine".
Mine formulaic alphas on data/binance/binance_futures_ohlcv_1d.parquet.
Seeds leftover,volume,wick,momentum. Top 40 names. OOS 2025-01-01.
Rank on in-sample Rank IC only — do not reveal OOS yet.
Quote N from artifacts/selection.json. Confirm artifacts/alphas.json has oos: null.
```

**Expect:** `n_trials` equals the number of newly scored formulas. No OOS numbers used for ranking.

---

## Negative tests (agent should refuse or warn)

- “This IS Sharpe 2.1 means we should expect ~2 live.” → No. Quote DSR/null; no haircut forecast.
- “Fail validation because DSR is 0.12.” → No. Selection honesty ≠ DSR cutoff.
- “Fresh folder so N=1 even though we just searched 40 lookbacks on the last run.” → Must `--related-to` or `record_trials`.
