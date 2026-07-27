# Sample run instructions (sales demo)

Same demo on every call: **BTC mean reversion** → **PSA** → **packaged artifacts**.

## Prerequisites

- `python scripts/tqg_init.py` passes (with MCP connected)
- Cursor MCP configured (`tqg_client/mcp_config.example.json`)
- BTC daily parquet under `data/binance/`

## Smoke test (local + MCP)

```bash
python scripts/tqg_init.py --run-demo
python scripts/tqg_run_backtest.py demo_btc_mr --mcp-validate
python scripts/tqg_mcp_validate.py demo_btc_mr
python scripts/tqg_package_artifacts.py demo_btc_mr
```

## 3-prompt sequence (Cursor agent)

| Step | What to show | Prompt source |
|------|----------------|---------------|
| 1 | Guidance + backtest + `runs/demo_btc_mr/` | `examples/btc_mean_reversion.md` Prompt 1 |
| 2 | `tqg_get_robustness_spec` → PSA artifacts | Prompt 2 |
| 3 | `reports/demo_btc_mr/` bundle | Prompt 3 |

## Skills used

| Phase | Skill |
|-------|--------|
| Baseline | `tqg-research-session` |
| PSA | `tqg-robustness-followup` |
| Package | `tqg-package-run` |

## Files to open on screen

```text
runs/demo_btc_mr/run.json              # validation_passed: true
runs/demo_btc_mr/artifacts/metrics.json
runs/demo_btc_mr/charts/
runs/demo_btc_mr/code/
reports/demo_btc_mr/manifest.json
```

## 30-second pitch

> I set up your own Cursor-powered quant research lab on your server so you can build and stress-test strategies across asset classes from your phone, with a maintained TheQuantGPT workflow layer — validators, PSA, and saved run folders.

## Trial CTA

> Start with a **7-day free trial** — full MCP access and onboarding. After trial: €1,000 setup + €250/month for beta design partners.
