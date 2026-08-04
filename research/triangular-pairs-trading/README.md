# Triangular Pairs Trading (Binance USDT-M Perpetuals)

Research project for **statistical triangular pairs trading** on Binance perpetual futures. Lives under `research/triangular-pairs-trading/`; market data is read from the lab `data/binance/` directory at the repo root.

## Research summary

### What "triangular pairs trading" means here

We distinguish two concepts:

| Approach | Idea | Viability on Binance perps |
|----------|------|----------------------------|
| **Pure triangular arbitrage** | Loop three pairs (e.g. BTC→ETH→USDT→BTC) when implied cross-rates misprice | Edge collapsed on majors; needs sub-second execution and maker rebates |
| **Statistical triangular pairs** (this project) | Model `log(P_target) ≈ α + β₁·log(P_leg1) + β₂·log(P_leg2)`; trade mean reversion of the OLS residual | Feasible at daily/hourly horizons with proper costs and OOS validation |

Academic work on crypto pairs trading (cointegration, copula mispricing) finds **short-term inefficiencies exist** but **transaction costs often dominate** unless signals are selective and thresholds are tuned (Huang & Martin 2026; copula overlay studies on Binance perps).

### Strategy design

1. **Universe**: Liquid USDT-M perps; anchors `BTC`, `ETH`, `BNB`, `SOL`.
2. **Triangle**: alt `target` hedged with two anchor legs (e.g. `LINK ~ BTC + ETH`).
3. **Signal**: Rolling OLS residual z-score; enter at ±z, exit near 0.
4. **Portfolio**: Top N triangles ranked in-sample by ADF stationarity + half-life; capped per-triangle weight.
5. **Execution model**: 1-bar lag, taker fee + slippage per leg, turnover-based costs.
6. **OOS cutoff**: `2025-01-01` (lab default).

### Action plan

1. **Discover** — rank triangles on in-sample cointegration (`scripts/discover_triangles.py`).
2. **Backtest v1** — multi-triangle z-score mean reversion (`scripts/run_backtest.py`).
3. **Sweep** — grid search entry/exit/window (`scripts/param_sweep.py`).
4. **Iterate** — funding overlay, regime filter, hourly signals, Kalman hedge ratios (see `scripts/` enhancements).

## Quick start

```bash
cd research/triangular-pairs-trading
pip install -r requirements.txt

# 1) Discover triangles (in-sample only)
python scripts/discover_triangles.py

# 2) Run backtest
python scripts/run_backtest.py

# 3) Parameter sweep (slow)
python scripts/param_sweep.py
```

Results are written to `results/`.

## Project layout

```
research/triangular-pairs-trading/
  src/
    config.py           # paths, fees, interval profiles
    data.py             # daily + hourly panel loading
    triangles.py        # discovery + rolling OLS residuals
    signals.py          # z-score position logic
    backtest.py         # portfolio engine + metrics
    discovery.py        # batch triangle discovery
    rolling_refresh.py  # rolling triangle re-selection
  scripts/
    discover_triangles.py
    run_backtest.py
    run_best.py
    run_hourly.py
    discover_hourly.py
    sweep_hourly_native.py
    run_best_hourly_native.py
    run_rolling_refresh.py
    explore_hourly_rolling.py
    save_best_variants.py
    robustness.py
    param_sweep.py
  results/         # outputs (gitignored)
```

## Data

- Daily: `binance_futures_ohlcv_1d.parquet` (~618 symbols, 2020–2026)
- Hourly: `binance_futures_ohlcv_1h.parquet` (for future intraday work)

## Results (best validated system)

Run: `python scripts/run_best.py`

| Metric | Full sample | Out-of-sample (≥ 2025-01-01) |
|--------|-------------|------------------------------|
| Sharpe | 0.49 | **2.07** |
| CAGR | 7.0% | 8.7% |
| Max drawdown | -35.3% | **-2.3%** |

**Triangles (10):** SFP and DOGE altcoins hedged against BTC/ETH/BNB/SOL anchor legs — selected in-sample by ADF stationarity and half-life.

