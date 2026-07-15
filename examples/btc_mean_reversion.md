# BTC mean reversion — demo prompts

Use **one new Cursor chat** per study. Send prompts **in order**. Wait for each reply before sending the next.

Create the run first (agent or you):

```bash
python scripts/tqg_create_run.py --title "BTC mean reversion" --run-id demo_btc_mr
```

---

## Prompt 1 — Build the strategy

```text
Let's build a mean-reversion strategy on Bitcoin.

Use BTCUSDT daily data from our local Binance/crypto dataset under data/.

How the signal works:
- Use a 30-day Z-score of daily returns (not raw price)
- Use a 90-day simple moving average of price as a trend filter
- Indicators should use prior-day data only (no lookahead)

Trading rules:
- Go long when Z-score < -1.5 and price is above the 90-day average
- Go short when Z-score > 1.5 and price is below the 90-day average
- Exit long when Z-score rises above 0 or price falls below the average
- Exit short when Z-score falls below 0 or price rises above the average

Important: Single-asset only — not a multi-asset portfolio.

Out-of-sample cut-off: 2025-01-01.

Work in runs/demo_btc_mr/ only.

Please:
1. Call tqg_get_guidance with the user request and run.json context
2. Implement and run: python scripts/tqg_run_backtest.py demo_btc_mr
3. Save metrics.json, equity chart, and strategy code under the run folder
4. Call tqg_validate_strategy_code with run_context_json before finishing
```

---

## Prompt 2 — PSA on lookback windows

```text
Run PSA (parameter sensitivity analysis) on this BTC mean-reversion strategy.

Vary only:
- Z-score lookback window: 5 to 200 days, step 5
- Moving-average lookback window: 5 to 200 days, step 5

Keep other settings fixed. In-sample only (before 2025-01-01). Rank by Sharpe.

Call tqg_get_robustness_spec with user_request and run.json context first.
Implement PSA per the spec (not a rigid step list).
Save PSA outputs under runs/demo_btc_mr/artifacts/ and charts under runs/demo_btc_mr/charts/.
```

---

## Prompt 3 — Package

```text
Package this run for sharing.

python scripts/tqg_package_artifacts.py demo_btc_mr

Summarize artifact paths under reports/demo_btc_mr/.
```
