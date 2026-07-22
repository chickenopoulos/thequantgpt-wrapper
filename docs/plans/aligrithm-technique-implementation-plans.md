# Aligrithm Technique Implementation Plans

> **Source:** `docs/research/aligrithm-quant-techniques-for-tqg.md`  
> **Purpose:** One plan per technique — **Logic**, **Added Value**, **Integration Steps**.  
> **Generated:** 2026-07-22

---

## How to read

| Field | Meaning |
|-------|---------|
| **Logic** | What the technique does |
| **Added Value** | Why it strengthens the Cursor Lab |
| **Integration Steps** | Concrete TQG implementation actions |

---

### 1.1 Systems as recipes, not prophecies

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** H

#### Logic
Encode repeatable processes: inputs → rules → outputs. Strategies are falsifiable recipes, not forecasts.

#### Added Value
Agents produce auditable research artifacts instead of opaque predictions.

#### Integration Steps
1. Require complete `strategy_spec.json` on every run.
2. Add `edge_source` field for economic hypothesis.
3. Block packaging without spec via `tqg-package-run` skill.
4. Split `report.md`: rules vs interpretation.

---

### 1.2 Signal–execution gap

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** H

#### Logic
Edge erodes via costs, sizing, psychology, and alpha decay between signal and fill.

#### Added Value
Research reflects deployability; fewer strategies that fail post-cost.

#### Integration Steps
1. Default `fee`/`slippage` in `run.json`.
2. Vol-target sizing in `tqg_client/portfolio.py`.
3. Document `expected_half_life_days` in spec.
4. Stress at 2× costs in robustness.

---

### 1.3 Rule vs strategy vs portfolio

**Section:** §1 Scientific Trader | **Fit:** Extend | **Priority:** M

#### Logic
Separate signal generation, sizing, and portfolio allocation layers.

#### Added Value
Reuse signals across sizing policies; cleaner complex runs.

#### Integration Steps
1. Split `code/` into `signals.py`, `sizing.py`, `portfolio.py` when needed.
2. Set `workflow: multi_layer` in spec.
3. Report signal-only vs sized returns in metrics.

---

### 1.4 Scientific = falsifiable

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** H

#### Logic
Every hypothesis needs null, benchmark, and replication.

#### Added Value
Evidence-based validation; fewer narrative backtests.

#### Integration Steps
1. MCP enforces benchmark in `tqg_validate_strategy_code`.
2. Auto buy-and-hold + random-rule baselines.
3. Store baselines in `artifacts/metrics.json`.

---

### 1.5 Loss control > prediction

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** H

#### Logic
Survival compounds; drawdown limits and kill switches dominate hit rate.

#### Added Value
Runs halt before catastrophic OOS failure.

#### Integration Steps
1. Add `max_drawdown_kill` to spec and `run.json`.
2. Simulate kill-switch in backtest engine.
3. Report max DD and time-underwater.
4. Stub live monitoring in `RUN.md`.

---

### 1.6 Rhyme not repeat

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** H

#### Logic
Persistent stats (momentum, MR, vol clustering, fat tails) beat chart patterns.

#### Added Value
Strategy families map to literature; less episode overfitting.

#### Integration Steps
1. Tag `stat_family` in spec.
2. PSA on parameter neighborhoods.
3. Document family in `report.md`.

---

### 1.7 Loose pants / general ideas

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** H

#### Logic
Robust rules survive instruments, regimes, and parameter bands.

#### Added Value
PSA and plateaus become first-class.

#### Integration Steps
1. Default first robustness = PSA in `tqg-robustness-followup`.
2. PSA heatmaps in `charts/`.
3. Reject spike optima.
4. Cross-symbol test with fixed params.

---

### 1.8 Portfolio of systems

**Section:** §1 Scientific Trader | **Fit:** Extend | **Priority:** M

#### Logic
Single systems die on regime change; uncorrelated systems smooth equity.

#### Added Value
Multi-run aggregation research track.

#### Integration Steps
1. Combine equity curves via `tqg_client/portfolio.py`.
2. Workflow `multi_strategy_portfolio`.
3. Report run correlation matrix.

---

### 1.9 Probability business

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** H

#### Logic
Edge manifests over N trades; single outcomes are noise.

#### Added Value
Sharpe CIs and min trade-count gates.

#### Integration Steps
1. SE(Sharpe) ≈ 1/√N in metrics.
2. Class-specific `min_trades` gates (200–1000).
3. Report 95% CI in `report.md`.

