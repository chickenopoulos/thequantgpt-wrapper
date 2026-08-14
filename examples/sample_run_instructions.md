# Sample run instructions

First strategy on a **fresh clone**: create a run, then **BTC mean reversion** → **PSA** → **packaged artifacts**.

No demo folder is shipped. `runs/` starts empty.

## Prerequisites

- `python scripts/tqg_init.py` passes (with MCP connected)
- Cursor MCP configured (`tqg_client/mcp_config.example.json`)
- Bundled Binance daily parquet under `data/binance/` (spot + USDT-M futures)

## Smoke test

```bash
python scripts/tqg_init.py
python scripts/tqg_create_run.py --title "BTC mean reversion" --run-id btc_mean_reversion
```

Then use the Cursor prompts in `examples/btc_mean_reversion.md`. After the agent implements the strategy:

```bash
python scripts/tqg_run_backtest.py btc_mean_reversion --mcp-validate
python scripts/tqg_package_artifacts.py btc_mean_reversion
```

## 3-prompt sequence (Cursor agent)

| Step | What to show | Prompt source |
|------|----------------|---------------|
| 1 | Guidance + backtest + `runs/btc_mean_reversion/` | `examples/btc_mean_reversion.md` Prompt 1 |
| 2 | `tqg_get_robustness_spec` → PSA artifacts | Prompt 2 |
| 3 | `reports/btc_mean_reversion/` bundle | Prompt 3 |

## Skills used

| Phase | Skill |
|-------|--------|
| Baseline | `tqg-research-session` |
| PSA | `tqg-robustness-followup` |
| Package | `tqg-package-run` |

## Files to open after the run completes

```text
runs/btc_mean_reversion/run.json              # validation_passed: true
runs/btc_mean_reversion/artifacts/metrics.json
runs/btc_mean_reversion/charts/
runs/btc_mean_reversion/code/
reports/btc_mean_reversion/manifest.json
```

## 30-second pitch

> I set up your own Cursor-powered quant research lab on your server so you can build and stress-test strategies across asset classes from your phone, with a maintained TheQuantGPT workflow layer — validators, PSA, and saved run folders.

## Trial CTA

> Start with a **7-day free trial** — full MCP access and onboarding. After trial: €1,000 setup + €250/month for beta design partners.
