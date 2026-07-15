---
name: tqg-research-session
description: >-
  Run a crypto OHLCV strategy research session in TheQuantGPT Cursor Lab.
  Use when the user asks to build, backtest, validate, iterate, or package
  a rule-based strategy under runs/.
---

# TheQuantGPT research session

You orchestrate the workflow. MCP tools provide **hints** and **validation** — not mandatory step lists.

## Before coding

1. Inspect `data/README_DATA_FORMAT.md` and list files under `data/`.
2. Create or open the active run:
   ```bash
   python scripts/tqg_create_run.py --title "<short title>"
   ```
3. Read `runs/<run_id>/run.json` for status, OOS, and artifacts.
4. When MCP is connected, call **`tqg_get_guidance`** with:
   - `user_request` — the user's message
   - `run_context_json` — contents of `run.json` (as JSON string)
5. If OOS is missing for a new backtest, ask the user (default `2025-01-01`).

## Implement

6. Write code **only** under `runs/<run_id>/code/`.
7. Use `tqg_client.market_data` for OHLCV loading.
8. Save `strategy_spec.json` when the strategy definition is clear.

## Validate and execute

9. When MCP is connected, call **`tqg_validate_strategy_code`** before running, or use:
   ```bash
   python scripts/tqg_run_backtest.py <run_id> --mcp-validate
   ```
10. Run locally:
    ```bash
    python scripts/tqg_run_backtest.py <run_id>
    ```
11. On failure, read `runs/<id>/logs/*.log`; call `tqg_get_guidance` with `last_error`; retry (max 3 attempts).

## Artifacts (baseline)

| Path | Content |
|------|---------|
| `artifacts/metrics.json` | `in_sample` + `out_of_sample` |
| `charts/equity_curve.png` | Equity vs benchmark |
| `charts/drawdown.png` | Drawdown series |
| `strategy_spec.json` | Workflow, symbol, params, OOS |
| `report.md` | Short human summary |

## Robustness and packaging

For PSA / robustness follow-ups, switch to skill **`tqg-robustness-followup`**.

For packaging, switch to skill **`tqg-package-run`**.

## Finish

15. Record turns when useful:
    ```bash
    python scripts/tqg_record_turn.py <run_id> --user "..." --assistant "..."
    ```
16. Package when asked (requires `validation_passed: true` in `run.json`):
    ```bash
    python scripts/tqg_package_artifacts.py <run_id>
    ```

## Reply format

- Run ID and `status` from `run.json`
- Key IS/OOS metrics from `artifacts/metrics.json`
- Paths to code, charts, and logs