---

### 1.10 Engineered boredom

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** M

#### Logic
Pre-computed signals, batched execution, vol targeting — no discretionary overrides.

#### Added Value
Deterministic reproducible baseline runs.

#### Integration Steps
1. Document no-discretion policy in `RUN.md`.
2. Vectorized signals only.
3. Optional vol-target in `portfolio.py`.

---

### 1.11 TA as hypothesis

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** H

#### Logic
Operationalize trigger; permutation/block-bootstrap null for thresholds.

#### Added Value
Statistical significance for any TA rule.

#### Integration Steps
1. Permutation module in robustness skill.
2. Store p-value in `artifacts/robustness/`.
3. Gate thresholds on significance.

---

### 1.12 Backtest = experiment

**Section:** §1 Scientific Trader | **Fit:** Extend | **Priority:** H

#### Logic
Detrend returns; separate beta exposure from residual edge.

#### Added Value
Distinguishes long bias from alpha.

#### Integration Steps
1. Decompose total = beta + residual returns.
2. Add `beta_symbol` in spec.
3. Six-test diagnostic panel in extended validation.

---

### 1.13 One backtest ≈ uninformative

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** H

#### Logic
Single path has wide Sharpe CI; need WF, bootstrap, multiple OOS.

#### Added Value
Honest uncertainty reporting.

#### Integration Steps
1. Walk-forward via `tqg_get_robustness_spec`.
2. Bootstrap trade CIs.
3. Multiple OOS windows in spec.

---

### 1.14 History is n=1

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** M

#### Logic
Cannot resample universes; use stress scenarios and regime stratification.

#### Added Value
Honest language in agent outputs.

#### Integration Steps
1. Regime-stratified metrics.
2. Stress scenarios in robustness.
3. Regime coverage matrix as gate.

---

### 1.15 Induction uncertainty

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** H

#### Logic
Past ≠ future distribution; test IS/OOS regime overlap.

#### Added Value
Diagnose regime shift vs overfit on OOS failure.

#### Integration Steps
1. IS/OOS vol/trend/correlation overlap report.
2. Output `artifacts/regime_overlap.json`.
3. Flag unrepresented OOS regimes.

---

### 1.16 Null: no edge

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** H

#### Logic
Default = no edge; random baseline + deflated Sharpe required to deploy.

#### Added Value
Quantt/Quantocracy false-discovery control.

#### Integration Steps
1. Random-signal baseline every run.
2. DSR with trial count.
3. RMP for scan rows.
4. Fail validation if DSR below threshold.

---

### 1.17 Benchmark discipline

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** H

#### Logic
Long bias masquerades as alpha; bias-matched random + symbol benchmark.

#### Added Value
Appropriate benchmarks per asset class.

#### Integration Steps
1. Auto benchmark by `asset_class`.
2. Bias-matched random entry.
3. Benchmark overlay on equity chart.

---

### 1.18 Predictive power vs long bias

**Section:** §1 Scientific Trader | **Fit:** Extend | **Priority:** H

#### Logic
95% exposure / 5% edge common; six-test panel detects long bias.

#### Added Value
Catches leveraged-beta strategies.

#### Integration Steps
1. Six-test panel in `artifacts/diagnostics/six_test.json`.
2. MCP references panel.

---

### 1.19 Falsifiable TA (7 steps)

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** H

#### Logic
Pre-commit entry, exit, horizon, success metric before testing.

#### Added Value
Scientific protocol in spec template.

#### Integration Steps
1. Spec fields: `entry_rule`, `exit_rule`, `horizon_bars`, `success_metric`.
2. Pre-registration via `run.json` `created_at`.
3. New run_id for rule changes.

---

### 1.20 Explanation ≠ prediction

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** M

#### Logic
Post-hoc stories are cheap; separate narrative from pre-registered rules.

#### Added Value
Clearer agent communication.

#### Integration Steps
1. `report.md` sections: Rules | Results | Post-hoc.
2. Spec immutable after first execution.

---

### 1.21 Simplicity as weapon

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** H

#### Logic
Parameters inflate SE and search space; degrees-of-freedom budget.

#### Added Value
Parsimony enforced in validation.

#### Integration Steps
1. Count DoF in spec.
2. 10% rule: params/trades < 10%.
3. Complexity score in metrics.

---

### 1.22 11-stage scientific protocol

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** H

