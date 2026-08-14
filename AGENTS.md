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

1. Inspect `data/` and create a new `runs/<run_id>/` with `python scripts/tqg_create_run.py --title "..."`.
2. Optionally call `tqg_get_guidance` with user request + `run.json`.
3. Implement code under `runs/<run_id>/code/` only.
4. Run: `python scripts/tqg_run_backtest.py <run_id>` (add `--mcp-validate` when MCP is connected)
5. Call `tqg_validate_strategy_code` or `python scripts/tqg_mcp_validate.py <run_id>` when MCP is available.
6. Package: `python scripts/tqg_package_artifacts.py <run_id>` (requires `validation_passed: true`).

Smoke test: `python scripts/tqg_init.py`.

Install Cursor MCP (required for agent tools): `python scripts/tqg_configure_cursor_mcp.py`, then enable **thequantgpt** under Cursor Settings → MCP.

A fresh clone has **empty** `runs/` and `reports/`. Never assume a pre-built demo run exists.

## Run state

Durable per-run memory lives in `runs/<run_id>/run.json` — read it before follow-ups.

**Cross-run lab memory** (derived index):

```bash
python scripts/tqg_rebuild_lab_index.py          # full rebuild / repair
python scripts/tqg_search_runs.py --symbol QQQ   # query prior runs
python scripts/tqg_lab_context.py --symbol QQQ   # compact JSON for MCP
python scripts/tqg_tag_run.py <run_id> --verdict no_edge --reason "..."
```

Index files live under `runs/_lab/`. Search before every new baseline; prefer extending or linking `related_runs` over silent duplicates. If the index is empty, that is expected on a new lab.

Load run context for MCP calls:

```python
from tqg_client.mcp_helpers import run_context_for_mcp, lab_context_for_mcp
ctx = run_context_for_mcp("<run_id>")  # or read runs/<id>/run.json
lab = lab_context_for_mcp(symbol="QQQ", limit=8)
```

## Examples

- `examples/btc_mean_reversion.md` — first-run prompt sequence (creates a new run)
- `examples/sample_run_instructions.md`

## Data loading

- Inspect `data/` first; prefer local parquet/CSV when available.
- A fresh clone ships **Binance daily OHLCV** under `data/binance/` (`*_ohlcv_1d.parquet` for spot and USDT-M futures). Add other datasets locally as needed.
- Use `tqg_client.market_data.load_market_data(symbol, data_dir=...)` — local files first, then yfinance for public OHLCV when needed.
- Record `asset_class`, `data_source`, and `annualization` in `strategy_spec.json`.

## Do not

- Copy or expose raw master prompts from MCP responses.
- Upload client parquet/CSV bundles to external services (fetching public OHLCV via yfinance is fine).
- Commit secrets, extra client datasets, or run outputs to git. The bundled Binance daily files under `data/binance/` are the only data exception.