**Parameters:** `window=120`, `entry_z=3.0`, `exit_z=0.75`, `weight_cap=0.20`.

**Robustness** (`python scripts/robustness.py`):
- Bootstrap OOS Sharpe: p5=0.76, median=2.02, p95=3.23
- 2024 was weak (Sharpe -0.10); 2025–2026 strong (Sharpe > 1.85)
- Walk-forward re-selection and diversification **hurt** performance — static IS triangle set generalizes better

### What did not work

- Pure triangular arbitrage (millisecond mispricings) — not viable at daily frequency after fees
- Correlation-regime gating, funding tilt, vol scaling overlays — degraded full-sample returns
- Walk-forward triangle refresh — OOS Sharpe fell to 0.35
- Forcing one triangle per target (diversification) — removed the best SFP/DOGE clusters

### Caveats

- Triangle universe is calibrated in-sample; monitor for structural breaks (e.g. 2022 bear drawdown -35%)
- Three-leg trades incur ~0.29% round-trip cost at default fee/slippage assumptions
- Research only — not live trading advice

## Hourly data exploration

Run: `python scripts/run_hourly.py --window 1440 --entry-z 2.5`

Uses the same daily-selected triangles on **hourly** Binance perp bars (2022+).
Best config from sweep: **60-day window (1440 bars)**, `entry_z=2.5`.

| Metric | Daily static baseline | Hourly (daily-compounded) |
|--------|----------------------|---------------------------|
| OOS Sharpe | **2.07** | **1.81** |
| Full MaxDD | -35.3% | -50.1% |

Hourly nearly matches OOS Sharpe of the daily system but with worse full-sample drawdown
(more trades, more fee drag in 2022–2024). Shorter windows (480 bars / 20 days) also work
(OOS ~1.50) but 1440 bars is best.

## Rolling triangle refresh

Run: `python scripts/run_rolling_refresh.py --refresh-freq 180D --lookback-days 180`

Re-selects triangles every **180 days** using only the prior **180 days** of data
(restricted to top-40 liquid alts). Sticky retention disabled for best results.

| Metric | Daily static | Rolling 180D/180 |
|--------|-------------|------------------|
| Full Sharpe | 0.49 | **0.55** |
| OOS Sharpe | **2.07** | 1.05 |
| Full MaxDD | -35.3% | **-11.7%** |
| OOS MaxDD | -2.3% | -4.0% |

Rolling refresh trades OOS Sharpe for a **much smoother equity curve** and better
in-sample risk. Avoid 90D refresh (too little time per triangle to mean-revert).

**Hourly + rolling combined** underperformed (OOS Sharpe ~0.36) — refresh churn
dominates at hourly frequency.

## Hourly-native triangle discovery

Run discovery: `python scripts/discover_hourly.py --lookback-days 365 --window 720`  
Full sweep: `python scripts/sweep_hourly_native.py`  
Best config: `python scripts/run_best_hourly_native.py`

Triangles are ranked on **hourly** cointegration (not daily picks), then backtested
on hourly bars (2023+). Sweep over discovery lookback (90/180/365d), discovery window
(720/1440 bars), and backtest window/entry.

| Source | Discovery | Backtest | OOS Sharpe (daily-comp) | Full MaxDD |
|--------|-----------|----------|-------------------------|------------|
| Daily-static triangles | daily IS | hourly w=1440, z=2.5 | 1.81 | -21.7% |
| **Hourly-native** | **365d lb, w=720** | **w=1440, z=2.5** | **2.87** | **-19.8%** |

Hourly-native discovery is the best variant tested so far on the 2023+ hourly panel.
Use **365-day lookback** for discovery; 90-day lookback is too noisy (OOS &lt; 0 on
several configs). Top triangles overlap with daily picks (SFP, SPELL, RSR) but ranking
differs — native discovery surfaces RSR/SPELL-heavy baskets for shorter lookbacks.

Results: `results/hourly_native_sweep.csv`, `results/hourly_native_summary.json`

Full sweep: `python scripts/explore_hourly_rolling.py` → `results/explore_summary.json`
