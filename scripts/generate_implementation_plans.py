#!/usr/bin/env python3
"""Generate implementation plan markdown from research synthesis sources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLANS = ROOT / "docs" / "plans"

COMMON_INTEGRATION = [
    "Create run: `python scripts/tqg_create_run.py --title \"<name>\"`.",
    "Set `oos_start_ts` (default `2025-01-01`) in `strategy_spec.json` and `run.json`.",
    "Implement under `runs/<run_id>/code/` only; lag non-price features 1 bar.",
    "Run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`.",
    "Validate: `python scripts/tqg_mcp_validate.py <run_id>` when MCP connected.",
    "One robustness test per turn via `tqg-robustness-followup` skill.",
    "Package: `python scripts/tqg_package_artifacts.py <run_id>` after `validation_passed: true`.",
]


@dataclass
class Plan:
    id: str
    name: str
    logic: str
    value: str
    steps: list[str]
    fit: str = "Native"
    priority: str = "M"
    section: str = ""


def fmt_plan(p: Plan) -> str:
    meta = f"**Fit:** {p.fit} | **Priority:** {p.priority}"
    if p.section:
        meta = f"**Section:** {p.section} | {meta}"
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(p.steps, 1))
    return f"""### {p.id} {p.name}

{meta}

#### Logic
{p.logic}

#### Added Value
{p.value}

#### Integration Steps
{steps}

