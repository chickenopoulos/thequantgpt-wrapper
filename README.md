# TheQuantGPT Cursor Lab (client wrapper)

A **thin client repo** for systematic quant research on your own server. Cursor agents build strategies, run backtests, and save audit-ready artifacts under `runs/<id>/`. The maintained **TheQuantGPT workflow layer** (validators, PSA catalog, planning) is delivered via a private MCP API.

> **Research only** — no live trading. Asset-class agnostic (crypto, equities, FX, bonds, metals, etc.); local OHLCV preferred, yfinance supported.

## Quick start

```bash
git clone https://github.com/chickenopoulos/thequantgpt-wrapper.git
cd thequantgpt-wrapper
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml   # set tqg_api.base_url
export TQG_API_KEY="your-key"
python scripts/tqg_init.py
```

Connect Cursor MCP using `tqg_client/mcp_config.example.json`, then follow `examples/sample_run_instructions.md`.

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
data/                        # Client OHLCV parquet/CSV (gitignored)
runs/<id>/                   # Per-strategy workspace (run.json, code/, artifacts/)
reports/                     # Packaged artifact bundles
scripts/
  tqg_create_run.py          # Scaffold run folder + run.json
  tqg_run_backtest.py        # Execute code/ (--mcp-validate optional)
  tqg_mcp_validate.py        # MCP validation only → updates run.json
  tqg_update_run_state.py    # Merge execution into run.json
  tqg_record_turn.py         # Append to flow.json
  tqg_package_artifacts.py   # runs/ → reports/
  tqg_init.py                # Smoke test (--run-demo for local execution)
tqg_client/                  # API client, run state, execution helpers
examples/                    # Demo prompt sequences
docs/                        # Setup SOP, FAQ, commercial templates
```

Local smoke test without MCP:

```bash
python scripts/tqg_init.py --skip-mcp --run-demo
```

## Documentation

- [Setup SOP](docs/cursor-lab-setup-sop.md)
- [FAQ](docs/FAQ.md)
- [Offer summary](docs/commercial/OFFER.md)
- [7-day trial terms](docs/commercial/TRIAL_TERMS.md)

## Support

Async support during active subscription. On cancel you keep server, data, code, and artifacts; MCP access and updates end.
