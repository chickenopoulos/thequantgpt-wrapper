# Implementable Trading Strategies — Mapped to TheQuantGPT Data

> **Research synthesis** from [Aligrithm](https://aligrithm.com/), [Quantocracy](https://quantocracy.com/), and [Glassnode Week On-chain](https://research.glassnode.com/tag/newsletter/).  
> **Scope:** rule-based strategies backtestable in `runs/<run_id>/` with data under `data/` or public OHLCV via `tqg_client.market_data.load_market_data()`.  
> **Default OOS:** `2025-01-01` unless noted.  
> **Generated:** 2026-07-20

---

## Data inventory summary

| Source | What you have | Coverage (approx.) |
|--------|---------------|-------------------|
| **Binance futures** | OHLCV 1d + 1h, 600+ symbols incl. BTCUSDT, ETHUSDT, SPYUSDT, QQQUSDT, equity perps | 2020-01 → 2026-05 |
| **Talos** | 1,179 on-chain + derivatives metrics, 650+ crypto assets | Asset-specific |
| **Coinglass** | ETF flows, exchange balances, funding, OI, liquidations, orderbook, taker flow, Puell | BTC/ETH + Binance perps |
| **yfinance fallback** | Public equities, ETFs, FX, commodities when no local file | User-driven |
| **Hyperliquid** | 2 datasets (catalogued) | Limited |

**Feature families in catalog:** `price_ohlcv`, `valuation`, `funding`, `network_activity`, `volatility`, `supply`, `etf`, `positioning`, `exchange_flows`, `open_interest`, `liquidations`.

**Not available locally (strategies marked ⚠️ need upload or yfinance):** single-stock fundamentals, VIX spot (⚠️ use `^VIX` via yfinance), options chains (only aggregate OI from Talos), L2/L4 tick data (partial Hyperliquid only), prediction markets.

---

## Strategy format key

| Field | Meaning |
|-------|---------|
| **Data** | Minimum columns/metrics |
| **Freq** | `1d`, `1h`, or mixed |
| **Class** | `trend`, `MR`, `carry`, `vol`, `cross-section`, `event`, `multi-factor` |
| **Complexity** | `S` single-asset, `M` multi-asset, `X` cross-sectional universe |

---

# Part A — OHLCV-only strategies (Binance + yfinance)

These require only `open, high, low, close, volume` — implementable immediately.

## A1. Trend following

| ID | Strategy | Logic | Params | Data | Freq | Src |
|----|----------|-------|--------|------|------|-----|
| T-01 | **Dual moving-average crossover** | Long when fast MA > slow MA | 20/100, 50/200 | OHLCV | 1d | Quantocracy, Aligrithm 6.47 |
| T-02 | **CMMA trend** | Sign of ATR-normalized log-price minus lagged MA | k=20–60 | OHLCV | 1d | Aligrithm 2.12 |
| T-03 | **Donchian breakout** | Long on N-day high break; exit on N/2 low | N=20,55,100 | OHLCV | 1d | Quantocracy (QQQ/BTC rotation) |
| T-04 | **Donchian + ER gate** | T-03 only when efficiency ratio < 0.3 | ER lookback 20 | OHLCV | 1d | Aligrithm 4.5, 4.10 |
| T-05 | **Time-series momentum (TSMOM)** | Long if 12-1 month return > 0; vol-scaled | 21–252d lookback | OHLCV | 1d | Quantocracy, AHL |
| T-06 | **Percentile-rank momentum + hysteresis** | Rank return vs own past; enter/exit bands | Landolfi ranks | OHLCV | 1d | Aligrithm 6.49, Quantocracy |
| T-07 | **Multi-horizon momentum ensemble** | Average 5/10/20/60d momentum signals | 4 speeds | OHLCV | 1d | Aligrithm 6.46, Robot Wealth |
| T-08 | **Vol-filtered trend** | TSMOM active only when realized vol < 90d median | vol gate | OHLCV | 1d | Aligrithm 3.6 |
| T-09 | **52-week high breakout** | Long near 252d high | proximity 0–5% | OHLCV | 1d | Quantocracy literature |
| T-10 | **QQQ/BTC Donchian rotation** | Hold QQQ or BTC by breakout strength; cash if neither | N=5–50d | OHLCV QQQUSDT, BTCUSDT | 1d | Quantocracy 2026 |
| T-11 | **Session volume momentum** | 13:30–15:00 UTC: trade sign of first 30m return if volume rising | 1h bars | OHLCV | 1h | Aligrithm 5.27 |
| T-12 | **Hour-of-day vol premium tilt** | Small long bias at 00:00 UTC, reduce into 02:00–06:00 | hourly | OHLCV | 1h | Aligrithm 5.24 |
| T-13 | **Network momentum (single hub)** | BTC 20d mom → trade ETH next day (fixed lead-lag) | lag 1d | BTC+ETH OHLCV | 1d | Aligrithm 4.24, 10.15 |
| T-14 | **Trend in FX majors** | MA cross on EURUSD, GBPUSD, etc. | 50/200 | OHLCV | 1d | Quantocracy TLDR FX |
| T-15 | **Commodity dual momentum** | Absolute + relative momentum on GLD, USO, etc. | 12-1 | OHLCV | 1d | Quantocracy/Quantpedia |

## A2. Mean reversion

| ID | Strategy | Logic | Params | Data | Freq | Src |
|----|----------|-------|--------|------|------|-----|
| MR-01 | **Bollinger fade** | Short upper band touch, long lower (or long-only fade lower) | 20,2σ | OHLCV | 1d | Classic / Aligrithm ER gate |
| MR-02 | **RSI oversold bounce** | Long RSI < 30; exit RSI > 50 | 14 | OHLCV | 1d | Aligrithm 6.10 pipeline |
| MR-03 | **RSI + ER gate** | MR-02 only when ER > 0.5 | 14, ER 20 | OHLCV | 1d | Aligrithm 4.4, 4.6 |
| MR-04 | **Z-score price vs MA** | Long z < −2; flat/short z > 0 | 20d MA | OHLCV | 1d | Stat arb standard |
| MR-05 | **Intraday gap fade** | Fade open gap > X% on crypto perps | X=1–3% | OHLCV | 1h | Microstructure |
| MR-06 | **Short-term reversal (STR)** | Long after −2σ daily return; hold 1–5d | 1–5d | OHLCV | 1d | Quantocracy multi-ETF study |
| MR-07 | **Turnaround Tuesday** | Long SPY/SPYUSDT Monday close if Friday red | calendar | OHLCV | 1d | Quantocracy TradeQuantiX |
| MR-08 | **Turn-of-month** | Long last day + first 3 days of month | calendar | OHLCV | 1d | Quantocracy TradeQuantiX |
| MR-09 | **Holiday effect** | Pre/post holiday drift on SPY | calendar | OHLCV | 1d | TradeQuantiX |
| MR-10 | **Pairs ratio MR** | Spread z-score on BTC/ETH or correlated perps | 60d | 2× OHLCV | 1d | Aligrithm 4.19 |
| MR-11 | **2-period RSI on detrended** | HPF detrend then RSI | BPF period 20 | OHLCV | 1d | Aligrithm 2.22–2.23 |
| MR-12 | **Overnight vs intraday reversal** | Fade large overnight move in first hour | 1h | OHLCV | 1h | Quantocracy intraday |
| MR-13 | **24h ticker artifact fade** | Front-run hour when large negative rolls out of 24h window | 1h | OHLCV | 1h | Aligrithm 5.25 |
| MR-14 | **Low-volume fade** | Fade >1σ move on <30d median volume | vol confirm | OHLCV | 1d | Aligrithm 5.26 |
| MR-15 | **QQQ mean reversion** | User branch `cursor/qqq-mean-reversion` baseline | TBD | QQQ / QQQUSDT | 1d | Lab demo |

## A3. Volatility & risk premium

| ID | Strategy | Logic | Params | Data | Freq | Src |
|----|----------|-------|--------|------|------|-----|
| V-01 | **Realized vol breakout** | Long vol proxy when 20d vol crosses above 60d | vol windows | OHLCV | 1d | Aligrithm 3.7 |
| V-02 | **Vol targeting overlay** | Scale exposure ∝ target_vol / realized_vol | 15% ann target | OHLCV | 1d | Aligrithm 6.3 |
| V-03 | **Vol regime switch** | Trend in low vol tercile; cash in high | 90d terciles | OHLCV | 1d | Aligrithm 3.6, 8.9 |
| V-04 | **SAR seasonal vol forecast** | Size positions by AR+24h+168h vol forecast | hourly | OHLCV | 1h | Aligrithm 5.23 |
| V-05 | **VIX term structure ⚠️** | Short vol when VIX < MA and contango | ^VIX yfinance | VIX OHLCV | 1d | Quantocracy Concretum |
| V-06 | **Intraday straddle proxy** | Long realized vol after DVOL proxy spike | custom | OHLCV | 1d | Glassnode DVOL narrative |
| V-07 | **GARCH vol forecast gate** | Only trade when forecast vol < realized | GARCH(1,1) | OHLCV | 1d | Aligrithm 8.9 MS-GARCH lite |
| V-08 | **Entropy chop filter** | Trade MR when entropy high; trend when low | binary entropy | OHLCV | 1d | Aligrithm 8.6 |

## A4. Tactical asset allocation (TAA)

| ID | Strategy | Logic | Params | Data | Freq | Src |
|----|----------|-------|--------|------|------|-----|
| TAA-01 | **Faber 10-month SMA** | Long asset if price > 10M SMA else cash/bonds | 10M | Multi OHLCV | 1d | Quantocracy Meb Faber |
| TAA-02 | **Dual momentum TAA** | Faber + pick stronger asset among top | 12M | Multi OHLCV | 1d | Quantocracy |
| TAA-03 | **Distressed TAA rotation** | Rotate into worst recent performer among strategies | 3–6M | Strategy returns | 1d | Quantocracy 2026 series |
| TAA-04 | **Risk parity lite** | Equal risk contribution via 1/σ weights | 60d vol | Multi OHLCV | 1d | Quantocracy |
| TAA-05 | **Bond filter for equities** | Long SPY only if 10Y yield trend down | TLT/IEF + SPY | Multi | 1d | Aligrithm 4.15 |
| TAA-06 | **Gold / dollar / rates triangle** | Long gold when real yields falling + DXY weak | GLD, DXY | Multi | 1d | Aligrithm 4.16, Glassnode macro |
| TAA-07 | **Crypto vs equity rotation** | Risk-on: BTC; risk-off: cash/short perp | SPY, BTC | 1d | Quantocracy, Glassnode |
| TAA-08 | **Crisis convexity sleeve** | Small long vol / short beta when skew extreme | proxy via vol | 1d | Glassnode options narrative |

## A5. Cross-sectional (Binance universe)

Requires scanning many symbols from `binance_futures_ohlcv_1d.parquet`.

| ID | Strategy | Logic | Params | Data | Freq | Src |
|----|----------|-------|--------|------|------|-----|
| XS-01 | **Cross-sectional momentum** | Long top decile 20d return; short bottom | 20d | Universe OHLCV | 1d | Aligrithm 10.2 |
| XS-02 | **RSI rank L/S** | Z-score RSI cross-sectionally; L/S extremes | 14 | Universe | 1d | Aligrithm 6.10 |
| XS-03 | **Vol-scaled momentum** | Rank 20d return / 20d vol | risk-adj | Universe | 1d | Quantocracy |
| XS-04 | **Short-term reversal CS** | Long worst 5d return decile | 5d | Universe | 1d | Quantocracy STR paper |
| XS-05 | **Price-path convexity** | Rank low convexity (path shape) | 20d path | Universe | 1d | Aligrithm 10.14 |
| XS-06 | **Network momentum CS** | Signal = weighted sum neighbor momenta | graph | Universe | 1d | Aligrithm 10.15 |
| XS-07 | **Dollar volume filter** | Trade XS-01 only on top 50 liquidity names | vol filter | Universe | 1d | Practical |
| XS-08 | **Funding carry rank** | Long most negative funding; short positive | 7d mean | OHLCV+funding | 1d | Crypto carry |
| XS-09 | **Beta-neutral momentum** | Long top mom; short BTC beta hedge | BTC | Universe+BTC | 1d | Aligrithm 10.1 |
| XS-10 | **Target = demeaned return** | Predict cross-sectional rank next week | ML optional | Universe | 1d | Aligrithm 10.16 |

---

# Part B — OHLCV + Coinglass strategies

Coinglass files under `data/coinglass/` (31 datasets).

| ID | Strategy | Logic | Coinglass fields | Freq | Src |
|----|----------|-------|------------------|------|-----|
| CG-01 | **Funding rate carry** | Long perp when 8h funding < −X; exit when > 0 | `futures_funding_rate_*` | 1d/1h | Standard crypto |
| CG-02 | **Funding extreme fade** | Fade crowded funding (top decile) | funding OHLC | 1d | Glassnode deriv layer |
| CG-03 | **OI expansion breakout** | Long when price up + OI up (new money) | `futures_open_interest_history_ohlc` | 1d | Glassnode |
| CG-04 | **OI divergence fade** | Price new high but OI falling → fade | OI + price | 1d | On-chain/deriv |
| CG-05 | **Liquidation cascade fade** | Long after long_liq > 95th pctile (capitulation) | `futures_liquidations_*` | 1h/1d | Glassnode, Coinglass |
| CG-06 | **Short squeeze setup** | Negative funding + rising price + short liqs | funding+liq | 1h | Week 28 newsletter |
| CG-07 | **Taker buy imbalance** | Long when taker_buy/(buy+sell) > 0.55 | `*_taker_buy_sell_history_*` | 1h/1d | Aligrithm 5.15 |
| CG-08 | **Orderbook bid/ask imbalance** | Signal = (bids−asks)/(bids+asks) | `*_orderbook_*` | 1h/1d | Aligrithm 5.13 |
| CG-09 | **Whale index gate** | Only take trend signals when whale_index low | `indic_whale_index_*` | 1d | Coinglass |
| CG-10 | **Global long/short account fade** | Fade extreme `global_account_long_short_ratio` | positioning | 1d | Contrarian |
| CG-11 | **Net position change momentum** | Follow `net_long_change` sign | net_position_v2 | 1d | Positioning |
| CG-12 | **ETF flow momentum** | Long BTC when 5d sum `flow_usd` > 0 | `etf_flows_btc` | 1d | Glassnode Week 27–28 |
| CG-13 | **ETF flow divergence** | Price down + ETF inflows = accumulation | flows + price | 1d | Glassnode |
| CG-14 | **ETF premium discount** | Fade extreme discount (capitulation buy) | `etf_premium_discount_btc` | 1d | Institutional |
| CG-15 | **Exchange balance drain** | Bullish when exchange balance 30d Δ negative | `exchange_balance_btc` | 1d | Glassnode supply |
| CG-16 | **Puell multiple bottom** | Long when puell < 0.5; exit > 1.0 | `puell_multiple.csv` | 1d | Miner cap thesis |
| CG-17 | **Basis carry** | Long spot/short perp when `close_basis` > X | `futures_basis_binance_1d` | 1d | Carry |
| CG-18 | **Multi-factor BTC bottoming** | Score: LTH loss cooling + ETF flow improving + funding neutral | composite | 1d | Glassnode Week 28 |
| CG-19 | **Funding-weighted CS momentum** | XS-01 excluding top funding decile longs | funding+universe | 1d | Hybrid |
| CG-20 | **Liquidation + funding double extreme** | Require both liq spike AND funding extreme | liq+funding | 1h | High conviction MR |

---

# Part C — OHLCV + Talos on-chain / valuation strategies

Talos metrics available per asset (BTC, ETH, and 60+ alts for network/valuation). Join on `date` to daily OHLCV.

### C1. Valuation / cycle (Glassnode-aligned)

| ID | Strategy | Logic | Talos metrics | Src |
|----|----------|-------|---------------|-----|
| ON-01 | **MVRV Z-score** | Long when `CapMVRVZ` < −1; exit > 2 | CapMVRVZ, CapMVRVCur | Glassnode, Talos |
| ON-02 | **NUPL regime** | Long in capitulation (NUPL < 0.25); reduce > 0.75 | NUPL | Glassnode |
| ON-03 | **Realized price support** | Long when price < `CapRealUSD` × 1.05 | CapRealUSD, PriceUSD | Week 27–28 |
| ON-04 | **MVRV < 1 deep value** | Accumulate when MVRV < 1; trim > 3 | CapMVRVCur | Classic on-chain |
| ON-05 | **NVT high fade** | Reduce exposure when NVTAdj > 90d 90th pctile | NVTAdj, NVTAdj90 | Network value |
| ON-06 | **SOPR capitulation** | Long when SOPR < 1 persists 7d (if available) | SOPR* | Glassnode |
| ON-07 | **STH cost basis reclaim** | Long breakout when price crosses above STH cost proxy | realized cap variants | Week 28 |
| ON-08 | **LTH supply expansion** | Bearish when `SplyLTH` rising fast + price down | supply active metrics | Glassnode |
| ON-09 | **Accumulation trend score proxy** | Long when small+large wallet balance metrics rise | AdrBal*, SplyAdrBal* | Week 28 |
| ON-10 | **Realized loss exhaustion** | Long when realized loss metric peaks then −30% | loss proxies via flows | Week 27–28 |

*Verify exact Talos field names in `data/talos_data_catalog.json` for each asset.

### C2. Network activity

| ID | Strategy | Logic | Talos metrics | Src |
|----|----------|-------|---------------|-----|
| NA-01 | **Active address momentum** | Long when `AdrActCnt` 30d ROC > 0 | AdrActCnt, AdrAct30dCnt | Network growth |
| NA-02 | **Tx count breakout** | Long when `TxCnt` > 90d MA | TxCnt | Usage |
| NA-03 | **Transfer value surge** | Risk-off when `TxTfrValAdjUSD` spikes + price down | TxTfrValAdjUSD | Distribution |
| NA-04 | **Fee spike fade** | MR after `FeeMeanUSD` > 95th pctile (stress) | FeeMeanUSD | Congestion |
| NA-05 | **New address growth** | Long altcoins with `AdrNewCnt` / price divergence | AdrNewCnt | Alt rotation |

### C3. Exchange flows (Talos + Coinglass)

| ID | Strategy | Logic | Data | Src |
|----|----------|-------|------|-----|
| EF-01 | **Exchange net outflow** | Long when net flow negative 7d | Talos FlowNet* / Coinglass balance | Glassnode |
| EF-02 | **Miner to exchange** | Bearish when miner outflows spike | Talos mining flows | Glassnode |
| EF-03 | **ETF vs exchange flow combo** | Risk-on when ETF in + exchange out | Coinglass ETF + balance | Week 28 |
| EF-04 | **Stablecoin flow ⚠️** | Risk-on when stablecoin exchange inflows | needs upload | Macro crypto |

### C4. Derivatives (Talos)

| ID | Strategy | Logic | Talos metrics | Src |
|----|----------|-------|---------------|-----|
| DV-01 | **Funding rate trend** | Follow 30d cumulative funding sign | futures_cumulative_funding_rate_* | Coinglass+Talos |
| DV-02 | **OI / market cap ratio** | Fade high OI/MCAP at extremes | open_interest_reported_* + cap | Glassnode |
| DV-03 | **Options OI put/call** | Risk-off when put OI > call OI by X% | open_interest_reported_option_* | Week 27–28 |
| DV-04 | **Vol term structure** | Long gamma proxy when short vol < long vol | VtyDayRet30d vs 180d | Talos vol |
| DV-05 | **Perp vs spot volume** | Leverage excess when perp/spot vol ratio high | volume_reported_* | Positioning |

### C5. Multi-factor Glassnode-style regimes

Composite strategies mirroring newsletter *structure* (not discretionary calls):

| ID | Strategy | Layers | Rule sketch |
|----|----------|--------|-------------|
| GF-01 | **Deep value accumulator** | Valuation + flows | MVRV<1 AND exchange balance ↓ 14d AND ETF flows ≥ 0 |
| GF-02 | **Bear market late-stage** | LTH loss + ETF | LTH loss 30d SMA falling AND ETF outflow rate improving |
| GF-03 | **Recovery confirmation** | Price + derivatives | Price > realized price AND funding near neutral AND taker buy > 0.52 |
| GF-04 | **Risk-off de-risk** | Vol + skew + flows | Realized vol ↑ + ETF outflows + rising exchange balance |
| GF-05 | **Macro liquidity BTC** | DXY + BTC | Long BTC when DXY < 200d MA AND BTC above 200d MA ⚠️ yfinance DXY |
| GF-06 | **Dollar inverse sleeve** | Correlation | Scale BTC exposure by rolling −corr(BTC, DXY) |
| GF-07 | **Max pain pin ⚠️** | Options | Mean-revert to strike with max OI (needs options data upload) |
| GF-08 | **Vol compression breakout** | DVOL proxy | Enter breakout when 30d vol at 1y low (ATR percentile) |
| GF-09 | **STH resistance rejection** | Cost basis | Short-term fade at STH cost proxy; stop on reclaim |
| GF-10 | **Full Week 28 playbook** | All layers | Weighted scorecard: macro(1) + on-chain(3) + ETF(2) + deriv(2) → position size |

---

# Part D — Cross-asset & intermarket (multi-symbol OHLCV)

| ID | Strategy | Logic | Symbols | Src |
|----|----------|-------|---------|-----|
| IA-01 | **BTC leads ETH** | Trade ETH in direction of BTC 1d return | BTC, ETH | Lead-lag |
| IA-02 | **SPY leads BTCUSDT** | Risk-on filter for crypto longs | SPY, BTC | Glassnode macro |
| IA-03 | **Gold/BTC ratio MR** | Fade ratio z-score | PAXGUSDT, BTC | Aligrithm 4.19 |
| IA-04 | **Copper/gold ratio** | Risk-on when copper/gold rising | ⚠️ HG, GLD | Aligrithm 4.17 |
| IA-05 | **Oil shock risk-off** | Reduce BTC when USO 5d return > 8% | USO, BTC | Week 27 macro |
| IA-06 | **Rates proxy trend** | Gate equity perps (NVDAUSDT) with TLT trend | TLT, NVDAUSDT | Aligrithm 4.15 |
| IA-07 | **Equity perp basket** | Long strongest of SPY/QQQ/NVDA perps by 20d mom | perps | Binance equity perps |
| IA-08 | **ETH/BTC rotation** | Hold higher 20d risk-adj momentum | ETH, BTC | Relative value |
| IA-09 | **DXY risk filter** | Scale all crypto longs by DXY trend | DXY + universe | Week 28 |
| IA-10 | **Intermarket divergence** | Trade lagging leg when leader moved | 2-leg | Aligrithm 4.20 |

---

# Part E — Quantocracy-sourced equity / vol strategies (yfinance)

⚠️ = requires yfinance or user-uploaded equity files.

| ID | Strategy | Logic | Data | Src |
|----|----------|-------|------|-----|
| Q-01 | **Accrual anomaly ⚠️** | Short high accruals, long low | fundamentals | Quantocracy |
| Q-02 | **PEAD ⚠️** | Drift in direction of earnings surprise | earnings | Quantocracy |
| Q-03 | **Dividend premium ⚠️** | Long dividend payers | fundamentals | Alpha Architect |
| Q-04 | **Short interest / retail options ⚠️** | Fade crowded retail | options SI | Quantocracy 2026 |
| Q-05 | **Crack spread / refiner lag ⚠️** | Long refiners vs crack | futures + equities | Quantocracy |
| Q-06 | **VIX risk premium** | Short vol ETP when VIX elevated vs realized | ^VIX, VXX | Concretum |
| Q-07 | **0DTE intraday vol ⚠️** | Intraday vol breakout on SPY | intraday SPY | Quant Galore |
| Q-08 | **Recursive LS prediction** | Online regression forecast per bar | any OHLCV | OS Quant |
| Q-09 | **HMM regime overlay** | 2-state HMM gates base strategy | OHLCV | TASC / Quantocracy |
| Q-10 | **Margin debt risk-off ⚠️** | Reduce equity when margin debt/GDP extreme | macro | Quantocracy mashup |

---

# Part F — Strategy × data feasibility matrix

| Data tier | Strategy count (this doc) | Ready in lab? |
|-----------|---------------------------|---------------|
| OHLCV only | ~55 | ✅ Yes |
| OHLCV + Coinglass | ~20 | ✅ Yes (loader join needed) |
| OHLCV + Talos | ~35 | ✅ Extend loader |
| Multi-asset OHLCV | ~10 | ✅ Yes |
| yfinance equities/vol | ~10 | ✅ Fallback |
| Fundamentals / options strikes | ~5 | ❌ Upload required |
| L2/L4 microstructure | ~3 | ⚠️ Partial (Hyperliquid) |
| Prediction markets | — | ❌ Out of scope |

---

# Part G — Suggested first implementations for TheQuantGPT demos

Prioritized for **single-asset research sessions** with clean OOS narrative:

1. **BTC TSMOM + vol target** (T-05 + V-02) — baseline trend
2. **BTC MVRV deep value** (ON-01) — on-chain value
3. **BTC funding carry** (CG-01) — derivatives
4. **BTC Glassnode composite GF-02** — multi-factor newsletter style
5. **QQQ mean reversion + ER gate** (MR-15 + MR-03) — equity perp
6. **Binance XS momentum** (XS-01) — cross-section showcase
7. **Percentile-rank momentum** (T-06) — low churn, Aligrithm/Quantocracy
8. **Donchian QQQ/BTC rotation** (T-10) — multi-asset
9. **Turnaround Tuesday SPY** (MR-07) — calendar effect
10. **Liquidation fade 1h** (CG-05) — high-frequency Coinglass

---

# Part H — Implementation notes for agents

1. **Lag all non-price features 1 bar** — no same-bar lookahead (lab rule).
2. **Join alt-data on UTC date** — align Coinglass/Talos timestamps to bar close.
3. **Document units** — funding (8h vs 1d), volume (USD vs contracts) in `strategy_spec.json`.
4. **Annualization** — 365 for crypto, 252 for equity perps treated as equities.
5. **Costs** — crypto perp: assume 4–10 bps round-trip minimum; stress at 2×.
6. **Robustness** — one test per user message (PSA, MC, or cost stress per ladder rule).
7. **Single-name clarity** — state "one symbol only" for single-asset requests.

---

## References

- `data/data_dictionary.json` — 2,020 datasets indexed
- `data/talos_data_catalog.json` — 1,179 metric definitions
- `data/README_DATA_FORMAT.md` — OHLCV conventions
- Aligrithm: https://aligrithm.com/
- Quantocracy: https://quantocracy.com/
- Glassnode Week On-chain: https://research.glassnode.com/tag/newsletter/