---
"""


def techniques() -> list[Plan]:
    """Technique plans derived from aligrithm-quant-techniques-for-tqg.md."""
    t: list[Plan] = []

    def add(
        id_: str,
        name: str,
        logic: str,
        value: str,
        steps: list[str],
        fit: str = "Native",
        priority: str = "M",
        section: str = "",
    ) -> None:
        t.append(Plan(id_, name, logic, value, steps, fit, priority, section))

    # §1 Scientific Trader
    sec1 = "§1 Scientific Trader"
    add("1.1", "Systems as recipes, not prophecies",
        "Encode repeatable processes: inputs → rules → outputs. Strategies are falsifiable recipes, not forecasts.",
        "Agents produce auditable research artifacts instead of opaque predictions.",
        ["Require complete `strategy_spec.json` on every run.", "Add `edge_source` field for economic hypothesis.",
         "Block packaging without spec via `tqg-package-run` skill.", "Split `report.md`: rules vs interpretation."],
        priority="H", section=sec1)
    add("1.2", "Signal–execution gap",
        "Edge erodes via costs, sizing, psychology, and alpha decay between signal and fill.",
        "Research reflects deployability; fewer strategies that fail post-cost.",
        ["Default `fee`/`slippage` in `run.json`.", "Vol-target sizing in `tqg_client/portfolio.py`.",
         "Document `expected_half_life_days` in spec.", "Stress at 2× costs in robustness."],
        priority="H", section=sec1)
    add("1.3", "Rule vs strategy vs portfolio",
        "Separate signal generation, sizing, and portfolio allocation layers.",
        "Reuse signals across sizing policies; cleaner complex runs.",
        ["Split `code/` into `signals.py`, `sizing.py`, `portfolio.py` when needed.",
         "Set `workflow: multi_layer` in spec.", "Report signal-only vs sized returns in metrics."],
        fit="Extend", section=sec1)
    add("1.4", "Scientific = falsifiable",
        "Every hypothesis needs null, benchmark, and replication.",
        "Evidence-based validation; fewer narrative backtests.",
        ["MCP enforces benchmark in `tqg_validate_strategy_code`.",
         "Auto buy-and-hold + random-rule baselines.", "Store baselines in `artifacts/metrics.json`."],
        priority="H", section=sec1)
    add("1.5", "Loss control > prediction",
        "Survival compounds; drawdown limits and kill switches dominate hit rate.",
        "Runs halt before catastrophic OOS failure.",
        ["Add `max_drawdown_kill` to spec and `run.json`.", "Simulate kill-switch in backtest engine.",
         "Report max DD and time-underwater.", "Stub live monitoring in `RUN.md`."],
        priority="H", section=sec1)
    add("1.6", "Rhyme not repeat",
        "Persistent stats (momentum, MR, vol clustering, fat tails) beat chart patterns.",
        "Strategy families map to literature; less episode overfitting.",
        ["Tag `stat_family` in spec.", "PSA on parameter neighborhoods.", "Document family in `report.md`."],
        priority="H", section=sec1)
    add("1.7", "Loose pants / general ideas",
        "Robust rules survive instruments, regimes, and parameter bands.",
        "PSA and plateaus become first-class.",
        ["Default first robustness = PSA in `tqg-robustness-followup`.", "PSA heatmaps in `charts/`.",
         "Reject spike optima.", "Cross-symbol test with fixed params."],
        priority="H", section=sec1)
    add("1.8", "Portfolio of systems",
        "Single systems die on regime change; uncorrelated systems smooth equity.",
        "Multi-run aggregation research track.",
        ["Combine equity curves via `tqg_client/portfolio.py`.", "Workflow `multi_strategy_portfolio`.",
         "Report run correlation matrix."], fit="Extend", section=sec1)
    add("1.9", "Probability business",
        "Edge manifests over N trades; single outcomes are noise.",
        "Sharpe CIs and min trade-count gates.",
        ["SE(Sharpe) ≈ 1/√N in metrics.", "Class-specific `min_trades` gates (200–1000).",
         "Report 95% CI in `report.md`."], priority="H", section=sec1)
    add("1.10", "Engineered boredom",
        "Pre-computed signals, batched execution, vol targeting — no discretionary overrides.",
        "Deterministic reproducible baseline runs.",
        ["Document no-discretion policy in `RUN.md`.", "Vectorized signals only.",
         "Optional vol-target in `portfolio.py`."], section=sec1)
    add("1.11", "TA as hypothesis",
        "Operationalize trigger; permutation/block-bootstrap null for thresholds.",
        "Statistical significance for any TA rule.",
        ["Permutation module in robustness skill.", "Store p-value in `artifacts/robustness/`.",
         "Gate thresholds on significance."], priority="H", section=sec1)
    add("1.12", "Backtest = experiment",
        "Detrend returns; separate beta exposure from residual edge.",
        "Distinguishes long bias from alpha.",
        ["Decompose total = beta + residual returns.", "Add `beta_symbol` in spec.",
         "Six-test diagnostic panel in extended validation."], fit="Extend", priority="H", section=sec1)
    add("1.13", "One backtest ≈ uninformative",
        "Single path has wide Sharpe CI; need WF, bootstrap, multiple OOS.",
        "Honest uncertainty reporting.",
        ["Walk-forward via `tqg_get_robustness_spec`.", "Bootstrap trade CIs.",
         "Multiple OOS windows in spec."], priority="H", section=sec1)
    add("1.14", "History is n=1",
        "Cannot resample universes; use stress scenarios and regime stratification.",
        "Honest language in agent outputs.",
        ["Regime-stratified metrics.", "Stress scenarios in robustness.",
         "Regime coverage matrix as gate."], section=sec1)
    add("1.15", "Induction uncertainty",
        "Past ≠ future distribution; test IS/OOS regime overlap.",
        "Diagnose regime shift vs overfit on OOS failure.",
        ["IS/OOS vol/trend/correlation overlap report.", "Output `artifacts/regime_overlap.json`.",
         "Flag unrepresented OOS regimes."], priority="H", section=sec1)
    add("1.16", "Null: no edge",
        "Default = no edge; random baseline + deflated Sharpe required to deploy.",
        "Quantt/Quantocracy false-discovery control.",
        ["Random-signal baseline every run.", "DSR with trial count.", "RMP for scan rows.",
         "Fail validation if DSR below threshold."], priority="H", section=sec1)
    add("1.17", "Benchmark discipline",
        "Long bias masquerades as alpha; bias-matched random + symbol benchmark.",
        "Appropriate benchmarks per asset class.",
        ["Auto benchmark by `asset_class`.", "Bias-matched random entry.", "Benchmark overlay on equity chart."],
        priority="H", section=sec1)
    add("1.18", "Predictive power vs long bias",
        "95% exposure / 5% edge common; six-test panel detects long bias.",
        "Catches leveraged-beta strategies.",
        ["Six-test panel in `artifacts/diagnostics/six_test.json`.", "MCP references panel."],
        fit="Extend", priority="H", section=sec1)
    add("1.19", "Falsifiable TA (7 steps)",
        "Pre-commit entry, exit, horizon, success metric before testing.",
        "Scientific protocol in spec template.",
        ["Spec fields: `entry_rule`, `exit_rule`, `horizon_bars`, `success_metric`.",
         "Pre-registration via `run.json` `created_at`.", "New run_id for rule changes."],
        priority="H", section=sec1)
    add("1.20", "Explanation ≠ prediction",
        "Post-hoc stories are cheap; separate narrative from pre-registered rules.",
        "Clearer agent communication.",
        ["`report.md` sections: Rules | Results | Post-hoc.", "Spec immutable after first execution."],
        section=sec1)
    add("1.21", "Simplicity as weapon",
        "Parameters inflate SE and search space; degrees-of-freedom budget.",
        "Parsimony enforced in validation.",
        ["Count DoF in spec.", "10% rule: params/trades < 10%.", "Complexity score in metrics."],
        priority="H", section=sec1)
    add("1.22", "11-stage scientific protocol",
        "Gated pipeline: idea → data → spec → code → validate → backtest → robustness → package.",
        "Maps to TQG workflow end-to-end.",
        ["Track stages in `run.json` `completed_steps`.", "Package requires prior stages.",
         "Align with `cursor-lab-setup-sop.md`."], priority="H", section=sec1)
    add("1.23", "Theory of edge",
        "Document edge source: constraints, premia, capacity, pain tolerance.",
        "Capacity-aware research narrative.",
        ["`edge_source` enum in spec.", "One paragraph in `report.md`."], section=sec1)
    add("1.24", "Alpha decay = competition",
        "Published edges crowd; shorter half-life for literature-replicated strategies.",
        "Conservative expectations for known strategies.",
        ["Tag `literature_replicated: true`.", "Shorter default half-life.", "Decay warning in validation."],
        section=sec1)
    add("1.25", "Marginal buyer framing",
        "Price set by next participant; on-chain supply/demand context.",
        "Richer narrative for flow/on-chain strategies.",
        ["Narrative layer in reports for Talos/Coinglass runs.", "Link holder metrics from catalog."],
        fit="Extend", priority="L", section=sec1)
    add("1.26", "Large trade ≠ insider signal",
        "Impact manufactures moves; permanent vs temporary impact matters.",
        "Caution on whale-flow strategies.",
        ["Caveat in whale-index strategies (CG-09).", "Prefer flow persistence over single prints."],
        fit="Extend", section=sec1)

    # §2 Indicator Engineering (key items)
    sec2 = "§2 Indicator Engineering"
    indicators = [
        ("2.1", "Five quality components", "MI, stationarity, distribution, tails, theory.", "Feature QA ceiling before models.",
         ["`tqg_client/features/qa.py` checklist.", "Output `artifacts/feature_qa.json`."], "Extend", "H"),
        ("2.2", "Four garbage defects", "Non-stationary, heavy tails, clumps, lookback artifacts.", "Automated feature failure detection.",
         ["ADF, kurtosis, clustering checks in QA.", "Link to transform ladder."], "Extend", "H"),
        ("2.3", "Pre-model transforms", "Six causal repair transforms.", "Standard transform library.",
         ["`tqg_client/features/transforms.py`.", "Document chain in spec."], "Extend", "H"),
        ("2.7", "Threshold scan null", "Full threshold scan vs shuffled target.", "Honest PSA thresholds.",
         ["PSA varies threshold; compare to null.", "`tqg_get_robustness_spec` PSA path."], "Native", "H"),
        ("2.9", "Ban raw price levels", "Use returns/ratios only.", "Cross-asset comparable features.",
         ["MCP rejects raw close as signal.", "Set `feature_basis: returns` in spec."], "Native", "H"),
        ("2.10", "Stationarity transform ladder", "Lightest transform passing ADF.", "Default feature hygiene.",
         ["Ladder in transforms module.", "Log chosen transform in artifacts."], "Extend", "H"),
        ("2.11", "ATR normalization", "Vol-scale returns for cross-asset.", "Core momentum primitive.",
         ["`atr_normalized_return()` helper.", "Used in T-02, T-05, XS-03."], "Native", "H"),
        ("2.12", "CMMA momentum primitive", "ATR-norm log price minus lagged MA.", "Better than raw MA cross.",
         ["Implement in features or strategy T-02.", "PSA on lookback k."], "Native", "H"),
        ("2.16", "Feature engineering >> model", "90–95% edge in features.", "Agents exhaust features before ML.",
         ["Skill checklist before model swaps."], "Native", "H"),
        ("2.17", "Filters ≠ predictors", "Filters summarize past; document lag.", "Realistic indicator expectations.",
         ["Lag audit per indicator in spec."], "Native", "H"),
        ("2.18", "Lag tax of MAs", "SMA(N) lag ≈ (N−1)/2.", "Horizon discipline.",
         ["Warn if horizon < 2× lag."], "Native", "H"),
        ("2.22", "High-pass / detrender", "MR on detrended series.", "MR-11 foundation.",
         ["`detrend()` helper in features."], "Native", "M"),
        ("2.27", "Cascaded lag budget", "Sum lags across stacks.", "Block structurally late signals.",
         ["Sum `lag_bars` in spec.", "Validation warning on excess lag."], "Native", "M"),
        ("2.28", "Median filter for volume", "Outlier-resistant volume features.", "T-11, MR-14 support.",
         ["Median volume before thresholds."], "Native", "M"),
    ]
    for row in indicators:
        add(row[0], row[1], row[2], row[3], row[4], row[5], row[6], sec2)

    add("2.36–2.74", "Full DSP catalog", "Hilbert, homomorphic filters, advanced DSP.", "R&D reference only.",
        ["Internal training doc.", "No baseline implementation."], fit="Future", priority="L", section=sec2)

    # §3 Robust Systems Lab
    sec3 = "§3 Robust Systems Lab"
    robust = [
        ("3.1", "Stationarity precondition", "ADF/KPSS on returns/features.", "Baseline regime diagnostics.",
         ["ADF in validation.", "`artifacts/regime_diagnostics.json`."], "Native", "H"),
        ("3.5", "OOS failure = stationarity failure", "Regime overlap before blaming overfit.", "Better OOS diagnostics.",
         ["IS/OOS overlap report (Tier 1)."], "Native", "H"),
        ("3.6", "Vol regime gating", "Stratify Sharpe by vol tercile.", "Honest attribution.",
         ["`metrics.json` `by_regime.vol_tercile`."], "Native", "H"),
        ("3.11", "Regime coverage matrix", "Vol × trend × correlation cells.", "Deployment gate.",
         ["`artifacts/regime_coverage.json`.", "Min positive cells to pass."], "Native", "H"),
        ("3.12", "Plateau > peak", "Pick plateau center in PSA.", "Core robustness doctrine.",
         ["PSA heatmaps; select center not peak."], "Native", "H"),
        ("3.16", "Degrees of freedom budget", "Count all DoF categories.", "Overfit prevention.",
         ["Auto-count from spec.", "10% rule gate."], "Native", "H"),
        ("3.18", "10% rule", "params/effective_trades < 10%.", "Exploratory vs deployable.",
         ["Fail deployable if violated."], "Native", "H"),
        ("3.21", "Monte Carlo flavors", "Bootstrap trades vs synthetic paths.", "Robustness option.",
         ["MC via `tqg_get_robustness_spec`."], "Native", "H"),
        ("3.22", "Permutation tests", "Block perm for autocorrelated features.", "Indicator significance.",
         ["Block length from autocorr."], "Native", "H"),
        ("3.23", "CSCV / PBO", "Combinatorial purged CV overfit prob.", "Gold-standard overfit control.",
         ["`tqg_client/robustness/cscv.py` (Tier 3)."], "Extend", "H"),
        ("3.24", "Walk-forward > single OOS", "Distribution of OOS steps.", "Landolfi validation.",
         ["Rolling WF in robustness bundle."], "Native", "H"),
        ("3.31", "Costs early", "Costs in baseline not afterthought.", "Realistic metrics.",
         ["Never primary pre-cost Sharpe.", "2× cost stress."], "Native", "H"),
        ("3.32", "32-item integrity checklist", "Deployment readiness.", "MCP validation alignment.",
         ["Map to `tqg_mcp_validate.py` rules."], "Native", "H"),
        ("3.37", "Collinear parameter sweeps", "Fix one MA, vary other.", "Honest dual-MA PSA.",
         ["PSA template for MA pairs."], "Native", "H"),
    ]
    for row in robust:
        add(row[0], row[1], row[2], row[3], row[4], row[5], row[6], sec3)

    # §4 Market Structure
    sec4 = "§4 Market Structure"
    market = [
        ("4.1", "Noise ≠ volatility", "Same vol, opposite tradeability.", "Use ER with ATR.",
         ["Compute ER alongside ATR."], "Native", "H"),
        ("4.2", "Efficiency ratio (ER)", "|net move|/total path; 0–1.", "Primary regime classifier.",
         ["`efficiency_ratio()` helper.", "Gates T-04, MR-03."], "Native", "H"),
        ("4.4", "High noise → MR", "Gate fades when ER high.", "MR only in chop.",
         ["`er_min` param default 0.5."], "Native", "H"),
        ("4.5", "Low noise → trend", "Breakouts when ER low.", "T-04 Donchian gate.",
         ["`er_max` param default 0.3."], "Native", "H"),
        ("4.12", "Strategy routing matrix", "ER→family; vol→size.", "Meta-strategy router.",
         ["`meta_router.py` research module."], "Extend", "H"),
        ("4.24", "Network momentum", "Neighbor asset momentum signal.", "T-13, XS-06, IA-01.",
         ["Lead-lag or correlation graph.", "Tier 2 network module."], "Extend", "H"),
        ("4.25+", "Session / calendar structure", "Hour-of-day and calendar effects.", "T-11, MR-07–09.",
         ["`hour_utc`, `day_of_week` features."], "Native", "M"),
    ]
    for row in market:
        add(row[0], row[1], row[2], row[3], row[4], row[5], row[6], sec4)

    # §5 Microstructure
    sec5 = "§5 Microstructure Alpha"
    micro = [
        ("5.13", "Order book imbalance (OBI)", "(bid−ask)/(bid+ask) from Coinglass.", "CG-08 strategy.",
         ["Coinglass orderbook join.", "Lag 1 bar."], "Extend", "H"),
        ("5.15", "Trade flow autocorrelation", "Taker buy/sell persistence.", "CG-07 strategy.",
         ["Coinglass taker flow features."], "Extend", "H"),
        ("5.22", "Crypto vol seasonality", "Spikes 14:00, 00:00 UTC.", "T-12 hourly tilt.",
         ["Hour-of-day dummies on 1h bars."], "Native", "H"),
        ("5.25", "24h rolling return artifact", "Fade ticker roll mirage.", "MR-13 strategy.",
         ["Detect 24h roll-off on 1h bars."], "Native", "M"),
        ("5.26", "Volume confirms stickiness", "High vol continuation; low vol revert.", "MR-14.",
         ["Volume percentile gate."], "Native", "H"),
        ("5.35", "Square-root market impact", "Slippage ∝ size^0.5.", "Non-linear costs.",
         ["`impact_model: sqrt` in run defaults."], "Extend", "M"),
    ]
    for row in micro:
        add(row[0], row[1], row[2], row[3], row[4], row[5], row[6], sec5)

    # §6 Portfolio
    sec6 = "§6 Portfolio Construction"
    port = [
        ("6.1", "Ranking > forecasting", "Cross-sectional sort beats point forecast.", "XS family foundation.",
         ["`workflow: cross_sectional` in spec."], "Native", "H"),
        ("6.3", "Vol-adjusted sizing", "1/σ weights; vol targeting.", "V-02 overlay.",
         ["`vol_target_annual` in spec.", "`portfolio.py` helper."], "Native", "H"),
        ("6.46", "Signal averaging", "Ensemble parameter variants.", "T-07 multi-horizon.",
         ["`ensemble_weights` in spec."], "Native", "H"),
        ("6.47", "Trend follower build", "7-stage trend program template.", "Crypto trend demos.",
         ["Checklist in strategy plans.", "Demo `btc_tsmom_vol_target`."], "Native", "H"),
        ("6.49", "Percentile-rank momentum + hysteresis", "Landolfi low-churn momentum.", "T-06 priority demo.",
         ["Rank vs own past; WF validation required."], "Native", "H"),
    ]
    for row in port:
        add(row[0], row[1], row[2], row[3], row[4], row[5], row[6], sec6)

    # §7 Cross-sectional
    sec7 = "§7 Cross-Sectional & Factors"
    xs = [
        ("7.1", "α + βλ decomposition", "Separate BTC beta from alpha.", "XS-09 evaluation.",
         ["Rolling OLS vs BTC in metrics."], "Native", "H"),
        ("7.2", "Portfolio sorts", "Decile L/S on 600+ perps.", "XS-01 showcase.",
         ["Universe from `binance_futures_ohlcv_1d.parquet`."], "Extend", "H"),
        ("7.5", "Factor zoo / mult. testing", "DSR, Bonferroni on scans.", "CS false-discovery control.",
         ["DSR with scan count."], "Native", "H"),
        ("7.16", "Target transform > features", "Rank/demean forward return as target.", "XS-10; Tier 1 backlog.",
         ["CS rank target for prediction."], "Native", "H"),
    ]
    for row in xs:
        add(row[0], row[1], row[2], row[3], row[4], row[5], row[6], sec7)

    # §8 Physics
    sec8 = "§8 Physics & Geometry"
    phys = [
        ("8.6", "Entropy as chop gauge", "Up/down entropy ≈1 chop.", "V-08 filter.",
         ["Binary entropy on return signs."], "Extend", "M"),
        ("8.9", "MS-GARCH regime switching", "2-state vol regime.", "V-03, Q-09 overlay.",
         ["Lite vol regime gate."], "Extend", "M"),
    ]
    for row in phys:
        add(row[0], row[1], row[2], row[3], row[4], row[5], row[6], sec8)

    # §9 Prediction markets (sizing ports)
    sec9 = "§9 Prediction Market Arbitrage (sizing ports)"
    pred = [
        ("9.15", "Kelly with negative-edge reject", "Kelly only when edge > 0.", "Sizing discipline.",
         ["`kelly_fraction()` capped at fractional Kelly."], "Native", "M"),
        ("9.40", "Longshot bias analog", "Fade extreme funding/OI.", "CG-02, CG-10.",
         ["Extreme percentile gates."], "Native", "M"),
    ]
    for row in pred:
        add(row[0], row[1], row[2], row[3], row[4], row[5], row[6], sec9)

    # §10 Quantocracy table
    sec10 = "§10 Quantocracy"
    qocr = [
        ("Q-DSR", "Deflated Sharpe Ratio", "Adjust Sharpe for trial count.", "Mandated false-discovery control.",
         ["Trial count from PSA.", "DSR in validation."], "Native", "H"),
        ("Q-Faber", "Meb Faber TAA", "10M SMA tactical allocation.", "TAA-01 demo.",
         ["Multi-asset via yfinance."], "Native", "H"),
        ("Q-Landolfi", "Percentile-rank momentum", "Low-churn momentum.", "T-06 strategy plan.",
         ["See strategy plan T-06."], "Native", "H"),
        ("Q-HMM", "HMM regime filter", "2-state overlay.", "Q-09 gates base strategy.",
         ["2-state HMM on returns/vol.", "Gate base strategy."], "Extend", "M"),
        ("Q-Costs", "Non-linear transaction costs", "Size-dependent slippage.", "Sqrt impact model.",
         ["`impact_model` in run.json."], "Native", "H"),
    ]
    for row in qocr:
        fit = row[5] if len(row) > 5 else "Native"
        pri = row[6] if len(row) > 6 else "M"
        add(row[0], row[1], row[2], row[3], row[4], fit, pri, sec10)

    # §11 Glassnode methodology
    sec11 = "§11 Glassnode Methodology"
    glass = [
        ("GN-Macro", "Macro layer", "DXY, real yields, equity correlation filters.", "GF-05, IA-09.",
         ["yfinance TLT, DXY, SPY joins."], "Extend", "H"),
        ("GN-Valuation", "On-chain valuation", "MVRV, NUPL, realized price.", "ON-01–ON-04.",
         ["Talos loader; lag 1 day."], "Extend", "H"),
        ("GN-ETF", "ETF / institutional", "Flows, premium/discount.", "CG-12–CG-14.",
         ["Coinglass ETF parquets."], "Extend", "H"),
        ("GN-Deriv", "Derivatives layer", "Funding, OI, liquidations.", "CG-01–CG-06.",
         ["Coinglass join on bar index."], "Extend", "H"),
        ("GN-Confirm", "Confirmation logic", "Multi-layer alignment before full size.", "GF-01, GF-10 scorecards.",
         ["Weighted score → position size.", "Per-layer pass/fail in report."], "Extend", "H"),
    ]
    for row in glass:
        add(row[0], row[1], row[2], row[3], row[4], row[5], row[6], sec11)

    return t


def strategy_plan(
    sid: str,
    name: str,
    logic: str,
    data: str,
    freq: str,
    cls: str,
    complexity: str,
    extra_steps: list[str] | None = None,
    warnings: str = "",
) -> Plan:
    value_map = {
        "trend": "Captures directional persistence; core demo family for lab.",
        "MR": "Exploits short-term overreaction; pairs well with ER gates.",
        "vol": "Manages risk and exploits vol premia/regimes.",
        "carry": "Crypto-native funding/basis edge.",
        "cross-section": "Showcases Binance universe scanning.",
        "event": "Calendar/microstructure timing effects.",
        "multi-factor": "Glassnode-style layered confirmation.",
    }
    value = value_map.get(cls, "Expand lab strategy catalog with validated rule set.")
    if warnings:
        value += f" Note: {warnings}"

    steps = [
        f"Data: {data} at `{freq}` frequency.",
        f"Set `strategy_type: {cls.upper()}` and complexity `{complexity}` in `strategy_spec.json`.",
        f"Load via `tqg_client.market_data.load_market_data()` (local `data/` first, yfinance fallback).",
        "Lag alt-data features 1 bar; align Coinglass/Talos on UTC date.",
        "Document units (funding 8h vs 1d, annualization 365 crypto / 252 equity) in spec.",
        "Include costs: crypto perp 4–10 bps RT minimum; stress 2× in robustness.",
    ]
    if extra_steps:
        steps.extend(extra_steps)
    steps.extend(COMMON_INTEGRATION[3:])  # backtest through package

    return Plan(sid, name, logic, value, steps, section=f"Class: {cls}")


def fix_talos_strategies(s: list[Plan]) -> list[Plan]:
    """Append Talos, intermarket, and Quantocracy strategies."""

    def S(*args, **kwargs):
        s.append(strategy_plan(*args, **kwargs))

    talos_val = [
        ("ON-01", "MVRV Z-score", "Long when CapMVRVZ < −1; exit > 2.", "CapMVRVZ, CapMVRVCur"),
        ("ON-02", "NUPL regime", "Long in capitulation (NUPL < 0.25); reduce > 0.75.", "NUPL"),
        ("ON-03", "Realized price support", "Long when price < CapRealUSD × 1.05.", "CapRealUSD, PriceUSD"),
        ("ON-04", "MVRV < 1 deep value", "Accumulate when MVRV < 1; trim > 3.", "CapMVRVCur"),
        ("ON-05", "NVT high fade", "Reduce when NVTAdj > 90d 90th pctile.", "NVTAdj, NVTAdj90"),
        ("ON-06", "SOPR capitulation", "Long when SOPR < 1 persists 7d.", "SOPR*"),
        ("ON-07", "STH cost basis reclaim", "Long breakout above STH cost proxy.", "realized cap variants"),
        ("ON-08", "LTH supply expansion", "Bearish when SplyLTH rising fast + price down.", "SplyLTH"),
        ("ON-09", "Accumulation trend score proxy", "Long when wallet balance metrics rise.", "AdrBal*, SplyAdrBal*"),
        ("ON-10", "Realized loss exhaustion", "Long when realized loss peaks then declines 30%.", "loss proxies"),
    ]
    for sid, name, logic, metrics in talos_val:
        extra = [f"Talos: `{metrics}`.", "Verify in `data/talos_data_catalog.json`.", "Lag 1 day."]
        if sid == "ON-01":
            extra.append("Priority demo #2.")
        S(sid, name, logic, f"OHLCV + Talos ({metrics})", "1d", "multi-factor", "S", extra)

    for sid, name, logic, metrics in [
        ("NA-01", "Active address momentum", "Long when AdrActCnt 30d ROC > 0.", "AdrActCnt"),
        ("NA-02", "Tx count breakout", "Long when TxCnt > 90d MA.", "TxCnt"),
        ("NA-03", "Transfer value surge", "Risk-off when TxTfrValAdjUSD spikes + price down.", "TxTfrValAdjUSD"),
        ("NA-04", "Fee spike fade", "MR after FeeMeanUSD > 95th pctile.", "FeeMeanUSD"),
        ("NA-05", "New address growth", "Long alts with AdrNewCnt/price divergence.", "AdrNewCnt"),
    ]:
        S(sid, name, logic, f"OHLCV + Talos ({metrics})", "1d", "multi-factor", "S",
          [f"Talos: `{metrics}`.", "Lag 1 day."])

    for sid, name, logic, data in [
        ("EF-01", "Exchange net outflow", "Long on 7d negative net flow.", "Talos FlowNet* / Coinglass balance"),
        ("EF-02", "Miner to exchange", "Bearish on miner outflow spikes.", "Talos mining flows"),
        ("EF-03", "ETF vs exchange flow combo", "Risk-on when ETF in + exchange out.", "Coinglass ETF + balance"),
        ("EF-04", "Stablecoin flow", "Risk-on on stablecoin exchange inflows.", "needs upload"),
    ]:
        warn = "Requires user upload." if "upload" in data else ""
        S(sid, name, logic, data, "1d", "multi-factor", "S", ["Lag 1 day."], warn)

    for sid, name, logic, metrics in [
        ("DV-01", "Funding rate trend", "Follow 30d cumulative funding sign.", "futures_cumulative_funding_rate_*"),
        ("DV-02", "OI / market cap ratio", "Fade high OI/MCAP extremes.", "open_interest_reported_* + cap"),
        ("DV-03", "Options OI put/call", "Risk-off when put OI > call OI by X%.", "open_interest_reported_option_*"),
        ("DV-04", "Vol term structure", "Long gamma proxy when short vol < long vol.", "VtyDayRet30d vs 180d"),
        ("DV-05", "Perp vs spot volume", "Leverage excess when perp/spot vol ratio high.", "volume_reported_*"),
    ]:
        S(sid, name, logic, f"OHLCV + Talos/Coinglass ({metrics})", "1d", "carry", "S",
          [f"Metrics: `{metrics}`.", "Lag 1 day."])

    gf = [
        ("GF-01", "Deep value accumulator", "MVRV<1 AND exchange balance ↓ 14d AND ETF flows ≥ 0.", "valuation+flows"),
        ("GF-02", "Bear market late-stage", "LTH loss 30d SMA falling AND ETF outflow improving.", "LTH+ETF"),
        ("GF-03", "Recovery confirmation", "Price > realized AND neutral funding AND taker buy > 0.52.", "price+deriv"),
        ("GF-04", "Risk-off de-risk", "Vol ↑ + ETF outflows + rising exchange balance.", "vol+flows"),
        ("GF-05", "Macro liquidity BTC", "Long BTC when DXY < 200d MA AND BTC > 200d MA.", "DXY+BTC"),
        ("GF-06", "Dollar inverse sleeve", "Scale BTC by rolling −corr(BTC,DXY).", "BTC+DXY"),
        ("GF-07", "Max pain pin", "Mean-revert to max OI strike.", "options strikes"),
        ("GF-08", "Vol compression breakout", "Breakout when 30d vol at 1y low.", "ATR percentile"),
        ("GF-09", "STH resistance rejection", "Fade at STH cost; stop on reclaim.", "cost basis"),
        ("GF-10", "Full Week 28 playbook", "Weighted scorecard across macro/on-chain/ETF/deriv.", "all layers"),
    ]
    for sid, name, logic, layers in gf:
        extra = [f"Layers: {layers}.", "Weighted score → position size.", "Per-layer pass/fail in report."]
        warn = ""
        if sid == "GF-02":
            extra.append("Priority demo #4.")
        if sid in ("GF-05", "GF-07"):
            warn = "GF-05 needs yfinance DXY; GF-07 needs options strike upload."
        S(sid, name, logic, f"Multi-source ({layers})", "1d", "multi-factor", "M", extra, warn)

    for sid, name, logic, symbols in [
        ("IA-01", "BTC leads ETH", "Trade ETH in direction of BTC 1d return.", "BTC, ETH"),
        ("IA-02", "SPY leads BTCUSDT", "Risk-on filter for crypto longs.", "SPY, BTC"),
        ("IA-03", "Gold/BTC ratio MR", "Fade PAXGUSDT/BTC ratio z-score.", "PAXGUSDT, BTC"),
        ("IA-04", "Copper/gold ratio", "Risk-on when copper/gold rising.", "HG, GLD"),
        ("IA-05", "Oil shock risk-off", "Reduce BTC when USO 5d return > 8%.", "USO, BTC"),
        ("IA-06", "Rates proxy trend", "Gate NVDAUSDT with TLT trend.", "TLT, NVDAUSDT"),
        ("IA-07", "Equity perp basket", "Long strongest SPY/QQQ/NVDA 20d mom.", "equity perps"),
        ("IA-08", "ETH/BTC rotation", "Hold higher 20d risk-adj momentum.", "ETH, BTC"),
        ("IA-09", "DXY risk filter", "Scale crypto longs by DXY trend.", "DXY + universe"),
        ("IA-10", "Intermarket divergence", "Trade lagging leg after leader move.", "2-leg pair"),
    ]:
        warn = "IA-04 needs yfinance HG, GLD." if sid == "IA-04" else ("yfinance DXY." if sid == "IA-09" else "")
        S(sid, name, logic, f"Multi-symbol OHLCV ({symbols})", "1d", "trend", "M", [f"Symbols: {symbols}."], warn)

    for sid, name, logic, data, warn in [
        ("Q-01", "Accrual anomaly", "Short high accruals, long low.", "fundamentals", "Needs fundamentals upload."),
        ("Q-02", "PEAD", "Drift with earnings surprise.", "earnings", "Needs earnings data."),
        ("Q-03", "Dividend premium", "Long dividend payers.", "fundamentals", "Needs fundamentals."),
        ("Q-04", "Short interest / retail options", "Fade crowded retail.", "options SI", "Needs upload."),
        ("Q-05", "Crack spread / refiner lag", "Long refiners vs crack.", "futures+equities", "Needs crack spread data."),
        ("Q-06", "VIX risk premium", "Short vol ETP when VIX elevated vs realized.", "^VIX, VXX", "yfinance ^VIX."),
        ("Q-07", "0DTE intraday vol", "Intraday vol breakout on SPY.", "intraday SPY", "Needs intraday upload."),
        ("Q-08", "Recursive LS prediction", "Online regression forecast per bar.", "any OHLCV", ""),
        ("Q-09", "HMM regime overlay", "2-state HMM gates base strategy.", "OHLCV", ""),
        ("Q-10", "Margin debt risk-off", "Reduce equity when margin debt/GDP extreme.", "macro", "Needs macro upload."),
    ]:
        S(sid, name, logic, data, "1d", "vol" if "VIX" in name else "MR", "S", [], warn)

    return s


def _build_all_strategies() -> list[Plan]:
    """Full strategy list."""
    s: list[Plan] = []

    def S(*a, **kw):
        s.append(strategy_plan(*a, **kw))

    # Trend T-01..T-15
    trend_data = [
        ("T-01", "Dual moving-average crossover", "Long when fast MA > slow MA.", "OHLCV", "1d", "trend", "S", ["Params 20/100 or 50/200.", "PSA: fix slow, sweep fast."]),
        ("T-02", "CMMA trend", "Sign of ATR-normalized log-price minus lagged MA.", "OHLCV", "1d", "trend", "S", ["CMMA primitive (2.12).", "k=20–60."]),
        ("T-03", "Donchian breakout", "Long N-day high; exit N/2 low.", "OHLCV", "1d", "trend", "S", ["N=20,55,100."]),
        ("T-04", "Donchian + ER gate", "T-03 when ER < 0.3.", "OHLCV", "1d", "trend", "S", ["ER lookback 20."]),
        ("T-05", "Time-series momentum", "Long 12-1m return > 0; vol-scaled.", "OHLCV", "1d", "trend", "S", ["Demo #1 with V-02."]),
        ("T-06", "Percentile-rank momentum + hysteresis", "Rank vs own past; band entry/exit.", "OHLCV", "1d", "trend", "S", ["Walk-forward required.", "Demo #7."]),
        ("T-07", "Multi-horizon momentum ensemble", "Average 5/10/20/60d mom signals.", "OHLCV", "1d", "trend", "S", []),
        ("T-08", "Vol-filtered trend", "TSMOM when vol < 90d median.", "OHLCV", "1d", "trend", "S", []),
        ("T-09", "52-week high breakout", "Long within 0–5% of 252d high.", "OHLCV", "1d", "trend", "S", []),
        ("T-10", "QQQ/BTC Donchian rotation", "Hold stronger breakout; else cash.", "QQQUSDT, BTCUSDT", "1d", "trend", "M", ["Demo #8."]),
        ("T-11", "Session volume momentum", "13:30–15:00 UTC volume + 30m return sign.", "OHLCV", "1h", "trend", "S", []),
        ("T-12", "Hour-of-day vol premium tilt", "Long bias 00:00 UTC; reduce 02:00–06:00.", "OHLCV", "1h", "trend", "S", []),
        ("T-13", "Network momentum (single hub)", "BTC 20d mom → ETH next day.", "BTC+ETH", "1d", "trend", "M", []),
        ("T-14", "Trend in FX majors", "MA cross on EURUSD, GBPUSD.", "FX OHLCV", "1d", "trend", "S", [], "yfinance FX."),
        ("T-15", "Commodity dual momentum", "Absolute + relative mom on GLD, USO.", "Commodity OHLCV", "1d", "trend", "M", [], "yfinance."),
    ]
    for row in trend_data:
        warn = row[8] if len(row) > 8 else ""
        S(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], warn)

    mr_data = [
        ("MR-01", "Bollinger fade", "Fade band touches.", "OHLCV", "1d", "MR", "S", ["20, 2σ."]),
        ("MR-02", "RSI oversold bounce", "Long RSI<30; exit >50.", "OHLCV", "1d", "MR", "S", []),
        ("MR-03", "RSI + ER gate", "MR-02 when ER>0.5.", "OHLCV", "1d", "MR", "S", ["Use with MR-15."]),
        ("MR-04", "Z-score price vs MA", "Long z<-2 vs 20d MA.", "OHLCV", "1d", "MR", "S", []),
        ("MR-05", "Intraday gap fade", "Fade gap >1–3%.", "OHLCV", "1h", "MR", "S", []),
        ("MR-06", "Short-term reversal", "Long after -2σ daily return.", "OHLCV", "1d", "MR", "S", []),
        ("MR-07", "Turnaround Tuesday", "Long Mon close if Fri red.", "OHLCV", "1d", "event", "S", ["Demo #9."]),
        ("MR-08", "Turn-of-month", "Long last day + first 3 days.", "OHLCV", "1d", "event", "S", []),
        ("MR-09", "Holiday effect", "Pre/post holiday drift.", "OHLCV", "1d", "event", "S", []),
        ("MR-10", "Pairs ratio MR", "BTC/ETH spread z-score.", "2× OHLCV", "1d", "MR", "M", []),
        ("MR-11", "RSI on detrended", "HPF detrend + RSI(2).", "OHLCV", "1d", "MR", "S", []),
        ("MR-12", "Overnight intraday reversal", "Fade overnight move first hour.", "OHLCV", "1h", "MR", "S", []),
        ("MR-13", "24h ticker artifact fade", "Fade before 24h roll-off.", "OHLCV", "1h", "MR", "S", []),
        ("MR-14", "Low-volume fade", "Fade >1σ move on low volume.", "OHLCV", "1d", "MR", "S", []),
        ("MR-15", "QQQ mean reversion", "RSI(4) MR with 200d SMA filter.", "QQQ", "1d", "MR", "S", ["Ref: `qqq_rsi2_mr`.", "Demo #5."]),
    ]
    for row in mr_data:
        S(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])

    vol_data = [
        ("V-01", "Realized vol breakout", "Long vol when 20d crosses above 60d.", "OHLCV", "1d", "vol", "S", []),
        ("V-02", "Vol targeting overlay", "Scale to 15% ann vol target.", "OHLCV", "1d", "vol", "S", ["Overlay on T-05."]),
        ("V-03", "Vol regime switch", "Trend in low vol tercile; cash in high.", "OHLCV", "1d", "vol", "S", []),
        ("V-04", "SAR seasonal vol forecast", "AR+24h+168h vol sizing.", "OHLCV", "1h", "vol", "S", []),
        ("V-05", "VIX term structure", "Short vol when VIX < MA, contango.", "^VIX", "1d", "vol", "S", [], "yfinance ^VIX."),
        ("V-06", "Intraday straddle proxy", "Long vol after DVOL proxy spike.", "OHLCV", "1d", "vol", "S", []),
        ("V-07", "GARCH vol gate", "Trade when GARCH forecast < realized.", "OHLCV", "1d", "vol", "S", []),
        ("V-08", "Entropy chop filter", "MR high entropy; trend low.", "OHLCV", "1d", "vol", "S", []),
    ]
    for row in vol_data:
        warn = row[8] if len(row) > 8 else ""
        S(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], warn)

    taa_data = [
        ("TAA-01", "Faber 10-month SMA", "Long above 10M SMA else cash.", "Multi OHLCV", "1d", "trend", "M", []),
        ("TAA-02", "Dual momentum TAA", "Faber + pick stronger asset.", "Multi OHLCV", "1d", "trend", "M", []),
        ("TAA-03", "Distressed TAA rotation", "Rotate to worst recent performer.", "Strategy returns", "1d", "trend", "M", []),
        ("TAA-04", "Risk parity lite", "1/σ equal risk weights.", "Multi OHLCV", "1d", "vol", "M", []),
        ("TAA-05", "Bond filter for equities", "Long SPY if yield trend down.", "TLT+SPY", "1d", "trend", "M", []),
        ("TAA-06", "Gold/dollar/rates triangle", "Long gold when yields fall, DXY weak.", "GLD,DXY", "1d", "trend", "M", [], "yfinance."),
        ("TAA-07", "Crypto vs equity rotation", "BTC risk-on; cash risk-off.", "SPY,BTC", "1d", "trend", "M", []),
        ("TAA-08", "Crisis convexity sleeve", "Long vol when skew extreme.", "Vol proxy", "1d", "vol", "M", []),
    ]
    for row in taa_data:
        warn = row[8] if len(row) > 8 else ""
        S(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], warn)

    xs_data = [
        ("XS-01", "Cross-sectional momentum", "L/S top/bottom 20d return deciles.", "Binance universe", "1d", "cross-section", "X", ["Demo #6."]),
        ("XS-02", "RSI rank L/S", "CS z-score RSI extremes.", "Universe", "1d", "cross-section", "X", []),
        ("XS-03", "Vol-scaled momentum", "Rank return/vol.", "Universe", "1d", "cross-section", "X", []),
        ("XS-04", "Short-term reversal CS", "Long worst 5d decile.", "Universe", "1d", "cross-section", "X", []),
        ("XS-05", "Price-path convexity", "Rank low convexity.", "Universe", "1d", "cross-section", "X", []),
        ("XS-06", "Network momentum CS", "Neighbor-weighted momentum.", "Universe", "1d", "cross-section", "X", []),
        ("XS-07", "Dollar volume filter", "XS-01 top 50 liquid.", "Universe", "1d", "cross-section", "X", []),
        ("XS-08", "Funding carry rank", "L/S by 7d mean funding.", "Universe+funding", "1d", "carry", "X", []),
        ("XS-09", "Beta-neutral momentum", "Long mom; hedge BTC beta.", "Universe+BTC", "1d", "cross-section", "X", []),
        ("XS-10", "Demeaned return target", "Predict CS rank next week.", "Universe", "1d", "cross-section", "X", []),
    ]
    for row in xs_data:
        S(row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7])

    cg_data = [
        ("CG-01", "Funding rate carry", "Long when funding < -X.", "funding", "carry"),
        ("CG-02", "Funding extreme fade", "Fade crowded funding.", "funding", "MR"),
        ("CG-03", "OI expansion breakout", "Price up + OI up.", "OI", "trend"),
        ("CG-04", "OI divergence fade", "Price high, OI falling.", "OI+price", "MR"),
        ("CG-05", "Liquidation cascade fade", "Long after liq > 95th pctile.", "liquidations", "MR"),
        ("CG-06", "Short squeeze setup", "Neg funding + price up + short liqs.", "funding+liq", "trend"),
        ("CG-07", "Taker buy imbalance", "taker_buy ratio > 0.55.", "taker flow", "trend"),
        ("CG-08", "Orderbook imbalance", "(bids-asks)/(bids+asks).", "orderbook", "trend"),
        ("CG-09", "Whale index gate", "Trend when whale_index low.", "whale_index", "trend"),
        ("CG-10", "Global L/S fade", "Fade extreme positioning.", "positioning", "MR"),
        ("CG-11", "Net position momentum", "Follow net_long_change.", "net_position", "trend"),
        ("CG-12", "ETF flow momentum", "Long on 5d positive ETF flow.", "etf_flows", "trend"),
        ("CG-13", "ETF flow divergence", "Price down + inflows.", "etf+price", "multi-factor"),
        ("CG-14", "ETF premium discount", "Buy extreme discount.", "etf_premium", "MR"),
        ("CG-15", "Exchange balance drain", "Bullish on negative 30d Δ balance.", "exchange_balance", "multi-factor"),
        ("CG-16", "Puell multiple bottom", "Long puell < 0.5.", "puell", "multi-factor"),
        ("CG-17", "Basis carry", "Long spot/short perp on basis.", "basis", "carry"),
        ("CG-18", "Multi-factor BTC bottoming", "Composite capitulation score.", "composite", "multi-factor"),
        ("CG-19", "Funding-weighted CS mom", "XS-01 ex high funding.", "funding+universe", "cross-section"),
        ("CG-20", "Liq + funding extreme", "Both liq spike and funding extreme.", "liq+funding", "MR"),
    ]
    demos = {"CG-01": "Demo #3.", "CG-05": "Demo #10.", "CG-18": "Demo #4."}
    for sid, name, logic, field, cls in cg_data:
        extra = [f"Coinglass `{field}` from `data/coinglass/`.", "Lag 1 bar."]
        if sid in demos:
            extra.append(demos[sid])
        S(sid, name, logic, f"OHLCV+Coinglass ({field})", "1d/1h", cls, "S", extra)

    fix_talos_strategies(s)
    return s


def write_techniques_md(path: Path) -> int:
    plans = techniques()
    header = """# Aligrithm Technique Implementation Plans

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

