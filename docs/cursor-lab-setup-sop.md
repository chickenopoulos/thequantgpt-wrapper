# Cursor Lab — client setup SOP

Target: **≤ 3 hours hands-on** for a technical operator (no call required).

## Prerequisites (client)

- [ ] Cursor account (Pro or Business recommended)
- [ ] Cloud server (e.g. Hetzner CX32, Ubuntu 22.04, 4+ vCPU, 8+ GB RAM)
- [ ] SSH key access to server
- [ ] TheQuantGPT API key (trial or subscription)

Binance daily OHLCV (spot + USDT-M futures) is bundled in the repo under `data/binance/`. Additional instruments can use extra local files or yfinance.

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
cp .env.example .env
# edit .env: TQG_API_KEY=your-key
# config.example.yaml defaults to https://tqg-mcp.vkotopoulos.com/v1
```

## Step 4 — Data

A fresh clone already includes:

```text
data/binance/binance_futures_ohlcv_1d.parquet
data/binance/binance_spot_ohlcv_1d.parquet
```

Add more parquet/CSV under `data/` as needed. See `data/README_DATA_FORMAT.md`.

## Step 5 — Smoke test

```bash
source .venv/bin/activate
python scripts/tqg_init.py
```

All checks must pass. `runs/` should still be empty until you create a strategy.

## Step 6 — Cursor SSH workspace

1. Cursor → Remote SSH → add host
2. Open folder `~/thequantgpt-wrapper`
3. Ensure `AGENTS.md` is visible to the agent

## Step 7 — Install MCP in Cursor

Cursor agents do **not** inherit a terminal `export TQG_API_KEY`. Install a project MCP server:

```bash
source .venv/bin/activate
python scripts/tqg_configure_cursor_mcp.py
```

That writes `.cursor/mcp.json` (gitignored) pointing at this clone’s venv Python, `scripts/tqg_mcp_bridge.py`, and `.env`.

Then in Cursor:

1. Open the wrapper folder as the workspace (**File → Open Folder**, or SSH remote folder).
2. **Cursor Settings → MCP**.
3. Enable the project server **`thequantgpt`**.
4. Confirm these tools are listed: `tqg_get_guidance`, `tqg_validate_strategy_code`, `tqg_get_robustness_spec`.
5. If the server is red, reload the window and re-check `.env` / `.venv`.

Manual fallback: copy `tqg_client/mcp_config.example.json` to `.cursor/mcp.json` and replace the absolute paths.

For local provider testing: `export TQG_API_BASE_URL=http://127.0.0.1:8787/v1` in `.env` as well.

## Step 8 — First run

Follow `examples/sample_run_instructions.md` (create a run, then BTC mean reversion).

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
| MCP API fail | Check `TQG_API_KEY` in `.env`, `config.yaml` base_url, trial not expired |
| Cursor MCP server red / no tools | Run `python scripts/tqg_configure_cursor_mcp.py`; Cursor Settings → MCP → enable `thequantgpt`; reload window |
| Missing bundled data | Re-clone or restore `data/binance/*_ohlcv_1d.parquet`; re-run `tqg_init.py` |
| Import errors | `pip install -r requirements.txt` in `.venv` |
| Agent writes outside run folder | Point agent at `AGENTS.md`; specify `runs/<id>/` in prompt |
