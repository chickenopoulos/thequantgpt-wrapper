# TheQuantGPT Cursor Lab — Agent Instructions

You operate a **client-owned quant research lab**. Build, run, validate, and package **crypto OHLCV rule-based strategies** for **research only**.

## Orchestration

**You orchestrate.** Skills and rules define defaults. MCP (when configured) provides advisory hints and validation — not a rigid step script.

| Layer | Role |
|-------|------|
| **This file** | Constitution and repo map |
| **`.cursor/rules/`** | Always-on invariants (scope, OOS, safety) |
| **`.cursor/skills/tqg-research-session/`** | Default research workflow |
| **MCP tools** | Optional: `tqg_get_guidance`, `tqg_validate_strategy_code`, `tqg_get_robustness_spec` |
| **Local scripts** | Execution and state (`tqg_run_backtest.py`, etc.) |

## Quick workflow

1. Inspect `data/` and create or open `runs/<run_id>/`.
2. Implement code under `runs/<run_id>/code/` only.
3. Run: `python scripts/tqg_run_backtest.py <run_id>`
4. Save artifacts (`metrics.json`, charts, `strategy_spec.json`, `report.md`).
5. Package: `python scripts/tqg_package_artifacts.py <run_id>`

Smoke test: `python scripts/tqg_init.py` (add `--run-demo` to test local execution without MCP).

## Run state

Durable memory lives in `runs/<run_id>/run.json` — read it before follow-ups. Do not rely on chat history alone.

## MCP (optional in Phase 1)

When MCP is connected, call tools when helpful — especially for validation and robustness specs. The lab works locally without MCP using `tqg_client.local_validate` inside `tqg_run_backtest.py`.

Config: `config.yaml` + `TQG_API_KEY`; example MCP config in `tqg_client/mcp_config.example.json`.

## Examples

- `examples/btc_mean_reversion.md` — demo prompt sequence
- `examples/sample_run_instructions.md` — sales demo flow

## Do not

- Copy or expose raw master prompts from MCP responses.
- Send client OHLCV data to external services.
- Commit secrets, parquet files, or full run outputs to git.
