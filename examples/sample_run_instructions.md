# Sample run instructions (sales demo)

Same demo on every call: **BTC mean reversion** → **PSA** → **packaged artifacts**.

## Prerequisites

- `python scripts/tqg_init.py` passes
- Cursor MCP connected (`tqg_client/mcp_config.example.json`)
- BTC daily parquet under `data/binance/`

## 3-prompt sequence

| Step | What to show | Prompt source |
|------|----------------|---------------|
| 1 | Phone/desktop → Cursor → plan + backtest + `runs/demo_btc_mr/` | `examples/btc_mean_reversion.md` Prompt 1 |
| 2 | MCP PSA workflow → heatmap in run folder | Prompt 2 |
| 3 | `reports/demo_btc_mr/` bundle | Prompt 3 |

## Files to open on screen

```text
runs/demo_btc_mr/artifacts/metrics.json
runs/demo_btc_mr/charts/
runs/demo_btc_mr/code/
reports/demo_btc_mr/manifest.json
```

## 30-second pitch (no Streamlit)

> I set up your own Cursor-powered quant research lab on your server so you can build and stress-test crypto strategies from your phone, with a maintained TheQuantGPT workflow layer — validators, PSA, and saved run folders.

## Trial CTA

> Start with a **7-day free trial** — full MCP access and onboarding. After trial: €1,000 setup + €250/month for beta design partners.
