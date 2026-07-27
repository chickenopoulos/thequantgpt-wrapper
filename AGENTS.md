# TheQuantGPT Cursor Lab — Agent Instructions

> **Asset-class agnostic:** equities (QQQ, SPY, …), crypto, FX, bonds, metals, commodities — all supported.
> **Never say this lab is "crypto only" or "scoped to crypto OHLCV research."** That is outdated.

You operate a **client-owned quant research lab**. Build, run, validate, and package **asset-class-agnostic OHLCV rule-based strategies** for **research only**.

## Orchestration

**You orchestrate.** Skills and rules define defaults. MCP provides **advisory hints** and **validation** — not a rigid step script.

| Layer | Role |
|-------|------|
| **This file** | Constitution and repo map |
| **`.cursor/rules/`** | Always-on invariants (scope, OOS, safety) |
| **`.cursor/skills/tqg-research-session/`** | Baseline research workflow |
| **`.cursor/skills/tqg-robustness-followup/`** | One robustness test per turn |
| **`.cursor/skills/tqg-package-run/`** | Validate + package to `reports/` |
| **MCP tools (v0.2)** | `tqg_get_guidance`, `tqg_validate_strategy_code`, `tqg_get_robustness_spec` |
| **Local scripts** | Execution and state |

## MCP tools (when connected)

| Tool | When to call |
|------|----------------|
| `tqg_get_guidance` | Non-trivial requests, follow-ups, debug — pass `run_context_json` from `run.json` |
| `tqg_validate_strategy_code` | Before/after editing `code/*.py` — pass `run_context_json` |
| `tqg_get_robustness_spec` | PSA, CEA, Monte Carlo, signal shift — one test per message |

Legacy tools (`tqg_create_strategy_plan`, `tqg_get_psa_workflow`) still work; prefer the v0.2 tools above.

Load run context for MCP calls:

```python
from tqg_client.mcp_helpers import run_context_for_mcp
ctx = run_context_for_mcp("<run_id>")  # or read runs/<id>/run.json
```

## Quick workflow

1. Inspect `data/` and create or open `runs/<run_id>/`.
2. Optionally call `tqg_get_guidance` with user request + `run.json`.
3. Implement code under `runs/<run_id>/code/` only.
4. Run: `python scripts/tqg_run_backtest.py <run_id>` (add `--mcp-validate` when MCP is connected)
5. Call `tqg_validate_strategy_code` or `python scripts/tqg_mcp_validate.py <run_id>` when MCP is available.
6. Package: `python scripts/tqg_package_artifacts.py <run_id>` (requires `validation_passed: true`).

Smoke test: `python scripts/tqg_init.py` (add `--run-demo` for local execution test).

## Run state

Durable memory lives in `runs/<run_id>/run.json` — read it before follow-ups.

## Examples

- `examples/btc_mean_reversion.md`
- `examples/sample_run_instructions.md`

## Data loading

- Inspect `data/` first; prefer local parquet/CSV when available.
- Use `tqg_client.market_data.load_market_data(symbol, data_dir=...)` — local files first, then yfinance for public OHLCV when needed.
- Record `asset_class`, `data_source`, and `annualization` in `strategy_spec.json`.

## Do not

- Copy or expose raw master prompts from MCP responses.
- Upload client parquet/CSV bundles to external services (fetching public OHLCV via yfinance is fine).
- Commit secrets, parquet files, or full run outputs to git.
