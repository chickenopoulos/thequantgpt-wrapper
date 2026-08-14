# TheQuantGPT Cursor Lab (client wrapper)

A **thin client repo** for systematic quant research on your own server. Cursor agents build strategies, run backtests, and save audit-ready artifacts under `runs/<id>/`. The maintained **TheQuantGPT workflow layer** (validators, PSA catalog, planning) is delivered via a private MCP API.

> **Research only** — no live trading. Asset-class agnostic (crypto, equities, FX, bonds, metals, etc.); local OHLCV preferred, yfinance supported.

A clone is a **fresh lab**: empty `runs/` and `reports/`. The only bundled market data is Binance daily OHLCV under `data/binance/`.

## Quick start

```bash
git clone https://github.com/chickenopoulos/thequantgpt-wrapper.git
cd thequantgpt-wrapper
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml   # defaults to https://tqg-mcp.vkotopoulos.com/v1
cp .env.example .env                 # then set TQG_API_KEY in .env
python scripts/tqg_init.py
python scripts/tqg_configure_cursor_mcp.py
```

### Install MCP in Cursor

`tqg_init.py` talks to the HTTP API. Cursor agents need a **project MCP server** as well:

1. Open this folder as the Cursor workspace (**File → Open Folder**).
2. `python scripts/tqg_configure_cursor_mcp.py` writes `.cursor/mcp.json` (gitignored) using this clone’s `.venv` and `.env`.
3. **Cursor Settings → MCP**.
4. Enable the project server named **`thequantgpt`**. Wait until tools appear: `tqg_get_guidance`, `tqg_validate_strategy_code`, `tqg_get_robustness_spec`.
5. If it errors, reload the window. Confirm `.env` has a real `TQG_API_KEY` (a shell `export` is not visible to Cursor).

Then follow `examples/sample_run_instructions.md`.

## Commercial model

| Stage | Offer |
|-------|--------|
| **Trial** | 7-day free trial (full workflow + MCP access) |
| **Beta** | €1,000 setup + €250/month (3-month minimum) — design partners |
| **Standard** | €3,500 setup + €500/month |

You pay separately for Cursor, cloud server, and LLM API usage.

## Repo layout

```text
AGENTS.md                    # Agent constitution (orchestration + repo map)
.cursor/rules/               # Always-on quant invariants
.cursor/skills/              # Research session playbooks
config.yaml                  # Local paths + MCP URL (gitignored)
data/binance/                # Bundled Binance daily OHLCV (spot + USDT-M futures)
runs/<id>/                   # Per-strategy workspace (created locally)
runs/_lab/                   # Cross-run memory index (derived, local)
reports/                     # Packaged artifact bundles (created locally)
scripts/
  tqg_create_run.py          # Scaffold run folder + run.json
  tqg_run_backtest.py        # Execute code/ (--mcp-validate optional)
  tqg_mcp_validate.py        # MCP validation only → updates run.json
  tqg_update_run_state.py    # Merge execution into run.json
  tqg_record_turn.py         # Append to flow.json
  tqg_package_artifacts.py   # runs/ → reports/
  tqg_rebuild_lab_index.py   # Rebuild cross-run index
  tqg_search_runs.py         # Query prior runs
  tqg_lab_context.py         # Compact lab context for MCP
  tqg_tag_run.py             # Verdicts, tags, related_runs
  tqg_init.py                # Smoke test (deps, config, bundled data, MCP API)
  tqg_configure_cursor_mcp.py  # Write .cursor/mcp.json for Cursor
tqg_client/                  # API client, run state, lab index, execution helpers
examples/                    # First-run prompt sequences
docs/                        # Setup SOP, FAQ, commercial templates
```

Local smoke test without MCP:

```bash
python scripts/tqg_init.py --skip-mcp
```

Create the first strategy workspace:

```bash
python scripts/tqg_create_run.py --title "BTC mean reversion" --run-id btc_mean_reversion
```

### Lab memory

```bash
python scripts/tqg_rebuild_lab_index.py
python scripts/tqg_search_runs.py --symbol BTCUSDT --oos-sharpe-lt 0.3
python scripts/tqg_tag_run.py <run_id> --verdict no_edge --reason "weak OOS"
```

## Documentation

- [Setup SOP](docs/cursor-lab-setup-sop.md)
- [FAQ](docs/FAQ.md)
- [Offer summary](docs/commercial/OFFER.md)
- [7-day trial terms](docs/commercial/TRIAL_TERMS.md)

## Support

Async support during active subscription. On cancel you keep server, data, code, and artifacts; MCP access and updates end.