#### Logic
Gated pipeline: idea → data → spec → code → validate → backtest → robustness → package.

#### Added Value
Maps to TQG workflow end-to-end.

#### Integration Steps
1. Track stages in `run.json` `completed_steps`.
2. Package requires prior stages.
3. Align with `cursor-lab-setup-sop.md`.

---

### 1.23 Theory of edge

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** M

#### Logic
Document edge source: constraints, premia, capacity, pain tolerance.

#### Added Value
Capacity-aware research narrative.

#### Integration Steps
1. `edge_source` enum in spec.
2. One paragraph in `report.md`.

---

### 1.24 Alpha decay = competition

**Section:** §1 Scientific Trader | **Fit:** Native | **Priority:** M

#### Logic
Published edges crowd; shorter half-life for literature-replicated strategies.

#### Added Value
Conservative expectations for known strategies.

#### Integration Steps
1. Tag `literature_replicated: true`.
2. Shorter default half-life.
3. Decay warning in validation.

---

### 1.25 Marginal buyer framing

**Section:** §1 Scientific Trader | **Fit:** Extend | **Priority:** L

#### Logic
Price set by next participant; on-chain supply/demand context.

#### Added Value
Richer narrative for flow/on-chain strategies.

#### Integration Steps
1. Narrative layer in reports for Talos/Coinglass runs.
2. Link holder metrics from catalog.

---

### 1.26 Large trade ≠ insider signal

**Section:** §1 Scientific Trader | **Fit:** Extend | **Priority:** M

#### Logic
Impact manufactures moves; permanent vs temporary impact matters.

#### Added Value
Caution on whale-flow strategies.

#### Integration Steps
1. Caveat in whale-index strategies (CG-09).
2. Prefer flow persistence over single prints.

---

### 2.1 Five quality components

**Section:** §2 Indicator Engineering | **Fit:** Extend | **Priority:** H

#### Logic
MI, stationarity, distribution, tails, theory.

#### Added Value
Feature QA ceiling before models.

#### Integration Steps
1. `tqg_client/features/qa.py` checklist.
2. Output `artifacts/feature_qa.json`.

---

### 2.2 Four garbage defects

**Section:** §2 Indicator Engineering | **Fit:** Extend | **Priority:** H

#### Logic
Non-stationary, heavy tails, clumps, lookback artifacts.

#### Added Value
Automated feature failure detection.

#### Integration Steps
1. ADF, kurtosis, clustering checks in QA.
2. Link to transform ladder.

---

### 2.3 Pre-model transforms

**Section:** §2 Indicator Engineering | **Fit:** Extend | **Priority:** H

#### Logic
Six causal repair transforms.

#### Added Value
Standard transform library.

#### Integration Steps
1. `tqg_client/features/transforms.py`.
2. Document chain in spec.

---

### 2.7 Threshold scan null

**Section:** §2 Indicator Engineering | **Fit:** Native | **Priority:** H

#### Logic
Full threshold scan vs shuffled target.

#### Added Value
Honest PSA thresholds.

#### Integration Steps
1. PSA varies threshold; compare to null.
2. `tqg_get_robustness_spec` PSA path.

---

### 2.9 Ban raw price levels

**Section:** §2 Indicator Engineering | **Fit:** Native | **Priority:** H

#### Logic
Use returns/ratios only.

#### Added Value
Cross-asset comparable features.

#### Integration Steps
1. MCP rejects raw close as signal.
2. Set `feature_basis: returns` in spec.

---

### 2.10 Stationarity transform ladder

**Section:** §2 Indicator Engineering | **Fit:** Extend | **Priority:** H

#### Logic
Lightest transform passing ADF.

#### Added Value
Default feature hygiene.

#### Integration Steps
1. Ladder in transforms module.
2. Log chosen transform in artifacts.

---

### 2.11 ATR normalization

**Section:** §2 Indicator Engineering | **Fit:** Native | **Priority:** H

#### Logic
Vol-scale returns for cross-asset.

#### Added Value
Core momentum primitive.

#### Integration Steps
1. `atr_normalized_return()` helper.
2. Used in T-02, T-05, XS-03.

---

### 2.12 CMMA momentum primitive

**Section:** §2 Indicator Engineering | **Fit:** Native | **Priority:** H

#### Logic
ATR-norm log price minus lagged MA.

#### Added Value
Better than raw MA cross.

#### Integration Steps
1. Implement in features or strategy T-02.
2. PSA on lookback k.

