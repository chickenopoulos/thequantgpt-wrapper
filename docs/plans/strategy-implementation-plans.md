# Strategy Implementation Plans

> **Source:** `docs/research/implementable-strategies-from-sources.md`  
> **Purpose:** One plan per strategy — **Logic**, **Added Value**, **Integration Steps**.  
> **Default OOS:** `2025-01-01`  
> **Generated:** 2026-07-22

---

## Priority demos (implement first)

1. T-05 + V-02 — BTC TSMOM + vol target
2. ON-01 — BTC MVRV deep value
3. CG-01 — BTC funding carry
4. GF-02 — Glassnode composite
5. MR-15 + MR-03 — QQQ MR + ER gate
6. XS-01 — Binance CS momentum
7. T-06 — Percentile-rank momentum
8. T-10 — QQQ/BTC rotation
9. MR-07 — Turnaround Tuesday
10. CG-05 — Liquidation fade (1h)

---

## Part A1 — Trend

### T-01 Dual moving-average crossover

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Long when fast MA > slow MA.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Params 20/100 or 50/200.
8. PSA: fix slow, sweep fast.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### T-02 CMMA trend

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Sign of ATR-normalized log-price minus lagged MA.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. CMMA primitive (2.12).
8. k=20–60.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### T-03 Donchian breakout

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Long N-day high; exit N/2 low.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. N=20,55,100.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### T-04 Donchian + ER gate

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
T-03 when ER < 0.3.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. ER lookback 20.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### T-05 Time-series momentum

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Long 12-1m return > 0; vol-scaled.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Demo #1 with V-02.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### T-06 Percentile-rank momentum + hysteresis

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Rank vs own past; band entry/exit.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Walk-forward required.
8. Demo #7.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### T-07 Multi-horizon momentum ensemble

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Average 5/10/20/60d mom signals.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### T-08 Vol-filtered trend

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
TSMOM when vol < 90d median.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### T-09 52-week high breakout

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Long within 0–5% of 252d high.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### T-10 QQQ/BTC Donchian rotation

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Hold stronger breakout; else cash.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: QQQUSDT, BTCUSDT at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Demo #8.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### T-11 Session volume momentum

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
13:30–15:00 UTC volume + 30m return sign.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV at `1h` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### T-12 Hour-of-day vol premium tilt

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Long bias 00:00 UTC; reduce 02:00–06:00.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV at `1h` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### T-13 Network momentum (single hub)

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
BTC 20d mom → ETH next day.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: BTC+ETH at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### T-14 Trend in FX majors

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
MA cross on EURUSD, GBPUSD.

#### Added Value
Captures directional persistence; core demo family for lab. Note: yfinance FX.

#### Integration Steps
1. Data: FX OHLCV at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### T-15 Commodity dual momentum

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Absolute + relative mom on GLD, USO.

#### Added Value
Captures directional persistence; core demo family for lab. Note: yfinance.

#### Integration Steps
1. Data: Commodity OHLCV at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---
## Part A2 — Mean Reversion

### MR-01 Bollinger fade

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Fade band touches.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. 20, 2σ.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### MR-02 RSI oversold bounce

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Long RSI<30; exit >50.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### MR-03 RSI + ER gate

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
MR-02 when ER>0.5.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Use with MR-15.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### MR-04 Z-score price vs MA

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Long z<-2 vs 20d MA.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### MR-05 Intraday gap fade

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Fade gap >1–3%.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV at `1h` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### MR-06 Short-term reversal

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Long after -2σ daily return.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### MR-07 Turnaround Tuesday

**Section:** Class: event | **Fit:** Native | **Priority:** M

#### Logic
Long Mon close if Fri red.

#### Added Value
Calendar/microstructure timing effects.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: EVENT` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Demo #9.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### MR-08 Turn-of-month

**Section:** Class: event | **Fit:** Native | **Priority:** M

#### Logic
Long last day + first 3 days.

#### Added Value
Calendar/microstructure timing effects.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: EVENT` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### MR-09 Holiday effect

