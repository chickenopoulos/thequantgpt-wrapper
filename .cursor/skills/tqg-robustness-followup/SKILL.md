---
name: tqg-robustness-followup
description: >-
  Run one robustness test (PSA, cost stress, Monte Carlo, signal shift) as a
  follow-up on an existing strategy run. Use after baseline_complete.
---

# Robustness follow-up

**One robustness test per user message.** Read `runs/<run_id>/run.json` first.

## Preconditions

- `status` is `baseline_complete` or later, OR `artifacts.metrics` exists
- Do not change canonical parameters unless the user explicitly asks

## Workflow

1. Load `run.json` and `strategy_spec.json`.
2. Call **`tqg_get_guidance`** with the user request + `run_context_json`.
3. Call **`tqg_get_robustness_spec`** with:
   - `user_request` — user's robustness request
   - `run_context_json` — from `run.json`
   - `test_name` — leave empty to infer (e.g. `parameter_sensitivity` for PSA)
4. Implement code under `runs/<run_id>/code/` (new file e.g. `psa.py` is fine).
5. Run: `python scripts/tqg_run_backtest.py <run_id> --code code/psa.py`
6. Optionally: `python scripts/tqg_mcp_validate.py <run_id>`
7. Save outputs to `artifacts/` and `charts/` per the spec's `expected_outputs`.

## PSA rules

- **In-sample only** (before `oos_start_ts`) unless user explicitly overrides
- Reuse baseline signal logic; vary only named parameters
- Save `artifacts/psa_summary.json` and `charts/psa_heatmap.png` for 2D grids

## Reply

- Which test was run
- Stable region / representative params (for PSA)
- Paths to new artifacts and charts
