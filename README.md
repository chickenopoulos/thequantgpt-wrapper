# TheQuantGPT Cursor Lab (client wrapper)

A **thin client repo** for systematic crypto research on your own server. Cursor agents build strategies, run backtests, and save audit-ready artifacts under `runs/<id>/`. The maintained **TheQuantGPT workflow layer** (validators, PSA catalog, planning) is delivered via a private MCP API.

> **Research only** — no live trading. Crypto OHLCV at launch.

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
AGENTS.md              # Cursor agent operating rules
config.yaml            # Local paths + MCP URL (gitignored)
data/                  # Client OHLCV parquet/CSV (gitignored)
runs/                  # Per-strategy workspaces
reports/               # Packaged artifact bundles for sharing
scripts/               # create_run, init, package, MCP bridge
tqg_client/            # API client + data helpers
examples/              # Demo prompt sequences
docs/                  # Setup SOP, FAQ, commercial templates
```

## Documentation

- [Setup SOP](docs/cursor-lab-setup-sop.md)
- [FAQ](docs/FAQ.md)
- [Offer summary](docs/commercial/OFFER.md)
- [7-day trial terms](docs/commercial/TRIAL_TERMS.md)

## Support

Async support during active subscription. On cancel you keep server, data, code, and artifacts; MCP access and updates end.