"""
    body = "\n".join(fmt_plan(p) for p in plans)
    footer = """
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
"""
    path.write_text(header + body + footer, encoding="utf-8")
    return len(plans)


def write_strategies_md(path: Path) -> int:
    plans = _build_all_strategies()
    header = """# Strategy Implementation Plans

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

"""
    # Group by ID prefix
    sections: dict[str, list[Plan]] = {}
    for p in plans:
        prefix = p.id.split("-")[0]
        sections.setdefault(prefix, []).append(p)

    part_names = {
        "T": "Part A1 — Trend",
        "MR": "Part A2 — Mean Reversion",
        "V": "Part A3 — Volatility",
        "TAA": "Part A4 — Tactical Asset Allocation",
        "XS": "Part A5 — Cross-Sectional",
        "CG": "Part B — Coinglass",
        "ON": "Part C1 — On-chain Valuation",
        "NA": "Part C2 — Network Activity",
        "EF": "Part C3 — Exchange Flows",
        "DV": "Part C4 — Derivatives (Talos)",
        "GF": "Part C5 — Glassnode Multi-factor",
        "IA": "Part D — Intermarket",
        "Q": "Part E — Quantocracy / yfinance",
    }

    body_parts = []
    order = ["T", "MR", "V", "TAA", "XS", "CG", "ON", "NA", "EF", "DV", "GF", "IA", "Q"]
    for key in order:
        if key in sections:
            body_parts.append(f"## {part_names[key]}\n\n")
            body_parts.append("\n".join(fmt_plan(p) for p in sections[key]))

    footer = """
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
"""
    path.write_text(header + "".join(body_parts) + footer, encoding="utf-8")
    return len(plans)


def main() -> None:
    PLANS.mkdir(parents=True, exist_ok=True)
    t_path = PLANS / "aligrithm-technique-implementation-plans.md"
    s_path = PLANS / "strategy-implementation-plans.md"
    n_t = write_techniques_md(t_path)
    n_s = write_strategies_md(s_path)
    print(f"Wrote {n_t} technique plans -> {t_path}")
    print(f"Wrote {n_s} strategy plans -> {s_path}")


if __name__ == "__main__":
    main()