---

### 2.16 Feature engineering >> model

**Section:** §2 Indicator Engineering | **Fit:** Native | **Priority:** H

#### Logic
90–95% edge in features.

#### Added Value
Agents exhaust features before ML.

#### Integration Steps
1. Skill checklist before model swaps.

---

### 2.17 Filters ≠ predictors

**Section:** §2 Indicator Engineering | **Fit:** Native | **Priority:** H

#### Logic
Filters summarize past; document lag.

#### Added Value
Realistic indicator expectations.

#### Integration Steps
1. Lag audit per indicator in spec.

---

### 2.18 Lag tax of MAs

**Section:** §2 Indicator Engineering | **Fit:** Native | **Priority:** H

#### Logic
SMA(N) lag ≈ (N−1)/2.

#### Added Value
Horizon discipline.

#### Integration Steps
1. Warn if horizon < 2× lag.

---

### 2.22 High-pass / detrender

**Section:** §2 Indicator Engineering | **Fit:** Native | **Priority:** M

#### Logic
MR on detrended series.

#### Added Value
MR-11 foundation.

#### Integration Steps
1. `detrend()` helper in features.

---

### 2.27 Cascaded lag budget

**Section:** §2 Indicator Engineering | **Fit:** Native | **Priority:** M

#### Logic
Sum lags across stacks.

#### Added Value
Block structurally late signals.

#### Integration Steps
1. Sum `lag_bars` in spec.
2. Validation warning on excess lag.

---

### 2.28 Median filter for volume

**Section:** §2 Indicator Engineering | **Fit:** Native | **Priority:** M

#### Logic
Outlier-resistant volume features.

#### Added Value
T-11, MR-14 support.

#### Integration Steps
1. Median volume before thresholds.

---

### 2.36–2.74 Full DSP catalog

**Section:** §2 Indicator Engineering | **Fit:** Future | **Priority:** L

#### Logic
Hilbert, homomorphic filters, advanced DSP.

#### Added Value
R&D reference only.

#### Integration Steps
1. Internal training doc.
2. No baseline implementation.

---

### 3.1 Stationarity precondition

**Section:** §3 Robust Systems Lab | **Fit:** Native | **Priority:** H

#### Logic
ADF/KPSS on returns/features.

#### Added Value
Baseline regime diagnostics.

#### Integration Steps
1. ADF in validation.
2. `artifacts/regime_diagnostics.json`.

---

### 3.5 OOS failure = stationarity failure

**Section:** §3 Robust Systems Lab | **Fit:** Native | **Priority:** H

#### Logic
Regime overlap before blaming overfit.

#### Added Value
Better OOS diagnostics.

#### Integration Steps
1. IS/OOS overlap report (Tier 1).

---

### 3.6 Vol regime gating

**Section:** §3 Robust Systems Lab | **Fit:** Native | **Priority:** H

#### Logic
Stratify Sharpe by vol tercile.

#### Added Value
Honest attribution.

#### Integration Steps
1. `metrics.json` `by_regime.vol_tercile`.

---

### 3.11 Regime coverage matrix

**Section:** §3 Robust Systems Lab | **Fit:** Native | **Priority:** H

#### Logic
Vol × trend × correlation cells.

#### Added Value
Deployment gate.

#### Integration Steps
1. `artifacts/regime_coverage.json`.
2. Min positive cells to pass.

---

### 3.12 Plateau > peak

**Section:** §3 Robust Systems Lab | **Fit:** Native | **Priority:** H

#### Logic
Pick plateau center in PSA.

#### Added Value
Core robustness doctrine.

#### Integration Steps
1. PSA heatmaps; select center not peak.

---

### 3.16 Degrees of freedom budget

**Section:** §3 Robust Systems Lab | **Fit:** Native | **Priority:** H

#### Logic
Count all DoF categories.

#### Added Value
Overfit prevention.

#### Integration Steps
1. Auto-count from spec.
2. 10% rule gate.

---

### 3.18 10% rule

**Section:** §3 Robust Systems Lab | **Fit:** Native | **Priority:** H

#### Logic
params/effective_trades < 10%.

#### Added Value
Exploratory vs deployable.

#### Integration Steps
1. Fail deployable if violated.

---

### 3.21 Monte Carlo flavors

**Section:** §3 Robust Systems Lab | **Fit:** Native | **Priority:** H

#### Logic
Bootstrap trades vs synthetic paths.