**Section:** Class: event | **Fit:** Native | **Priority:** M

#### Logic
Pre/post holiday drift.

#### Added Value
Calendar/microstructure timing effects.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: EVENT` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### MR-10 Pairs ratio MR

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
BTC/ETH spread z-score.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: 2× OHLCV at `1d` frequency.
2. Set `strategy_type: MR` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### MR-11 RSI on detrended

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
HPF detrend + RSI(2).

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### MR-12 Overnight intraday reversal

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Fade overnight move first hour.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV at `1h` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### MR-13 24h ticker artifact fade

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Fade before 24h roll-off.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV at `1h` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### MR-14 Low-volume fade

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Fade >1σ move on low volume.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### MR-15 QQQ mean reversion

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
RSI(4) MR with 200d SMA filter.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: QQQ at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Ref: `qqq_rsi2_mr`.
8. Demo #5.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---
## Part A3 — Volatility

### V-01 Realized vol breakout

**Section:** Class: vol | **Fit:** Native | **Priority:** M

#### Logic
Long vol when 20d crosses above 60d.

#### Added Value
Manages risk and exploits vol premia/regimes.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: VOL` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### V-02 Vol targeting overlay

**Section:** Class: vol | **Fit:** Native | **Priority:** M

#### Logic
Scale to 15% ann vol target.

#### Added Value
Manages risk and exploits vol premia/regimes.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: VOL` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Overlay on T-05.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### V-03 Vol regime switch

**Section:** Class: vol | **Fit:** Native | **Priority:** M

#### Logic
Trend in low vol tercile; cash in high.

#### Added Value
Manages risk and exploits vol premia/regimes.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: VOL` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### V-04 SAR seasonal vol forecast

**Section:** Class: vol | **Fit:** Native | **Priority:** M

#### Logic
AR+24h+168h vol sizing.

#### Added Value
Manages risk and exploits vol premia/regimes.

#### Integration Steps
1. Data: OHLCV at `1h` frequency.
2. Set `strategy_type: VOL` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### V-05 VIX term structure

**Section:** Class: vol | **Fit:** Native | **Priority:** M

#### Logic
Short vol when VIX < MA, contango.

#### Added Value
Manages risk and exploits vol premia/regimes. Note: yfinance ^VIX.

#### Integration Steps
1. Data: ^VIX at `1d` frequency.
2. Set `strategy_type: VOL` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### V-06 Intraday straddle proxy

**Section:** Class: vol | **Fit:** Native | **Priority:** M

#### Logic
Long vol after DVOL proxy spike.

#### Added Value
Manages risk and exploits vol premia/regimes.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: VOL` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### V-07 GARCH vol gate

**Section:** Class: vol | **Fit:** Native | **Priority:** M

#### Logic
Trade when GARCH forecast < realized.

#### Added Value
Manages risk and exploits vol premia/regimes.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: VOL` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### V-08 Entropy chop filter

**Section:** Class: vol | **Fit:** Native | **Priority:** M

#### Logic
MR high entropy; trend low.

