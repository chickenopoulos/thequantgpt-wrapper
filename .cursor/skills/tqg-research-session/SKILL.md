---
name: tqg-research-session
description: >-
  Run an asset-class-agnostic OHLCV strategy research session in TheQuantGPT Cursor Lab.
  Use when the user asks to build, backtest, validate, iterate, or package
  a rule-based strategy under runs/ (crypto, equities, FX, bonds, metals, etc.).
---

# TheQuantGPT research session

You orchestrate the workflow. MCP tools provide **hints** and **validation** — not mandatory step lists.

## Before coding

1. Inspect `data/README_DATA_FORMAT.md` and list files under `data/`.
2. **Search lab memory** for prior work on the same symbol / idea (required before a new baseline):
   ```bash
   python scripts/tqg_search_runs.py --symbol <SYMBOL> --text "<idea>" --json
   # or compact MCP context:
   python scripts/tqg_lab_context.py --symbol <SYMBOL> --limit 10
   ```
   If matches exist (especially `verdict: no_edge` / `killed`), summarize and ask whether to **extend** that run or start fresh. Link variants with `--related-to`.
3. Create or open the active run:
   ```bash
   python scripts/tqg_create_run.py --title "<short title>"
   ```
4. Read `runs/<run_id>/run.json` for status, OOS, and artifacts.
5. When MCP is connected, call **`tqg_get_guidance`** with:
   - `user_request` — the user's message
   - `run_context_json` — contents of `run.json` (as JSON string)
   - optionally merge `lab_context` from `tqg_lab_context.py` / `lab_context_for_mcp()` into the request context
6. If OOS is missing for a new backtest, ask the user (default `2025-01-01`).

## Implement

7. Write code **only** under `runs/<run_id>/code/`.
8. Use `tqg_client.market_data.load_market_data()` for OHLCV loading (local `data/` first, yfinance fallback).
9. Save `strategy_spec.json` with symbol, asset class, data source, annualization, and OOS.
   List `signals` / `ensemble_weights` when the book has more than one additive leg.
   Before a new baseline, search lab memory so family N (`related_runs`) is not laundered into N=1.

## Validate and execute

10. When MCP is connected, call **`tqg_validate_strategy_code`** before running, or use:
    ```bash
    python scripts/tqg_run_backtest.py <run_id> --mcp-validate
    ```
11. Run locally:
    ```bash
    python scripts/tqg_run_backtest.py <run_id>
    ```
12. On failure, read `runs/<id>/logs/*.log`; call `tqg_get_guidance` with `last_error`; retry (max 3 attempts).

## Artifacts (baseline)

| Path | Content |
|------|---------|
| `artifacts/metrics.json` | `in_sample` + `out_of_sample` |
| `artifacts/selection.json` | N (trials), k (legs), DSR, null baseline |
| `charts/equity_curve.png` | Equity vs benchmark |
| `charts/drawdown.png` | Drawdown series |
| `strategy_spec.json` | Workflow, symbol, params, OOS |
| `report.md` | Short human summary |

## Cross-sectional factor research (crypto perps)

When building or iterating **cross-sectional** L/S factor books on `runs/<id>/`:

1. **Baseline first** — daily decile L/S with 1-bar signal lag (`runs/<id>/code/cross_sectional_alpha_sweep.py` pattern).
2. **Stability screen** — rank by subperiod consistency, not peak OOS Sharpe (`stability_factor_sweep.py`).
3. **Enhanced stack** — re-test finalists with `cs_research_core.py` / `enhanced_cs_experiments.py`:
   - Weekly rebalance (5d hold) instead of daily sleeve churn
   - Top-50 liquidity filter on signals
   - PSA-stable sleeves (5%) + factor-specific signal smoothing
   - Cross-sectional dispersion regime gate (trade when xs return dispersion > rolling median)
4. **Report IS and OOS separately**; flag IS/OOS Sharpe gaps > 1.0 as unstable. Quote N, k, and DSR next to those Sharpes. For CS books, optional `tqg_client.cs_shuffle.label_shuffle_cs`.
5. Use `CSResearchConfig` presets: `BASELINE_DAILY`, `STABLE_DEFAULT`.


For formulaic **alpha mining** (universe + hunch → Rank IC leaderboard), switch to skill **`tqg-alpha-mine`**. Do not improvise a Python factor sweep — use `python scripts/tqg_alpha_mine.py`.

For PSA / robustness follow-ups, switch to skill **`tqg-robustness-followup`**.

For packaging, switch to skill **`tqg-package-run`**.

## Finish

15. Record turns after significant prompts:
    ```bash
    python scripts/tqg_record_turn.py <run_id> --user "..." --assistant "..."
    ```
16. Tag institutional memory when a hypothesis is settled:
    ```bash
    python scripts/tqg_tag_run.py <run_id> --verdict no_edge --reason "..." --tag negative_result
    ```
17. Package when asked (requires `validation_passed: true` in `run.json`):
    ```bash
    python scripts/tqg_package_artifacts.py <run_id>
    ```

## Reply format

```
Run: <id>  status: …
IS Sharpe: …   OOS Sharpe: …
N (this run / family): … / …
k (legs): …
DSR (N=family): …
Null IS p95: …  (strategy percentile …)
```

- Paths to `artifacts/selection.json`, code, charts, and logs
- Do not present DSR or the null mean as expected OOS Sharpe
