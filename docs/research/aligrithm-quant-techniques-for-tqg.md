# Algorithmic Trading, Signal Generation & Quant Techniques for TheQuantGPT

> **Research synthesis** from [Aligrithm](https://aligrithm.com/) (primary), [Quantocracy](https://quantocracy.com/), and Glassnode *Week On-chain* methodology.  
> **Purpose:** catalogue techniques, workflows, and validation primitives that can strengthen TheQuantGPT Cursor Lab — not a reading list, but an implementation backlog.  
> **Generated:** 2026-07-20

---

## How to use this document

| Column | Meaning |
|--------|---------|
| **TQG fit** | How naturally this maps to current lab capabilities (`runs/`, OHLCV backtests, MCP validation, robustness ladder) |
| **Priority** | `H` = high leverage for lab product; `M` = medium; `L` = niche / needs new infra |

**TQG fit legend:** `Native` = implementable today in rule-based backtests; `Extend` = needs loader/feature work but same architecture; `Future` = new subsystem (L2 book, prediction markets, etc.)

---

## 1. The Scientific Trader — epistemology & workflow (26 articles)

These define *how* TheQuantGPT should reason about evidence, not just what to trade.

| # | Technique / principle | Detail | TQG application | Fit | Pri |
|---|----------------------|--------|-------------------|-----|-----|
| 1.1 | **Systems as recipes, not prophecies** | Repeatable process: inputs → rules → outputs; falsify hypotheses | Encode every strategy as explicit `strategy_spec.json` + rule code; report process not “prediction” | Native | H |
| 1.2 | **Signal–execution gap** | Good ideas die via costs, sizing, psychology, decay | Default cost model in backtests; vol-target sizing; document decay assumptions | Native | H |
| 1.3 | **Rule vs strategy vs portfolio** | Forecast layer ≠ risk layer ≠ allocation layer | Separate `code/signals.py`, `code/sizing.py`, `code/portfolio.py` in complex runs | Extend | M |
| 1.4 | **Scientific = falsifiable** | Must have null, benchmark, replication | MCP `tqg_validate_strategy_code`; mandatory buy-and-hold / random-rule benchmarks | Native | H |
| 1.5 | **Loss control > prediction** | Survival compounds; drawdown limits, kill switches | Pre-specify `max_drawdown_kill`, OOS monitoring in `run.json` | Native | H |
| 1.6 | **Rhyme not repeat** | Persistent stats: momentum, MR, vol clustering, fat tails | Build strategy families around statistical properties, not chart patterns | Native | H |
| 1.7 | **Loose pants / general ideas** | Robust rules survive instruments, regimes, parameter bands | PSA + parameter plateau tests (robustness ladder) | Native | H |
| 1.8 | **Portfolio of systems** | Single-system traders die on regime change | Multi-run aggregation; uncorrelated system portfolio research track | Extend | M |
| 1.9 | **Probability business** | Edge over N trades; single trade meaningless | Report confidence intervals on Sharpe; min trade-count gates | Native | H |
| 1.10 | **Engineered boredom** | Pre-computed signals, batched execution, vol targeting | Agent workflow: no discretionary overrides in baseline runs | Native | M |
| 1.11 | **TA as hypothesis** | Operationalize trigger; simulate null; p-value | Permutation / block-bootstrap null for any rule threshold | Native | H |
| 1.12 | **Backtest = experiment** | Detrend returns; separate drift from edge | Decompose return into exposure + residual; report both | Extend | H |
| 1.13 | **One backtest ≈ uninformative** | Wide CI on Sharpe from one sample path | Walk-forward, bootstrap, multiple OOS windows | Native | H |
| 1.14 | **History is n=1** | Can't resample alternate universes | Stress scenarios; regime stratification; honest uncertainty language | Native | M |
| 1.15 | **Induction uncertainty** | Past ≠ future distribution | Regime overlap tests between IS/OOS | Native | H |
| 1.16 | **Null: no edge** | Default hypothesis; must reject to deploy | Random-signal baseline; deflated Sharpe (Quantocracy/Quantt) | Native | H |
| 1.17 | **Benchmark discipline** | Long bias masquerades as alpha | Bias-matched random entry; symbol-appropriate benchmark | Native | H |
| 1.18 | **Predictive power vs long bias** | 95% exposure / 5% edge common | Six-test diagnostic panel in validation reports | Extend | H |
| 1.19 | **Falsifiable TA (7 steps)** | Operationalize, bound horizon, pre-commit | Strategy spec template: entry, exit, horizon, success metric | Native | H |
| 1.20 | **Explanation ≠ prediction** | Post-hoc stories are cheap | Agent replies: separate in-sample narrative from pre-registered rules | Native | M |
| 1.21 | **Simplicity as weapon** | Parameters inflate SE and search space | Degrees-of-freedom budget in validation | Native | H |
| 1.22 | **11-stage scientific protocol** | Pass/fail gates from idea to deployment | Map to: data audit → spec → code → validate → backtest → robustness → package | Native | H |
| 1.23 | **Theory of edge** | Paid for constraints, premia, capacity, pain | Document edge source in `strategy_spec.json` | Native | M |
| 1.24 | **Alpha decay = competition** | Published edges are crowded | Flag literature-replicated strategies; shorter expected half-life | Native | M |
| 1.25 | **Marginal buyer framing** | Price set by who steps in next | Useful for narrative + on-chain supply/demand overlays | Extend | L |
| 1.26 | **Large trade ≠ insider signal** | Impact manufactures the move | Caution on whale-flow strategies; use permanent vs temporary impact | Extend | M |

---

## 2. Indicator Engineering — feature construction (82 articles)

**Core thesis:** indicator quality sets the ceiling; model class is secondary. TheQuantGPT should invest in *feature pipelines* before model complexity.

### 2A. Indicator quality framework

| # | Technique | Detail | TQG application | Fit | Pri |
|---|-----------|--------|-----------------|-----|-----|
| 2.1 | **Five quality components** | MI with target, stationarity, distribution shape, tails, theory | Feature QA checklist before any ML or threshold rule | Extend | H |
| 2.2 | **Four garbage defects** | Non-stationary, heavy tails, clumped values, lookback artifacts | Automated diagnostics on engineered features | Extend | H |
| 2.3 | **Pre-model transforms** | Six repair transforms; causal computation only | Standard transform library in `tqg_client` | Extend | H |
| 2.4 | **Relative entropy (RE) score** | Histogram utilization; noise can score high | RE as cheap feature filter (not sole gate) | Extend | M |
| 2.5 | **Range/IQR tail diagnostic** | R/IQR detects tail stretch without contaminated σ | Tail audit on indicators | Extend | M |
| 2.6 | **Tail Concentration Ratio (TCR)** | Per-decile MI — signal in tails vs body | Preserve tail signal when squashing outliers | Extend | M |
| 2.7 | **Threshold scan null** | Full scan on shuffled target, not single-threshold p | PSA-style threshold tests | Native | H |
| 2.8 | **Separate long/short thresholds** | Asymmetric conditional distributions | Dual-threshold rules in MR / breakout systems | Native | M |
| 2.9 | **Ban raw price levels** | Non-stationary; cross-instrument incomparable | Always derive from returns, ratios, or normalized spreads | Native | H |
| 2.10 | **Stationarity transform ladder** | Log returns → OHLC diffs → variance scale → ATR-norm → forced centering | Default: lightest transform passing ADF + coverage + rolling-var | Extend | H |
| 2.11 | **ATR normalization** | Structural vol scaling; preserves MI on momentum | `close.pct_change() / ATR` features for cross-asset | Native | H |
| 2.12 | **CMMA momentum primitive** | Log price − lagged MA, ATR-normalized, √(k+1) divisor | Replace raw MA crossover signals | Native | H |
| 2.13 | **Histogram-first diagnostics** | Scalars hide bimodal / light-tail / heavy-tail shapes | Plot feature histograms in run artifacts | Extend | M |
| 2.14 | **Sigmoid tail taming** | Center on train median; scale α for IQR in linear region | Bounded features for tree/linear models | Extend | M |
| 2.15 | **Median > mean for features** | Robust centering under crisis spikes | MAD/IQR spread; Spearman correlation | Native | M |
| 2.16 | **Feature engineering >> model** | 90–95% edge in features (XGBoost example) | Agent skill: exhaust features before model swaps | Native | H |

### 2B. Digital signal processing (DSP) for indicators

| # | Technique | Detail | TQG application | Fit | Pri |
|---|-----------|--------|-----------------|-----|-----|
| 2.17 | **Filters ≠ predictors** | Linear filters summarize past; R²≈0 on next return | Document lag budget per indicator | Native | H |
| 2.18 | **Lag tax of MAs** | SMA(N) lag ≈ (N−1)/2 bars | Lag audit before deploying MR on fast horizons | Native | H |
| 2.19 | **SMA sidelobe leakage** | Worst frequency response vs Hann/Blackman | Prefer Hann/Blackman for smoothing | Extend | L |
| 2.20 | **EMA as 1-pole IIR** | O(1) state; composable building block | EMA chains for trend / detrend | Native | M |
| 2.21 | **Low-pass filter family** | 1-pole 6 dB/oct; 2-pole 12 dB/oct | Super-smoother for trend extraction | Extend | M |
| 2.22 | **High-pass / detrender** | Input − LPF; 2-pole HPF for MR features | Mean-reversion on detrended series | Native | M |
| 2.23 | **Band-pass filter (BPF)** | Reject trend + noise; keep cycle band | Cycle-mode strategies with T, δ params | Extend | M |
| 2.24 | **Decycler** | Trend = price − cycle; less lag than heavy SMA | Trend/cycle decomposition features | Extend | M |
| 2.25 | **Turning-point lag** | MAs report prior regime at inflection | Use cycle detectors for timing-sensitive rules | Extend | M |
| 2.26 | **Frequency response view** | RSI/MACD/Stoch read same 15–40 bar band | De-duplicate redundant indicators | Extend | M |
| 2.27 | **Cascaded lag budget** | Sum lags across filter stacks | Block structurally broken EMA+RSI stacks | Native | M |
| 2.28 | **Median filter for volume** | Nonlinear; outlier-resistant | Volume/TR features before thresholds | Native | M |
| 2.29 | **Automatic Gain Control (AGC)** | Rescale indicator amplitude to regime | Threshold rules that survive 2017 vs 2020 vol | Extend | M |
| 2.30 | **Dominant cycle estimation** | Autocorrelation periodogram; falsifiable vs astrology | Adaptive lookback windows | Extend | L |
| 2.31 | **Evanescent cycles** | Period drifts 8–28 bars; gate cycle strategies | Regime gate on cycle coherence | Extend | M |
| 2.75 | **DSP primer** | Signal, frequency, lag, four filter jobs | Internal training doc for agents | Native | M |

### 2C. Advanced indicator design

| # | Technique | Detail | TQG application | Fit | Pri |
|---|-----------|--------|-----------------|-----|-----|
| 2.32 | **Transfer function H(z)** | Gain, lag, poles from rational filter form | Analytic lag/ringing audit | Future | L |
| 2.33 | **Phase-first design** | Causality couples magnitude & phase; zero-lag impossible | Set lag budget before parameter search | Extend | L |
| 2.34 | **Roofing filter** | Band-limit before building oscillators | Pre-filter noisy alt-data | Extend | M |
| 2.35 | **Adaptive RSI to cycle** | Tune indicator period to measured cycle | Adaptive parameter rules | Extend | M |
| 2.36–2.74 | **Full DSP catalog** | Hilbert, homomorphic filters, two-pole systems, etc. | Reference for advanced feature R&D | Future | L |

---

## 3. Robust Systems Lab — validation & survival (37 articles)

**Directly maps to TheQuantGPT robustness ladder, MCP validation, and `runs/` artifact standards.**

### 3A. Stationarity & regime

| # | Technique | Detail | TQG application | Fit | Pri |
|---|-----------|--------|-----------------|-----|-----|
| 3.1 | **Stationarity precondition** | Rolling stats → ADF/KPSS | Regime diagnostics in baseline reports | Native | H |
| 3.2 | **Slow wandering detection** | CUSUM; long-vs-short divergence | OOS failure diagnostic when ADF passes | Extend | H |
| 3.3 | **Four decay mechanisms** | Crowding, regime drift, microstructure, capacity | Document expected half-life per strategy | Native | M |
| 3.4 | **Eight dying-system metrics** | Early warning months before equity breaks | Live monitoring spec (research mode) | Extend | M |
| 3.5 | **OOS failure = stationarity failure** | Regime overlap test before blaming overfit | Compare IS/OOS vol, trend, correlation cells | Native | H |
| 3.6 | **Vol regime gating** | Lifetime Sharpe is regime-weighted | Stratify metrics by vol tercile | Native | H |
| 3.7 | **Vol more predictable than direction** | ACF +0.27 at 252d; VR 1.8 | Vol features as primary; direction secondary | Native | H |
| 3.8 | **Eight-class stationarity recipes** | Match violation type to transform | Feature repair playbook | Extend | H |
| 3.9 | **Don't destroy signal axis** | 12-1 momentum: raw SR 0.55 → z-scored 0.18 | Transform orthogonal to economic signal only | Native | H |
| 3.10 | **Rolling norm hyperparameter risk** | Window W is DoF; don't tune on live P&L | Structural priors for norm windows | Native | H |
| 3.11 | **Regime coverage matrix** | Vol × trend × correlation × macro cells | Ship only when required cells pass | Native | H |

### 3B. Optimization vs robustness

| # | Technique | Detail | TQG application | Fit | Pri |
|---|-----------|--------|-----------------|-----|-----|
| 3.12 | **Plateau > peak** | IS-optimal ≠ OOS-optimal | Parameter stability maps in PSA | Native | H |
| 3.13 | **"All markets" red flag** | Demand fixed-param matrix after costs | Cross-asset tests with same params | Native | H |
| 3.14 | **Market personality matching** | ER, autocorr, skew, vol driver per asset class | Asset-class tags in `strategy_spec.json` | Native | H |
| 3.15 | **Test before optimize** | Hypothesis → structural prototype → stability map → tune | Agent workflow ordering | Native | H |
| 3.16 | **Degrees of freedom budget** | Count all DoF categories, not just params | Search-width bias correction | Native | H |
| 3.17 | **Parameters sell, break** | More params ↑ IS, ↓ corrected OOS | Penalize complexity in validation | Native | H |
| 3.18 | **10% rule** | params / effective_trades < 10% (prefer <5%) | Hard gate for exploratory vs deployable | Native | H |
| 3.19 | **Trade-count SE** | SE(SR) ≈ 1/√N; report CI | Min trades per strategy class | Native | H |
| 3.20 | **30 trades insufficient** | CLT for mean ≠ deployment readiness | 200–1000 trades for property estimates | Native | H |
| 3.21 | **Monte Carlo flavors** | Bootstrap trades vs synthetic paths | MC robustness follow-up (one per turn) | Native | H |
| 3.22 | **Permutation tests** | Block perm for autocorrelated indicators | Indicator significance in PSA | Native | H |
| 3.23 | **CSCV / PBO** | P(IS-optimal ranks below median OOS) | Combinatorial purged cross-validation | Extend | H |
| 3.24 | **Walk-forward > single OOS** | Distribution of OOS steps | Rolling WF in robustness skill | Native | H |
| 3.25 | **Parameter stability** | Pick plateau center, not peak | PSA output: stability heatmaps | Native | H |
| 3.26 | **Hill / spike / cliff surfaces** | Shape determines deployability | Reject spike optima | Native | H |
| 3.27 | **Stop-loss asymmetry** | MR: stops destroy edge; trend: stops help | Strategy-family-specific stop tests | Native | M |
| 3.28 | **MAE/MFE analysis** | Unrealized loss/gain paths | Pre-stop/target design diagnostic | Extend | M |
| 3.29 | **Profit factor traps** | Dominated by extreme trades | Trimmed PF + Gini of trade P&L | Extend | M |
| 3.30 | **25-metric evaluation panel** | 7 categories beyond net profit | Expand `metrics.json` schema | Extend | M |
| 3.31 | **Costs early** | Pre-cost love → post-cost denial | Costs in baseline, not afterthought | Native | H |
| 3.32 | **32-item integrity checklist** | Deployment readiness artifact | MCP validation checklist alignment | Native | H |
| 3.33 | **Profit factor per bar** | Threshold holds ≠ trades | Bar-based PF for continuous signals | Native | M |
| 3.34 | **Trade-frequency floor** | Permute after flooring min trades | Honest threshold optimization | Native | H |
| 3.35 | **Trend/reversion unified β** | OLS understates lagged-beta magnitude | Use correct estimators for AR features | Extend | L |
| 3.36 | **Folklore gauntlet** | Cause test + mult.comp + perm + costs | Template for user-submitted "edges" | Native | M |
| 3.37 | **Collinear parameter sweeps** | 50/200 vs 60/210 tests one line | 2D sweeps: fix one, vary other | Native | H |

---

## 4. Market Structure Notes — where rules work (71 articles)

| # | Technique | Detail | TQG application | Fit | Pri |
|---|-----------|--------|-----------------|-----|-----|
| 4.1 | **Noise ≠ volatility** | Same vol, opposite tradeability | Efficiency ratio (ER) alongside ATR | Native | H |
| 4.2 | **Efficiency ratio** | \|net move\| / total path; 0–1 | Primary regime classifier | Native | H |
| 4.3 | **Trend quality ranking** | Rank markets before running trend systems | Universe selection for multi-asset runs | Native | H |
| 4.4 | **High noise → MR** | Gate fades on ER; MAE stops | MR only when ER high | Native | H |
| 4.5 | **Low noise → trend** | Breakouts need continuation | Trend only when ER low | Native | H |
| 4.6 | **One indicator, opposite regimes** | RSI 70: MR on FX, trend on crude | ER-gated parameter sets | Native | H |
| 4.7 | **Timeframe selection** | Same market: chop at 1h, trend at 1M | Multi-timeframe spec in strategy | Native | M |
| 4.8 | **Price density** | Visual chop measure ≈ ER | Quick EDA chart | Extend | L |
| 4.9 | **Vol expansion ≠ direction** | ATR up can be noise | Confirm with ER before breakout | Native | H |
| 4.10 | **Breakouts need low noise** | New highs as traps in chop | ER filter on Donchian/breakout | Native | H |
| 4.11 | **Grids need noise** | Vol without round-trips kills grids | Grid research gated on ER | Native | M |
| 4.12 | **Strategy routing matrix** | ER → family; vol → size | Meta-strategy router pattern | Extend | H |
| 4.13–4.24 | **Intermarket analysis** | Bonds filter equities; copper activity; gold/$/rates triangle | Cross-asset filters when multi-symbol data loaded | Extend | M |
| 4.24 | **Network momentum** | Signal from neighbor assets' momentum | Cross-sectional momentum on crypto basket | Extend | H |
| 4.25+ | **Session / calendar structure** | FX session effects, equity open, etc. | Calendar features on hourly data | Native | M |

---

## 5. Microstructure Alpha — execution-aware signals (46 articles)

| # | Technique | Detail | TQG application | Fit | Pri |
|---|-----------|--------|-----------------|-----|-----|
| 5.1–5.8 | **Market making framework** | Fair value, spread, skew; adverse selection | Informs cost model & fill assumptions | Extend | M |
| 5.4 | **Markout analysis** | Post-fill price path = truth serum | Evaluate limit vs market entries | Future | M |
| 5.13 | **Order book imbalance (OBI)** | (bid−ask)/(bid+ask); tail signal | Use Coinglass orderbook parquet | Extend | H |
| 5.14 | **Microprice** | Size-weighted mid | Better fair value for short-horizon | Extend | M |
| 5.15 | **Trade flow autocorrelation** | Signed volume; AR(1) clusters | Taker buy/sell history features | Extend | H |
| 5.17 | **TWAP/VWAP as execution** | Not crossover indicators | Execution benchmark for large orders | Future | L |
| 5.19 | **Maker vs taker economics** | Half-bp matters to makers not takers | Strategy class determines min edge | Native | M |
| 5.22 | **Crypto vol seasonality** | Spikes 14:00, 00:00 UTC | Hour-of-day features on 1h bars | Native | H |
| 5.23 | **SAR vol model** | AR + 24h + 168h seasonal lags | Vol forecast for position sizing | Extend | M |
| 5.24 | **Intraday vol risk premium** | Hour-sliced return/risk (cost-sensitive) | Tilt not standalone strategy | Extend | M |
| 5.25 | **24h rolling return artifact** | Exchange ticker mirage | Feature for uninformed-flow fades | Native | M |
| 5.26 | **Volume confirms stickiness** | High vol → continuation; low → revert | Volume regime switch on directional signal | Native | H |
| 5.27 | **NYSE-open volume momentum** | 13:30–15:00 UTC crypto surge | Session feature on 1h BTC/ETH | Native | M |
| 5.28 | **Arrival/cancel/update rates** | Churn vs resting size | Spoof detection; book quality filter | Extend | M |
| 5.30 | **Order-flow AR(1)** | OLS underestimates φ | Correct AR coefficient for flow features | Extend | L |
| 5.35 | **Square-root market impact** | Walk book; fit a·x^b, b≈0.5 | Slippage model for size sweeps | Extend | M |
| 5.37 | **Event-driven vs bar research** | Bars hide seasonality; fixed rebalance front-runnable | Screen on bars, validate on event time | Extend | M |
| 5.40 | **QLIKE vol loss** | Asymmetric penalty for underestimating vol | Vol model selection metric | Extend | L |
| 5.46 | **L4 on-chain order book** | Full event stream incl. rejects | Hyperliquid data path (2 datasets) | Future | M |

---

## 6. Portfolio Construction & System Death (49 articles)

| # | Technique | Detail | TQG application | Fit | Pri |
|---|-----------|--------|-----------------|-----|-----|
| 6.1 | **Ranking > forecasting** | Cross-sectional sort survives better | Rank-based crypto basket strategies | Native | H |
| 6.2 | **Ranked long/short** | Equal risk top/bottom slices | L/S backtest template | Extend | H |
| 6.4 | **Cost-aware ranking buffer** | No-trade band at slice boundaries | Turnover control in rebalance | Native | H |
| 6.5 | **U-shaped alpha metrics** | Fold to monotone before ranking | Shape diagnostic on features | Extend | M |
| 6.6 | **Z-score before rank** | Scale normalization across names | Cross-sectional z-scoring | Native | H |
| 6.7 | **Indicator → expected value** | Calibrate reading to historical payoff | Bin-wise return lookup | Extend | M |
| 6.8 | **Construction is alpha** | Sizing/correlation moves P&L as much as signal | Joint optimize signal + weights | Extend | M |
| 6.3 | **Vol-adjusted sizing** | 1/σ position weights | Default vol targeting in backtests | Native | H |
| 6.14 | **Expectancy** | E[win] = WR×avg_win − LR×avg_loss | Core metric in trade stats | Native | H |
| 6.18 | **Smooth equity = ensemble** | Uncorrelated systems offset DD | Multi-strategy portfolio runs | Extend | M |
| 6.19 | **Pre-written kill rules** | Permutation envelope breach | `run.json` kill criteria | Native | H |
| 6.32 | **Variance ratio test** | VR>1 trend, VR<1 MR | Regime feature | Native | M |
| 6.33–6.37 | **Fat tails / complex systems** | Size for unmodeled extremes | Stress tests; non-Gaussian MC | Extend | M |
| 6.44 | **Predict residual returns** | Strip beta; forecast idiosyncratic | Factor-neutral crypto strategies | Extend | M |
| 6.46 | **Signal averaging** | 10–20 variants of one alpha; average | Parameter ensemble instead of single optimum | Native | H |
| 6.47 | **Trend follower build** | 7-stage: universe, vol-norm, cap, sector, risk, buffer | Template for futures/crypto trend program | Native | H |
| 6.48 | **TF P&L = f(autocorrelation)** | Closed-form European TF decomposition | Analytic sanity check on trend results | Extend | M |
| 6.49 | **Percentile-rank momentum + hysteresis** | Landolfi low-churn momentum | Implement with walk-forward validation | Native | H |

---

## 7. Cross-Sectional & Factor Investing (16 articles)

| # | Technique | Detail | TQG application | Fit | Pri |
|---|-----------|--------|-----------------|-----|-----|
| 10.1 | **α + βλ decomposition** | Factor exposure vs true alpha | Attribute crypto strategy returns to BTC beta | Native | H |
| 10.2 | **Portfolio sorts** | Deciles, monotonicity, L/S spread | Sort 600+ Binance perps on feature | Extend | H |
| 10.3 | **GRS test** | Joint alpha = missing factor | Multi-strategy alpha attribution | Extend | L |
| 10.4 | **Fama-MacBeth + Shanken** | Correct SE when betas estimated | Cross-sectional factor research | Extend | L |
| 10.5 | **Factor zoo / mult. testing** | t>3 bar; 36% OOS haircut | Deflated Sharpe; Bonferroni on scans | Native | H |
| 10.6 | **ML in asset pricing** | Kelly: ~20% lift not 3× | Temper ML claims in agent outputs | Native | M |
| 10.7 | **Global vs regional models** | Complex models want global data | Pool crypto cross-section globally | Extend | M |
| 10.8 | **Selection vs diversification** | |t|>3 wrong for 18k-signal book | Ensemble many weak signals | Extend | M |
| 10.9 | **SDF unified view** | All factor models = one pricing kernel | Theoretical framing | Future | L |
| 10.11 | **Value repricing vs death** | Structural premium vs spread extreme | Regime narrative for factor drawdowns | Extend | L |
| 10.12 | **Factor timing fails** | Equal-weight factors beat timed | Avoid dynamic factor rotation | Native | M |
| 10.14 | **Price-path convexity** | Shape between endpoints predicts | Path-shape feature on OHLCV | Native | M |
| 10.15 | **Network momentum** | Neighbor momentum graph | Cross-asset momentum on crypto | Extend | H |
| 10.16 | **Target transform > features** | Demean/rank target beats 147 features | Predict cross-sectional rank not raw return | Native | H |

---

## 8. Physics, Geometry & Event-Driven Markets (9 articles)

| # | Technique | Detail | TQG application | Fit | Pri |
|---|-----------|--------|-----------------|-----|-----|
| 8.2 | **Omori aftershock law** | Post-crash elevated vol decays power-law | Reduce size for weeks after crash | Native | M |
| 8.5 | **Randomness non-stationarity** | Markets get more efficient over time | Decay prior Sharpe estimates | Native | M |
| 8.6 | **Entropy as chop gauge** | Up/down word entropy ≈1 chop, ≈0 trend | Alternative ER complement | Extend | M |
| 8.7 | **MI as regime filter** | Gate when structure present | MI between lagged returns and forward return | Extend | M |
| 8.9 | **MS-GARCH regime switching** | Variance regime > factor add-ons | 2-state vol regime model | Extend | M |

---

## 9. Prediction Market Arbitrage (40 articles) — mostly Future for TQG

Valuable for **sizing, calibration, and risk** even if Polymarket execution is out of scope:

| # | Technique | TQG port |
|---|-----------|----------|
| 9.15 | Kelly with auto-reject of negative edge | Position sizing module |
| 9.16 | CVaR-constrained sizing | Tail risk caps in portfolio runs |
| 9.18 | Fast fills = adverse selection | Limit-order fill assumptions |
| 9.35 | Price ≠ probability gap | Calibration mindset for any probabilistic signal |
| 9.38 | Outcome-based RL for calibration | LLM forecast evaluation metric = Brier not accuracy |
| 9.40 | Longshot bias; bet favorites early | Analog: fade extreme funding/OI positioning |

---

## 10. Quantocracy — curated techniques (ongoing feed)

| Source / topic | Technique | TQG application | Pri |
|----------------|-----------|-----------------|-----|
| Quantt | **Sharpe of pure noise** | 2M noise strategies; best look brilliant — mandate DSR/PBO | H |
| Quantt | **Deflated Sharpe Ratio (DSR)** | Adjust for N trials; 99M+ backtest context | H |
| Quantt | **RMP (Random-Max Percentile)** | Per-row luck probability in scans | H |
| OS Quant | **Recursive least-squares regression** | Online beta estimation for adaptive signals | M |
| Concretum | **VIX vol risk premium automation** | Needs VIX OHLCV via yfinance | M |
| Quant Galore | **Vol mean-reversion trap** | IV rank ≠ safe short vol | M |
| TradeQuantiX | **Calendar effects** | Turnaround Tuesday, turn-of-month, holiday — SPY | M |
| Alpha Architect | **Momentum crash risk** | Monitor crowding; diversifiers | M |
| Alpha Architect | **Factor zoo species** | ~400 factors → few independent forces | M |
| Meb Faber / TAA | **Simple MA tactical allocation** | 5 assets, 1 signal, monthly rebalance | H |
| QuantStart | **Quant fund taxonomy** | Strategy family map for user intake | L |
| VertoxQuant | **Plug-in MVO instability** | Shrinkage / robust cov for portfolio runs | M |
| Robot Wealth | **Covariance estimation review** | Ledoit-Wolf etc. for multi-asset | M |
| Quantitativo | **Small market effects → systems** | Rigorous calendar/microstructure effects | H |
| Concretum | **Non-linear transaction costs** | Size-dependent slippage model | H |
| Sepp & Lucic / Man AHL | **Closed-form trend follower P&L** | Validate trend backtests analytically | M |
| Landolfi | **Percentile-rank momentum** | See Aligrithm 6.49 | H |
| Crack spread / refiner lag | **Commodity equity lag** | Needs crack spread + equity (yfinance) | L |
| PEAD / accruals | **Fundamental anomalies** | Needs fundamentals (not in local data yet) | Future |
| HMM regime filter (TASC) | **Regime-switching overlay** | HMM on returns/vol features | M |

---

## 11. Glassnode Week On-chain — analytical methodology (not signals per se)

Glassnode newsletters are **regime narratives** built from layered evidence. TheQuantGPT should replicate the *structure*:

| Layer | Metrics / concepts | How TQG uses them |
|-------|-------------------|-------------------|
| **Macro** | Real yields, DXY, equity correlation, liquidity | yfinance: TLT, DXY, SPY filters on BTC |
| **On-chain valuation** | Realized Price, STH/LTH cost basis, MVRV, NUPL | Talos: `CapRealUSD`, `CapMVRVCur`, `NUPL` |
| **Holder behavior** | LTH realized loss, profit/loss mix, accumulation score | Talos supply/active/revived metrics; Coinglass flows |
| **ETF / institutional** | Net flows, volume SMA, premium/discount | Coinglass ETF parquets |
| **Derivatives** | Funding, OI, put/call, 25Δ skew, max pain, DVOL | Coinglass funding/OI/liquidations; Talos options OI |
| **Confirmation logic** | Require spot + flows + on-chain alignment | Multi-factor rule templates (see strategies doc) |

**Recurring Glassnode decision rules (research-grade, not trading advice):**

1. **Capitulation cooldown** — LTH realized loss peak → declining 30D SMA = potential regime shift (Week 27–28, 2026).
2. **Cost-basis resistance** — Price approaching STH cost basis = supply wall; reclaim = bullish confirmation.
3. **ETF flow divergence** — Outflows easing but not positive = "pressure easing, not resolved."
4. **Derivatives de-risking without spot** — Falling put/call without spot demand = incomplete bottom.
5. **Max pain magnet** — Options pin as gravitational level into expiry.
6. **Vol compression catalyst** — DVOL at 12-month low → breakout risk (direction agnostic).

---

## 12. Recommended TheQuantGPT product integrations (prioritized backlog)

### Tier 1 — ship in baseline workflow
1. **Indicator QA pipeline** — stationarity, R/IQR, histogram, MI stub (Aligrithm §2)
2. **Efficiency ratio regime gate** — route trend vs MR (Aligrithm §4)
3. **Benchmark + null suite** — buy-hold, random signal, bias-matched (Aligrithm §1)
4. **Deflated Sharpe / trial count** — from Quantocracy/Quantt
5. **Cost-first backtest** — slippage + fees before metrics (Aligrithm §3.31)
6. **IS/OOS regime overlap report** — vol, trend, correlation cells (Aligrithm §3.5, §3.11)
7. **Target transform for cross-section** — rank/demean forward returns (Aligrithm §10.16)

### Tier 2 — extend data loaders
8. **Talos metric loader** — 1,179 metrics × 650+ assets
9. **Coinglass feature join** — funding, OI, liquidations, orderbook, ETF flows on bar index
10. **Cross-asset intermarket filters** — BTC + SPY/TLT/DXY alignment

### Tier 3 — research infrastructure
11. **CSCV / PBO module** — combinatorial overfit probability
12. **Walk-forward bundle** — Landolfi-style hysteresis validation
13. **Hour-of-day / session features** — microstructure seasonality
14. **Network momentum graph** — learned or fixed crypto correlation graph

---

## References

- Aligrithm pillars: https://aligrithm.com/ (10 pillars, 300+ articles)
- Quantocracy Quant Mashup: https://quantocracy.com/
- Glassnode Week On-chain: https://research.glassnode.com/tag/newsletter/
- Local data inventory: `data/data_dictionary.json`, `data/talos_data_catalog.json`