#### Added Value
Manages risk and exploits vol premia/regimes.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: VOL` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---
## Part A4 — Tactical Asset Allocation

### TAA-01 Faber 10-month SMA

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Long above 10M SMA else cash.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: Multi OHLCV at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### TAA-02 Dual momentum TAA

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Faber + pick stronger asset.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: Multi OHLCV at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### TAA-03 Distressed TAA rotation

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Rotate to worst recent performer.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: Strategy returns at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### TAA-04 Risk parity lite

**Section:** Class: vol | **Fit:** Native | **Priority:** M

#### Logic
1/σ equal risk weights.

#### Added Value
Manages risk and exploits vol premia/regimes.

#### Integration Steps
1. Data: Multi OHLCV at `1d` frequency.
2. Set `strategy_type: VOL` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### TAA-05 Bond filter for equities

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Long SPY if yield trend down.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: TLT+SPY at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### TAA-06 Gold/dollar/rates triangle

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Long gold when yields fall, DXY weak.

#### Added Value
Captures directional persistence; core demo family for lab. Note: yfinance.

#### Integration Steps
1. Data: GLD,DXY at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### TAA-07 Crypto vs equity rotation

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
BTC risk-on; cash risk-off.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: SPY,BTC at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### TAA-08 Crisis convexity sleeve

**Section:** Class: vol | **Fit:** Native | **Priority:** M

#### Logic
Long vol when skew extreme.

#### Added Value
Manages risk and exploits vol premia/regimes.

#### Integration Steps
1. Data: Vol proxy at `1d` frequency.
2. Set `strategy_type: VOL` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---
## Part A5 — Cross-Sectional

### XS-01 Cross-sectional momentum

**Section:** Class: cross-section | **Fit:** Native | **Priority:** M

#### Logic
L/S top/bottom 20d return deciles.

#### Added Value
Showcases Binance universe scanning.

#### Integration Steps
1. Data: Binance universe at `1d` frequency.
2. Set `strategy_type: CROSS-SECTION` and complexity `X` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Demo #6.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### XS-02 RSI rank L/S

**Section:** Class: cross-section | **Fit:** Native | **Priority:** M

#### Logic
CS z-score RSI extremes.

#### Added Value
Showcases Binance universe scanning.

#### Integration Steps
1. Data: Universe at `1d` frequency.
2. Set `strategy_type: CROSS-SECTION` and complexity `X` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### XS-03 Vol-scaled momentum

**Section:** Class: cross-section | **Fit:** Native | **Priority:** M

#### Logic
Rank return/vol.

#### Added Value
Showcases Binance universe scanning.

#### Integration Steps
1. Data: Universe at `1d` frequency.
2. Set `strategy_type: CROSS-SECTION` and complexity `X` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### XS-04 Short-term reversal CS

**Section:** Class: cross-section | **Fit:** Native | **Priority:** M

#### Logic
Long worst 5d decile.

#### Added Value
Showcases Binance universe scanning.

#### Integration Steps
1. Data: Universe at `1d` frequency.
2. Set `strategy_type: CROSS-SECTION` and complexity `X` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### XS-05 Price-path convexity

**Section:** Class: cross-section | **Fit:** Native | **Priority:** M

#### Logic
Rank low convexity.

#### Added Value
Showcases Binance universe scanning.

#### Integration Steps
1. Data: Universe at `1d` frequency.
2. Set `strategy_type: CROSS-SECTION` and complexity `X` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### XS-06 Network momentum CS

**Section:** Class: cross-section | **Fit:** Native | **Priority:** M

#### Logic
Neighbor-weighted momentum.

#### Added Value
Showcases Binance universe scanning.

#### Integration Steps
1. Data: Universe at `1d` frequency.
2. Set `strategy_type: CROSS-SECTION` and complexity `X` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### XS-07 Dollar volume filter

**Section:** Class: cross-section | **Fit:** Native | **Priority:** M

#### Logic
XS-01 top 50 liquid.

#### Added Value
Showcases Binance universe scanning.

#### Integration Steps
1. Data: Universe at `1d` frequency.
2. Set `strategy_type: CROSS-SECTION` and complexity `X` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### XS-08 Funding carry rank

**Section:** Class: carry | **Fit:** Native | **Priority:** M

#### Logic
L/S by 7d mean funding.

#### Added Value
Crypto-native funding/basis edge.

#### Integration Steps
1. Data: Universe+funding at `1d` frequency.
2. Set `strategy_type: CARRY` and complexity `X` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### XS-09 Beta-neutral momentum

**Section:** Class: cross-section | **Fit:** Native | **Priority:** M

#### Logic
Long mom; hedge BTC beta.

#### Added Value
Showcases Binance universe scanning.

#### Integration Steps
1. Data: Universe+BTC at `1d` frequency.
2. Set `strategy_type: CROSS-SECTION` and complexity `X` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### XS-10 Demeaned return target

**Section:** Class: cross-section | **Fit:** Native | **Priority:** M

#### Logic
Predict CS rank next week.

#### Added Value
Showcases Binance universe scanning.

#### Integration Steps
1. Data: Universe at `1d` frequency.
2. Set `strategy_type: CROSS-SECTION` and complexity `X` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---
## Part B — Coinglass

### CG-01 Funding rate carry

**Section:** Class: carry | **Fit:** Native | **Priority:** M

#### Logic
Long when funding < -X.

#### Added Value
Crypto-native funding/basis edge.

#### Integration Steps
1. Data: OHLCV+Coinglass (funding) at `1d/1h` frequency.
2. Set `strategy_type: CARRY` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `funding` from `data/coinglass/`.
8. Lag 1 bar.
9. Demo #3.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-02 Funding extreme fade

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Fade crowded funding.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV+Coinglass (funding) at `1d/1h` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `funding` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-03 OI expansion breakout

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Price up + OI up.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV+Coinglass (OI) at `1d/1h` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `OI` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-04 OI divergence fade

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Price high, OI falling.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV+Coinglass (OI+price) at `1d/1h` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `OI+price` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-05 Liquidation cascade fade

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Long after liq > 95th pctile.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV+Coinglass (liquidations) at `1d/1h` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `liquidations` from `data/coinglass/`.
8. Lag 1 bar.
9. Demo #10.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-06 Short squeeze setup

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Neg funding + price up + short liqs.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV+Coinglass (funding+liq) at `1d/1h` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `funding+liq` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-07 Taker buy imbalance

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
taker_buy ratio > 0.55.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV+Coinglass (taker flow) at `1d/1h` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `taker flow` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-08 Orderbook imbalance

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
(bids-asks)/(bids+asks).

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV+Coinglass (orderbook) at `1d/1h` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `orderbook` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-09 Whale index gate

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Trend when whale_index low.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV+Coinglass (whale_index) at `1d/1h` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `whale_index` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-10 Global L/S fade

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Fade extreme positioning.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV+Coinglass (positioning) at `1d/1h` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `positioning` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-11 Net position momentum

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Follow net_long_change.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV+Coinglass (net_position) at `1d/1h` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `net_position` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-12 ETF flow momentum

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Long on 5d positive ETF flow.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: OHLCV+Coinglass (etf_flows) at `1d/1h` frequency.
2. Set `strategy_type: TREND` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `etf_flows` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-13 ETF flow divergence

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Price down + inflows.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV+Coinglass (etf+price) at `1d/1h` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `etf+price` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-14 ETF premium discount

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Buy extreme discount.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV+Coinglass (etf_premium) at `1d/1h` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `etf_premium` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-15 Exchange balance drain

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Bullish on negative 30d Δ balance.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV+Coinglass (exchange_balance) at `1d/1h` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `exchange_balance` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-16 Puell multiple bottom

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Long puell < 0.5.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV+Coinglass (puell) at `1d/1h` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `puell` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-17 Basis carry

**Section:** Class: carry | **Fit:** Native | **Priority:** M

#### Logic
Long spot/short perp on basis.

#### Added Value
Crypto-native funding/basis edge.

#### Integration Steps
1. Data: OHLCV+Coinglass (basis) at `1d/1h` frequency.
2. Set `strategy_type: CARRY` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `basis` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-18 Multi-factor BTC bottoming

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Composite capitulation score.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV+Coinglass (composite) at `1d/1h` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `composite` from `data/coinglass/`.
8. Lag 1 bar.
9. Demo #4.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-19 Funding-weighted CS mom

**Section:** Class: cross-section | **Fit:** Native | **Priority:** M

#### Logic
XS-01 ex high funding.

#### Added Value
Showcases Binance universe scanning.

#### Integration Steps
1. Data: OHLCV+Coinglass (funding+universe) at `1d/1h` frequency.
2. Set `strategy_type: CROSS-SECTION` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `funding+universe` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### CG-20 Liq + funding extreme

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Both liq spike and funding extreme.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV+Coinglass (liq+funding) at `1d/1h` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Coinglass `liq+funding` from `data/coinglass/`.
8. Lag 1 bar.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---
## Part C1 — On-chain Valuation

### ON-01 MVRV Z-score

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Long when CapMVRVZ < −1; exit > 2.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV + Talos (CapMVRVZ, CapMVRVCur) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Talos: `CapMVRVZ, CapMVRVCur`.
8. Verify in `data/talos_data_catalog.json`.
9. Lag 1 day.
10. Priority demo #2.
11. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
12. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
13. One robustness test per turn via `tqg-robustness-followup` skill.
14. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### ON-02 NUPL regime

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Long in capitulation (NUPL < 0.25); reduce > 0.75.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV + Talos (NUPL) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Talos: `NUPL`.
8. Verify in `data/talos_data_catalog.json`.
9. Lag 1 day.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### ON-03 Realized price support

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Long when price < CapRealUSD × 1.05.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV + Talos (CapRealUSD, PriceUSD) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Talos: `CapRealUSD, PriceUSD`.
8. Verify in `data/talos_data_catalog.json`.
9. Lag 1 day.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### ON-04 MVRV < 1 deep value

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Accumulate when MVRV < 1; trim > 3.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV + Talos (CapMVRVCur) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Talos: `CapMVRVCur`.
8. Verify in `data/talos_data_catalog.json`.
9. Lag 1 day.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### ON-05 NVT high fade

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Reduce when NVTAdj > 90d 90th pctile.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV + Talos (NVTAdj, NVTAdj90) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Talos: `NVTAdj, NVTAdj90`.
8. Verify in `data/talos_data_catalog.json`.
9. Lag 1 day.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### ON-06 SOPR capitulation

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Long when SOPR < 1 persists 7d.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV + Talos (SOPR*) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Talos: `SOPR*`.
8. Verify in `data/talos_data_catalog.json`.
9. Lag 1 day.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### ON-07 STH cost basis reclaim

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Long breakout above STH cost proxy.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV + Talos (realized cap variants) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Talos: `realized cap variants`.
8. Verify in `data/talos_data_catalog.json`.
9. Lag 1 day.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### ON-08 LTH supply expansion

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Bearish when SplyLTH rising fast + price down.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV + Talos (SplyLTH) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Talos: `SplyLTH`.
8. Verify in `data/talos_data_catalog.json`.
9. Lag 1 day.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### ON-09 Accumulation trend score proxy

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Long when wallet balance metrics rise.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV + Talos (AdrBal*, SplyAdrBal*) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Talos: `AdrBal*, SplyAdrBal*`.
8. Verify in `data/talos_data_catalog.json`.
9. Lag 1 day.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### ON-10 Realized loss exhaustion

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Long when realized loss peaks then declines 30%.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV + Talos (loss proxies) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Talos: `loss proxies`.
8. Verify in `data/talos_data_catalog.json`.
9. Lag 1 day.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---
## Part C2 — Network Activity

### NA-01 Active address momentum

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Long when AdrActCnt 30d ROC > 0.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV + Talos (AdrActCnt) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Talos: `AdrActCnt`.
8. Lag 1 day.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### NA-02 Tx count breakout

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Long when TxCnt > 90d MA.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV + Talos (TxCnt) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Talos: `TxCnt`.
8. Lag 1 day.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### NA-03 Transfer value surge

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Risk-off when TxTfrValAdjUSD spikes + price down.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV + Talos (TxTfrValAdjUSD) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Talos: `TxTfrValAdjUSD`.
8. Lag 1 day.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### NA-04 Fee spike fade

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
MR after FeeMeanUSD > 95th pctile.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV + Talos (FeeMeanUSD) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Talos: `FeeMeanUSD`.
8. Lag 1 day.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### NA-05 New address growth

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Long alts with AdrNewCnt/price divergence.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: OHLCV + Talos (AdrNewCnt) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Talos: `AdrNewCnt`.
8. Lag 1 day.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---
## Part C3 — Exchange Flows

### EF-01 Exchange net outflow

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Long on 7d negative net flow.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: Talos FlowNet* / Coinglass balance at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Lag 1 day.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### EF-02 Miner to exchange

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Bearish on miner outflow spikes.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: Talos mining flows at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Lag 1 day.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### EF-03 ETF vs exchange flow combo

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Risk-on when ETF in + exchange out.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: Coinglass ETF + balance at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Lag 1 day.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### EF-04 Stablecoin flow

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Risk-on on stablecoin exchange inflows.

#### Added Value
Glassnode-style layered confirmation. Note: Requires user upload.

#### Integration Steps
1. Data: needs upload at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Lag 1 day.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---
## Part C4 — Derivatives (Talos)

### DV-01 Funding rate trend

**Section:** Class: carry | **Fit:** Native | **Priority:** M

#### Logic
Follow 30d cumulative funding sign.

#### Added Value
Crypto-native funding/basis edge.

#### Integration Steps
1. Data: OHLCV + Talos/Coinglass (futures_cumulative_funding_rate_*) at `1d` frequency.
2. Set `strategy_type: CARRY` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Metrics: `futures_cumulative_funding_rate_*`.
8. Lag 1 day.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### DV-02 OI / market cap ratio

**Section:** Class: carry | **Fit:** Native | **Priority:** M

#### Logic
Fade high OI/MCAP extremes.

#### Added Value
Crypto-native funding/basis edge.

#### Integration Steps
1. Data: OHLCV + Talos/Coinglass (open_interest_reported_* + cap) at `1d` frequency.
2. Set `strategy_type: CARRY` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Metrics: `open_interest_reported_* + cap`.
8. Lag 1 day.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### DV-03 Options OI put/call

**Section:** Class: carry | **Fit:** Native | **Priority:** M

#### Logic
Risk-off when put OI > call OI by X%.

#### Added Value
Crypto-native funding/basis edge.

#### Integration Steps
1. Data: OHLCV + Talos/Coinglass (open_interest_reported_option_*) at `1d` frequency.
2. Set `strategy_type: CARRY` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Metrics: `open_interest_reported_option_*`.
8. Lag 1 day.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### DV-04 Vol term structure

**Section:** Class: carry | **Fit:** Native | **Priority:** M

#### Logic
Long gamma proxy when short vol < long vol.

#### Added Value
Crypto-native funding/basis edge.

#### Integration Steps
1. Data: OHLCV + Talos/Coinglass (VtyDayRet30d vs 180d) at `1d` frequency.
2. Set `strategy_type: CARRY` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Metrics: `VtyDayRet30d vs 180d`.
8. Lag 1 day.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### DV-05 Perp vs spot volume

**Section:** Class: carry | **Fit:** Native | **Priority:** M

#### Logic
Leverage excess when perp/spot vol ratio high.

#### Added Value
Crypto-native funding/basis edge.

#### Integration Steps
1. Data: OHLCV + Talos/Coinglass (volume_reported_*) at `1d` frequency.
2. Set `strategy_type: CARRY` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Metrics: `volume_reported_*`.
8. Lag 1 day.
9. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
10. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
11. One robustness test per turn via `tqg-robustness-followup` skill.
12. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---
## Part C5 — Glassnode Multi-factor

### GF-01 Deep value accumulator

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
MVRV<1 AND exchange balance ↓ 14d AND ETF flows ≥ 0.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: Multi-source (valuation+flows) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Layers: valuation+flows.
8. Weighted score → position size.
9. Per-layer pass/fail in report.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### GF-02 Bear market late-stage

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
LTH loss 30d SMA falling AND ETF outflow improving.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: Multi-source (LTH+ETF) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Layers: LTH+ETF.
8. Weighted score → position size.
9. Per-layer pass/fail in report.
10. Priority demo #4.
11. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
12. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
13. One robustness test per turn via `tqg-robustness-followup` skill.
14. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### GF-03 Recovery confirmation

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Price > realized AND neutral funding AND taker buy > 0.52.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: Multi-source (price+deriv) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Layers: price+deriv.
8. Weighted score → position size.
9. Per-layer pass/fail in report.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### GF-04 Risk-off de-risk

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Vol ↑ + ETF outflows + rising exchange balance.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: Multi-source (vol+flows) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Layers: vol+flows.
8. Weighted score → position size.
9. Per-layer pass/fail in report.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### GF-05 Macro liquidity BTC

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Long BTC when DXY < 200d MA AND BTC > 200d MA.

#### Added Value
Glassnode-style layered confirmation. Note: GF-05 needs yfinance DXY; GF-07 needs options strike upload.

#### Integration Steps
1. Data: Multi-source (DXY+BTC) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Layers: DXY+BTC.
8. Weighted score → position size.
9. Per-layer pass/fail in report.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### GF-06 Dollar inverse sleeve

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Scale BTC by rolling −corr(BTC,DXY).

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: Multi-source (BTC+DXY) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Layers: BTC+DXY.
8. Weighted score → position size.
9. Per-layer pass/fail in report.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### GF-07 Max pain pin

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Mean-revert to max OI strike.

#### Added Value
Glassnode-style layered confirmation. Note: GF-05 needs yfinance DXY; GF-07 needs options strike upload.

#### Integration Steps
1. Data: Multi-source (options strikes) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Layers: options strikes.
8. Weighted score → position size.
9. Per-layer pass/fail in report.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### GF-08 Vol compression breakout

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Breakout when 30d vol at 1y low.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: Multi-source (ATR percentile) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Layers: ATR percentile.
8. Weighted score → position size.
9. Per-layer pass/fail in report.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### GF-09 STH resistance rejection

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Fade at STH cost; stop on reclaim.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: Multi-source (cost basis) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Layers: cost basis.
8. Weighted score → position size.
9. Per-layer pass/fail in report.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### GF-10 Full Week 28 playbook

**Section:** Class: multi-factor | **Fit:** Native | **Priority:** M

#### Logic
Weighted scorecard across macro/on-chain/ETF/deriv.

#### Added Value
Glassnode-style layered confirmation.

#### Integration Steps
1. Data: Multi-source (all layers) at `1d` frequency.
2. Set `strategy_type: MULTI-FACTOR` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Layers: all layers.
8. Weighted score → position size.
9. Per-layer pass/fail in report.
10. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
11. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
12. One robustness test per turn via `tqg-robustness-followup` skill.
13. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---
## Part D — Intermarket

### IA-01 BTC leads ETH

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Trade ETH in direction of BTC 1d return.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: Multi-symbol OHLCV (BTC, ETH) at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Symbols: BTC, ETH.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### IA-02 SPY leads BTCUSDT

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Risk-on filter for crypto longs.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: Multi-symbol OHLCV (SPY, BTC) at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Symbols: SPY, BTC.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### IA-03 Gold/BTC ratio MR

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Fade PAXGUSDT/BTC ratio z-score.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: Multi-symbol OHLCV (PAXGUSDT, BTC) at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Symbols: PAXGUSDT, BTC.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### IA-04 Copper/gold ratio

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Risk-on when copper/gold rising.

#### Added Value
Captures directional persistence; core demo family for lab. Note: IA-04 needs yfinance HG, GLD.

#### Integration Steps
1. Data: Multi-symbol OHLCV (HG, GLD) at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Symbols: HG, GLD.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### IA-05 Oil shock risk-off

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Reduce BTC when USO 5d return > 8%.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: Multi-symbol OHLCV (USO, BTC) at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Symbols: USO, BTC.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### IA-06 Rates proxy trend

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Gate NVDAUSDT with TLT trend.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: Multi-symbol OHLCV (TLT, NVDAUSDT) at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Symbols: TLT, NVDAUSDT.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### IA-07 Equity perp basket

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Long strongest SPY/QQQ/NVDA 20d mom.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: Multi-symbol OHLCV (equity perps) at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Symbols: equity perps.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### IA-08 ETH/BTC rotation

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Hold higher 20d risk-adj momentum.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: Multi-symbol OHLCV (ETH, BTC) at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Symbols: ETH, BTC.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### IA-09 DXY risk filter

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Scale crypto longs by DXY trend.

#### Added Value
Captures directional persistence; core demo family for lab. Note: yfinance DXY.

#### Integration Steps
1. Data: Multi-symbol OHLCV (DXY + universe) at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Symbols: DXY + universe.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### IA-10 Intermarket divergence

**Section:** Class: trend | **Fit:** Native | **Priority:** M

#### Logic
Trade lagging leg after leader move.

#### Added Value
Captures directional persistence; core demo family for lab.

#### Integration Steps
1. Data: Multi-symbol OHLCV (2-leg pair) at `1d` frequency.
2. Set `strategy_type: TREND` and complexity `M` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Symbols: 2-leg pair.
8. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
9. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
10. One robustness test per turn via `tqg-robustness-followup` skill.
11. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---
## Part E — Quantocracy / yfinance

### Q-01 Accrual anomaly

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Short high accruals, long low.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates. Note: Needs fundamentals upload.

#### Integration Steps
1. Data: fundamentals at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### Q-02 PEAD

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Drift with earnings surprise.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates. Note: Needs earnings data.

#### Integration Steps
1. Data: earnings at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### Q-03 Dividend premium

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Long dividend payers.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates. Note: Needs fundamentals.

#### Integration Steps
1. Data: fundamentals at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### Q-04 Short interest / retail options

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Fade crowded retail.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates. Note: Needs upload.

#### Integration Steps
1. Data: options SI at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### Q-05 Crack spread / refiner lag

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Long refiners vs crack.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates. Note: Needs crack spread data.

#### Integration Steps
1. Data: futures+equities at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### Q-06 VIX risk premium

**Section:** Class: vol | **Fit:** Native | **Priority:** M

#### Logic
Short vol ETP when VIX elevated vs realized.

#### Added Value
Manages risk and exploits vol premia/regimes. Note: yfinance ^VIX.

#### Integration Steps
1. Data: ^VIX, VXX at `1d` frequency.
2. Set `strategy_type: VOL` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### Q-07 0DTE intraday vol

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Intraday vol breakout on SPY.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates. Note: Needs intraday upload.

#### Integration Steps
1. Data: intraday SPY at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### Q-08 Recursive LS prediction

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Online regression forecast per bar.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: any OHLCV at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### Q-09 HMM regime overlay

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
2-state HMM gates base strategy.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates.

#### Integration Steps
1. Data: OHLCV at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

### Q-10 Margin debt risk-off

**Section:** Class: MR | **Fit:** Native | **Priority:** M

#### Logic
Reduce equity when margin debt/GDP extreme.

#### Added Value
Exploits short-term overreaction; pairs well with ER gates. Note: Needs macro upload.

#### Integration Steps
1. Data: macro at `1d` frequency.
2. Set `strategy_type: MR` and complexity `S` in `strategy_spec.json`.
3. Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).
4. Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.
5. Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.
6. Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.
7. Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.
8. Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.
9. One robustness test per turn via `tqg-robustness-followup` skill.
10. Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.

---

## Lab rules (all strategies)

1. Lag non-price features **1 bar** — no same-bar lookahead.
2. Join alt-data on **UTC date** aligned to bar close.
3. Document units in `strategy_spec.json` (funding 8h vs 1d, annualization).
4. Crypto annualization **365**; equity perps **252**.
5. Costs: crypto perp **4–10 bps** RT minimum; stress **2×** in robustness.
6. **One** robustness test per user message.

## References

- `docs/research/implementable-strategies-from-sources.md`
- `data/README_DATA_FORMAT.md`
- Example run: `runs/qqq_rsi2_mr/`
