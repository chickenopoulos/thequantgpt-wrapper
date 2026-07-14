---
name: tqg-research-session
description: >-
  Run a crypto OHLCV strategy research session in TheQuantGPT Cursor Lab.
  Use when the user asks to build, backtest, validate, iterate, or package
  a rule-based strategy under runs/.
---

# TheQuantGPT research session

You orchestrate the workflow. MCP tools (when configured) provide **hints**; you decide the steps.

## Before coding

1. Inspect `data/README_DATA_FORMAT.md` and list files under `data/`.
2. Read or create the active run:
   ```bash
   python scripts/tqg_create_run.py --title "<short title>"
   ```
3. Optionally call MCP `tqg_get_guidance` with the user request and `run.json` context.
4. If OOS is missing for a new backtest, ask the user (default `2025-01-01`).

## Implement

5. Write code **only** under `runs/<run_id>/code/`.
6. Use `tqg_client.market_data` for OHLCV loading.
7. Save `strategy_spec.json` when the strategy definition is clear.

## Execute

8. Run the backtest locally:
   ```bash
   python scripts/tqg_run_backtest.py <run_id>
   ```
9. On failure, read `runs/<id>/logs/*.log`, fix code, retry (max 3 attempts per user turn).
10. Optionally call MCP `tqg_validate_strategy_code` when MCP is configured.

## Artifacts (baseline)

Required after a successful baseline:

| Path | Content |
|------|---------|
| `artifacts/metrics.json` | `in_sample` + `out_of_sample` blocks |
| `charts/equity_curve.png` | Equity vs benchmark |
| `charts/drawdown.png` | Drawdown series |
| `strategy_spec.json` | Workflow, symbol, params, OOS |
| `report.md` | Short human summary |

## Follow-ups

11. Record the turn when useful:
    ```bash
    python scripts/tqg_record_turn.py <run_id> --user "..." --assistant "..."
    ```
12. For PSA / robustness: one test per message; read `run.json` first.
13. Package when the user asks:
    ```bash
    python scripts/tqg_package_artifacts.py <run_id>
    ```

## Reply format

End with:

- Run ID and status from `run.json`
- Key IS/OOS metrics from `artifacts/metrics.json`
- Paths to code, charts, and logs