#### Added Value
Robustness option.

#### Integration Steps
1. MC via `tqg_get_robustness_spec`.

---

### 3.22 Permutation tests

**Section:** §3 Robust Systems Lab | **Fit:** Native | **Priority:** H

#### Logic
Block perm for autocorrelated features.

#### Added Value
Indicator significance.

#### Integration Steps
1. Block length from autocorr.

---

### 3.23 CSCV / PBO

**Section:** §3 Robust Systems Lab | **Fit:** Extend | **Priority:** H

#### Logic
Combinatorial purged CV overfit prob.

#### Added Value
Gold-standard overfit control.

#### Integration Steps
1. `tqg_client/robustness/cscv.py` (Tier 3).

---

### 3.24 Walk-forward > single OOS

**Section:** §3 Robust Systems Lab | **Fit:** Native | **Priority:** H

#### Logic
Distribution of OOS steps.

#### Added Value
Landolfi validation.

#### Integration Steps
1. Rolling WF in robustness bundle.

---

### 3.31 Costs early

**Section:** §3 Robust Systems Lab | **Fit:** Native | **Priority:** H

#### Logic
Costs in baseline not afterthought.

#### Added Value
Realistic metrics.

#### Integration Steps
1. Never primary pre-cost Sharpe.
2. 2× cost stress.

---

### 3.32 32-item integrity checklist

**Section:** §3 Robust Systems Lab | **Fit:** Native | **Priority:** H

#### Logic
Deployment readiness.

#### Added Value
MCP validation alignment.

#### Integration Steps
1. Map to `tqg_mcp_validate.py` rules.

---

### 3.37 Collinear parameter sweeps

**Section:** §3 Robust Systems Lab | **Fit:** Native | **Priority:** H

#### Logic
Fix one MA, vary other.

#### Added Value
Honest dual-MA PSA.

#### Integration Steps
1. PSA template for MA pairs.

---

### 4.1 Noise ≠ volatility

**Section:** §4 Market Structure | **Fit:** Native | **Priority:** H

#### Logic
Same vol, opposite tradeability.

#### Added Value
Use ER with ATR.

#### Integration Steps
1. Compute ER alongside ATR.

---

### 4.2 Efficiency ratio (ER)

**Section:** §4 Market Structure | **Fit:** Native | **Priority:** H

#### Logic
|net move|/total path; 0–1.

#### Added Value
Primary regime classifier.

#### Integration Steps
1. `efficiency_ratio()` helper.
2. Gates T-04, MR-03.

---

### 4.4 High noise → MR

**Section:** §4 Market Structure | **Fit:** Native | **Priority:** H

#### Logic
Gate fades when ER high.

#### Added Value
MR only in chop.

#### Integration Steps
1. `er_min` param default 0.5.

---

### 4.5 Low noise → trend

**Section:** §4 Market Structure | **Fit:** Native | **Priority:** H

#### Logic
Breakouts when ER low.

#### Added Value
T-04 Donchian gate.

#### Integration Steps
1. `er_max` param default 0.3.

---

### 4.12 Strategy routing matrix

**Section:** §4 Market Structure | **Fit:** Extend | **Priority:** H

#### Logic
ER→family; vol→size.

#### Added Value
Meta-strategy router.

#### Integration Steps
1. `meta_router.py` research module.

---

### 4.24 Network momentum

**Section:** §4 Market Structure | **Fit:** Extend | **Priority:** H

#### Logic
Neighbor asset momentum signal.

#### Added Value
T-13, XS-06, IA-01.

#### Integration Steps
1. Lead-lag or correlation graph.
2. Tier 2 network module.

---

### 4.25+ Session / calendar structure

**Section:** §4 Market Structure | **Fit:** Native | **Priority:** M

#### Logic
Hour-of-day and calendar effects.

#### Added Value
T-11, MR-07–09.

#### Integration Steps
1. `hour_utc`, `day_of_week` features.

---

### 5.13 Order book imbalance (OBI)

**Section:** §5 Microstructure Alpha | **Fit:** Extend | **Priority:** H

#### Logic
(bid−ask)/(bid+ask) from Coinglass.

#### Added Value
CG-08 strategy.

#### Integration Steps
1. Coinglass orderbook join.
2. Lag 1 bar.

---

### 5.15 Trade flow autocorrelation

**Section:** §5 Microstructure Alpha | **Fit:** Extend | **Priority:** H

