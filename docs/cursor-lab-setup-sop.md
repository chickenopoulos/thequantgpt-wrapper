# Cursor Lab — client setup SOP

Target: **≤ 3 hours hands-on** for a technical operator (no call required).

## Prerequisites (client)

- [ ] Cursor account (Pro or Business recommended)
- [ ] Cloud server (e.g. Hetzner CX32, Ubuntu 22.04, 4+ vCPU, 8+ GB RAM)
- [ ] SSH key access to server
- [ ] TheQuantGPT API key (trial or subscription)
- [ ] Daily OHLCV data for at least one demo instrument (BTC parquet or any ticker via yfinance)

## Step 1 — Server access

```bash
ssh user@YOUR_SERVER
```

## Step 2 — Bootstrap

```bash
curl -fsSL https://raw.githubusercontent.com/chickenopoulos/thequantgpt-wrapper/main/scripts/bootstrap_server.sh | bash
# or clone manually and run scripts/bootstrap_server.sh
```

## Step 3 — Configuration

```bash
cd ~/thequantgpt-wrapper
cp config.example.yaml config.yaml   # if not already done
# Edit config.yaml: set tqg_api.base_url to your MCP host /v1
export TQG_API_KEY="your-key"
```

## Step 4 — Data

Upload parquet to:

```text
data/binance/binance_futures_ohlcv_1d.parquet
```

See `data/README_DATA_FORMAT.md`.

## Step 5 — Smoke test

```bash
source .venv/bin/activate
python scripts/tqg_init.py
```

All checks must pass.

## Step 6 — Cursor SSH workspace

1. Cursor → Remote SSH → add host
2. Open folder `~/thequantgpt-wrapper`
3. Ensure `AGENTS.md` is visible to the agent

## Step 7 — MCP in Cursor

Merge `tqg_client/mcp_config.example.json` into Cursor MCP settings. Set `TQG_API_KEY` in the environment Cursor uses for MCP (or in shell profile on server).

For local provider testing: `export TQG_API_BASE_URL=http://127.0.0.1:8787/v1`

Restart Cursor MCP / reload window.

## Step 8 — First run

Follow `examples/sample_run_instructions.md` (BTC mean reversion).

## Step 9 — Phone workflow

1. Cursor mobile → same SSH workspace
2. New agent chat
3. Paste Prompt 1 from `examples/btc_mean_reversion.md`
4. Review artifacts when run completes

## Acceptance (beta SOW)

- [ ] Server bootstrapped per this SOP
- [ ] MCP connected in Cursor
- [ ] 1 completed run: baseline backtest + PSA
- [ ] Artifacts under `runs/`
- [ ] Client triggers new run unaided from phone or desktop

## Troubleshooting

| Issue | Fix |
|-------|-----|
| MCP API fail | Check `TQG_API_KEY`, `config.yaml` base_url, trial not expired |
| No data | Upload parquet; re-run `tqg_init.py` |
| Import errors | `pip install -r requirements.txt` in `.venv` |
| Agent writes outside run folder | Point agent at `AGENTS.md`; specify `runs/<id>/` in prompt |