#### Logic
Taker buy/sell persistence.

#### Added Value
CG-07 strategy.

#### Integration Steps
1. Coinglass taker flow features.

---

### 5.22 Crypto vol seasonality

**Section:** §5 Microstructure Alpha | **Fit:** Native | **Priority:** H

#### Logic
Spikes 14:00, 00:00 UTC.

#### Added Value
T-12 hourly tilt.

#### Integration Steps
1. Hour-of-day dummies on 1h bars.

---

### 5.25 24h rolling return artifact

**Section:** §5 Microstructure Alpha | **Fit:** Native | **Priority:** M

#### Logic
Fade ticker roll mirage.

#### Added Value
MR-13 strategy.

#### Integration Steps
1. Detect 24h roll-off on 1h bars.

---

### 5.26 Volume confirms stickiness

**Section:** §5 Microstructure Alpha | **Fit:** Native | **Priority:** H

#### Logic
High vol continuation; low vol revert.

#### Added Value
MR-14.

#### Integration Steps
1. Volume percentile gate.

---

### 5.35 Square-root market impact

**Section:** §5 Microstructure Alpha | **Fit:** Extend | **Priority:** M

#### Logic
Slippage ∝ size^0.5.

#### Added Value
Non-linear costs.

#### Integration Steps
1. `impact_model: sqrt` in run defaults.

---

### 6.1 Ranking > forecasting

**Section:** §6 Portfolio Construction | **Fit:** Native | **Priority:** H

#### Logic
Cross-sectional sort beats point forecast.

#### Added Value
XS family foundation.

#### Integration Steps
1. `workflow: cross_sectional` in spec.

---

### 6.3 Vol-adjusted sizing

**Section:** §6 Portfolio Construction | **Fit:** Native | **Priority:** H

#### Logic
1/σ weights; vol targeting.

#### Added Value
V-02 overlay.

#### Integration Steps
1. `vol_target_annual` in spec.
2. `portfolio.py` helper.

---

### 6.46 Signal averaging

**Section:** §6 Portfolio Construction | **Fit:** Native | **Priority:** H

#### Logic
Ensemble parameter variants.

#### Added Value
T-07 multi-horizon.

#### Integration Steps
1. `ensemble_weights` in spec.

---

### 6.47 Trend follower build

**Section:** §6 Portfolio Construction | **Fit:** Native | **Priority:** H

#### Logic
7-stage trend program template.

#### Added Value
Crypto trend demos.

#### Integration Steps
1. Checklist in strategy plans.
2. Demo `btc_tsmom_vol_target`.

---

### 6.49 Percentile-rank momentum + hysteresis

**Section:** §6 Portfolio Construction | **Fit:** Native | **Priority:** H

#### Logic
Landolfi low-churn momentum.

#### Added Value
T-06 priority demo.

#### Integration Steps
1. Rank vs own past; WF validation required.

---

### 7.1 α + βλ decomposition

**Section:** §7 Cross-Sectional & Factors | **Fit:** Native | **Priority:** H

#### Logic
Separate BTC beta from alpha.

#### Added Value
XS-09 evaluation.

#### Integration Steps
1. Rolling OLS vs BTC in metrics.

---

### 7.2 Portfolio sorts

**Section:** §7 Cross-Sectional & Factors | **Fit:** Extend | **Priority:** H

#### Logic
Decile L/S on 600+ perps.

#### Added Value
XS-01 showcase.

#### Integration Steps
1. Universe from `binance_futures_ohlcv_1d.parquet`.

---

### 7.5 Factor zoo / mult. testing

**Section:** §7 Cross-Sectional & Factors | **Fit:** Native | **Priority:** H

#### Logic
DSR, Bonferroni on scans.

#### Added Value
CS false-discovery control.

#### Integration Steps
1. DSR with scan count.

---

### 7.16 Target transform > features

**Section:** §7 Cross-Sectional & Factors | **Fit:** Native | **Priority:** H

#### Logic
Rank/demean forward return as target.

#### Added Value
XS-10; Tier 1 backlog.

#### Integration Steps
1. CS rank target for prediction.

---

### 8.6 Entropy as chop gauge

**Section:** §8 Physics & Geometry | **Fit:** Extend | **Priority:** M

#### Logic
Up/down entropy ≈1 chop.

#### Added Value
V-08 filter.

#### Integration Steps
1. Binary entropy on return signs.

---

### 8.9 MS-GARCH regime switching

**Section:** §8 Physics & Geometry | **Fit:** Extend | **Priority:** M

#### Logic
2-state vol regime.

#### Added Value
V-03, Q-09 overlay.

#### Integration Steps
1. Lite vol regime gate.

---

### 9.15 Kelly with negative-edge reject

**Section:** §9 Prediction Market Arbitrage (sizing ports) | **Fit:** Native | **Priority:** M

#### Logic
Kelly only when edge > 0.

#### Added Value
Sizing discipline.

#### Integration Steps
1. `kelly_fraction()` capped at fractional Kelly.

---

### 9.40 Longshot bias analog

**Section:** §9 Prediction Market Arbitrage (sizing ports) | **Fit:** Native | **Priority:** M

#### Logic
Fade extreme funding/OI.

#### Added Value
CG-02, CG-10.

#### Integration Steps
1. Extreme percentile gates.

---

### Q-DSR Deflated Sharpe Ratio

**Section:** §10 Quantocracy | **Fit:** Native | **Priority:** H

#### Logic
Adjust Sharpe for trial count.

#### Added Value
Mandated false-discovery control.

#### Integration Steps
1. Trial count from PSA.
2. DSR in validation.

---

### Q-Faber Meb Faber TAA

**Section:** §10 Quantocracy | **Fit:** Native | **Priority:** H

#### Logic
10M SMA tactical allocation.

#### Added Value
TAA-01 demo.

#### Integration Steps
1. Multi-asset via yfinance.

---

### Q-Landolfi Percentile-rank momentum

**Section:** §10 Quantocracy | **Fit:** Native | **Priority:** H

#### Logic
Low-churn momentum.

#### Added Value
T-06 strategy plan.

#### Integration Steps
1. See strategy plan T-06.

---

### Q-HMM HMM regime filter

**Section:** §10 Quantocracy | **Fit:** Extend | **Priority:** M

#### Logic
2-state overlay.

#### Added Value
Q-09 gates base strategy.

#### Integration Steps
1. 2-state HMM on returns/vol.
2. Gate base strategy.

---

### Q-Costs Non-linear transaction costs

**Section:** §10 Quantocracy | **Fit:** Native | **Priority:** H

#### Logic
Size-dependent slippage.

#### Added Value
Sqrt impact model.

#### Integration Steps
1. `impact_model` in run.json.

---

### GN-Macro Macro layer

**Section:** §11 Glassnode Methodology | **Fit:** Extend | **Priority:** H

#### Logic
DXY, real yields, equity correlation filters.

#### Added Value
GF-05, IA-09.

#### Integration Steps
1. yfinance TLT, DXY, SPY joins.

---

### GN-Valuation On-chain valuation

**Section:** §11 Glassnode Methodology | **Fit:** Extend | **Priority:** H

#### Logic
MVRV, NUPL, realized price.

#### Added Value
ON-01–ON-04.

#### Integration Steps
1. Talos loader; lag 1 day.

---

### GN-ETF ETF / institutional

**Section:** §11 Glassnode Methodology | **Fit:** Extend | **Priority:** H

#### Logic
Flows, premium/discount.

#### Added Value
CG-12–CG-14.

#### Integration Steps
1. Coinglass ETF parquets.

---

### GN-Deriv Derivatives layer

**Section:** §11 Glassnode Methodology | **Fit:** Extend | **Priority:** H

#### Logic
Funding, OI, liquidations.

#### Added Value
CG-01–CG-06.

#### Integration Steps
1. Coinglass join on bar index.

---

### GN-Confirm Confirmation logic

**Section:** §11 Glassnode Methodology | **Fit:** Extend | **Priority:** H

#### Logic
Multi-layer alignment before full size.

#### Added Value
GF-01, GF-10 scorecards.

#### Integration Steps
1. Weighted score → position size.
2. Per-layer pass/fail in report.

---

## Tier 1 backlog (ship first)

1. Indicator QA pipeline (§2)
2. Efficiency ratio regime gate (§4)
3. Benchmark + null suite (§1)
4. Deflated Sharpe / trial count (§10)
5. Cost-first backtest (§3.31)
6. IS/OOS regime overlap (§3.5, §3.11)
7. Target transform for cross-section (§7.16)

## References

- `docs/research/aligrithm-quant-techniques-for-tqg.md`
- `AGENTS.md`
- `data/data_dictionary.json`, `data/talos_data_catalog.json`
