# Autonomous research log — November 2026

Athens time zone is UTC+2. Machine timestamps below that come from the clock are labeled. This file is the program record. Backtests live under `runs/` (gitignored). Nothing here is a live-trading instruction.

## What this session will not do

Cursor does not expose a monthly usage meter to this agent. The request to keep going until 10% of monthly usage cannot be checked from here. The stopping rule used instead is a pre-committed research design: four hypotheses, no parameter search, no second look at a failure, and at most one robustness test on a book that already clears the screen below.

Out-of-sample cut-off is the lab default, `2025-01-01`. That window runs only through the latest cached print (about autumn 2026), so OOS Sharpe is a short sign check, not a career statistic.

## What the lab already settled (so it is not repeated)

Lesson briefs and `runs/_lab/index.json` were read before any new baseline.

- Single-asset 12-month SPY trend, long or cash (`si230_tsmom_spy`, `si268_tsmom_spy_b`): positive IS and OOS Sharpe, tagged `no_edge` because it did not beat buy-and-hold. Not re-run, and the lookback is not nudged.
- Multi-asset 12-month sign, inverse-vol, long/short (`si68_anatomy_trend`): IS Sharpe 0.48, OOS 0.70, tagged `no_edge` against the panel buy-and-hold. A 12-1 or 40% vol-target neighbor would be a tweak of a killed trend book. Not run.
- Faber 10-month SMA on SPY (`si31_faber_spy`, `catalog_taa_01`) is already marked promising and is a human hold. The multi-ETF Faber book (`si31_faber_multiasset_book`) exists. No new moving-average neighbor, including a gold-only copy.
- Crypto time-series momentum (`crypto_tsmom_zakamulin`): IS Sharpe about 1.02, OOS about −0.50. Not repeated on perps.
- Crypto funding and basis carry failed or died out of sample in the catalog. That is a different instrument from FX forward carry.
- Turn-of-month, Turnaround Tuesday, and holiday overlays on SPY are already weak or negative. They are not revived.
- Fixed-income dual momentum (`dmfi_antonacci_hyg_lqd_ief_bil`) is the credit module, not Global Equity Momentum. It is a cousin, not a template to retune.

SPY lesson-brief blockers are other hypotheses (intraday opening-range, turn-of-month, a Faber hold). They are not the fingerprints below. Those fingerprints were not treated as a ban on every future SPY test.

## Pre-committed hypotheses

Costs on every book: 4.5 bps fee plus 5 bps slippage on each unit of weight change (19 bps round-trip), matching the lab default. Signals use only information available before the return they earn. No grid is scored inside these baselines. Program-level trial count is 4 even when the harness family N stays 1 because symbols differ.

Screen, applied after the runs and not used to change rules:

1. In-sample Sharpe above the hurdle named on that hypothesis.
2. Out-of-sample Sharpe above 0 (same sign as a positive in-sample result).
3. In-sample Lo 95% interval lower bound above 0 when `sharpe_diagnostics` exists.
4. The path is not one decade. Decade Sharpe table is evidence, not a new trial.
5. A pass is a candidate for one robustness test. It is not a forecast, and deflated Sharpe is not an expected live Sharpe.

### H1 — G10 symmetric FX carry

- Mechanism: Lustig, Roussanov, and Verdelhan (2011). High interest-rate currencies pay a premium that shows up as a common factor. This is not crypto funding.
- Data: `data/fx/g10_carry_monthly.parquet` (Verdelhan forwards through the MIT panel, then FRED 3-month rates and Dukascopy spot).
- Rule: each month, rank G10 currencies including USD (forward discount 0) on the **previous** month's forward discount. Long the expensive half, short the cheap half, equal weight, gross 1. If the count is odd, drop the median name. Earn this month's carry excess.
- The repo helper `portfolio_excess_returns` multiplies the same month's discount by the same month's excess return. That timing is not used. The paper sorts at t and earns the next month.
- Bekaert and Panayotov "good carry" (drop AUD, NOK, JPY) is not tested. That exclusion was chosen after seeing which names hurt on this history.
- Hurdle: in-sample Sharpe > 0.30, because published G10 carry Sharpes are usually well above that. Annualization 12.
- Run id: `g10_fx_symmetric_carry`.

### H2 — Global Equity Momentum

- Mechanism: Antonacci, "Risk Premia Harvesting Through Dual Momentum" (2012) and *Dual Momentum Investing* (2014). Absolute momentum leaves equities when US stocks lose to cash. Relative momentum picks the stronger equity market.
- Assets: SPY, EFA (developed ex-US; the book uses ACWI ex-US, so EFA is a stated proxy), AGG as the defensive bond, and a Treasury-bill hurdle from local `TB3MS` compounded daily. BIL is not the hurdle, because it starts in 2007.
- Rule: at each month-end, 12-month total return. If SPY beat bills, hold whichever of SPY and EFA won. Otherwise hold AGG. The weight is applied from the next session. One switching rule, so k = 1, not three averaged sleeves.
- Context benchmark, not a second trial: 60% SPY / 40% AGG, same costs, same dates.
- Hurdle: in-sample Sharpe above that 60/40, in-sample max drawdown at least 5 percentage points shallower than SPY buy-and-hold, and out-of-sample Sharpe > 0.
- Run id: `gem_spy_efa_agg`.

### H3 — Halloween indicator

- Mechanism: Bouman and Jacobsen (AER 2002). November–April equity returns exceed May–October. Later work (Dichtl and Drobetz) finds the trading rule does not reliably beat buy-and-hold. This run is a falsification, not a search over months.
- Rule: long SPY when the session's calendar month is November, December, January, February, March, or April; otherwise flat. Weight shifted one session.
- Hurdle: in-sample Sharpe above SPY buy-and-hold, and out-of-sample Sharpe > 0. Failing to beat buy-and-hold is a kill even if the strategy Sharpe is positive.
- Run id: `halloween_spy`.

### H4 — Volatility-managed 60/40

- Mechanism: Moreira and Muir (Journal of Finance, 2017). Scale a payoff by the inverse of recent variance. The lab's BTC vol-target (`catalog_v_02`) is a different book and is not a license to search scales.
- Rule: base weights 60% SPY and 40% TLT. Daily variance is the prior 21 sessions (`.rolling(21).var().shift(1)`). Target daily variance is `(0.10^2) / 252`. Scale = target / variance, clipped to [0, 1.5]. One spec. The clip and the 10% target are declared, not fit.
- Hurdle: in-sample Sharpe above unscaled 60/40 on the same dates, out-of-sample Sharpe > 0, and in-sample max drawdown no deeper than unscaled 60/40.
- Run id: `vm_spy_tlt_6040`.

## Harness note

`runpy.run_path` executes the strategy in a new module dictionary and returns that dictionary. `tqg_run_backtest.py` was discarding the return, so `pf` never reached the selection log and deflated Sharpe stayed missing. `tqg_client/execution.py` now keeps the returned globals. The first pass of H1–H3 was replayed after that fix. Fingerprints were unchanged, so those replays did not increment N.

The random-entry null is not used below. Each book is marked to market as a buy-and-hold of its own net-asset-value series, and the null Sharpe then has no dispersion (5th percentile equals 95th percentile). PBO is not computable: there is no `psa_returns_matrix.csv`.

Run-level deflated Sharpe uses that run's N, which is 1. It does not know about the other three hypotheses. Recomputing H4's deflated Sharpe at program N = 4 still gives about 0.9996, because the in-sample Sharpe is high and the sample is long. That number is still not an expected live Sharpe.

## Results

Screen outcomes use the hurdles written above. Evidence-report conclusions are quoted and are not a substitute for those hurdles.

### H1 — G10 symmetric carry — `no_edge`

Run `g10_fx_symmetric_carry`. N = 1, family N = 1, k = 1. Annualization 12. In-sample months 493. Out-of-sample months 20.

| | Sharpe | CAGR | Max DD |
|--|--|--|--|
| In sample, net | −0.094 | −0.12% | −12.0% |
| Out of sample, net | 1.177 | 1.9% | −1.8% |
| In sample, before costs | 0.016 | | |

Lo SE 0.156. 95% interval [−0.40, 0.21]. Deflated Sharpe 0.27. `dsr_status` ok. The only selection warning is that PBO is not computable. HAC t on the mean net return −0.59, two-sided p 0.55. Block-bootstrap 95% interval for the annualized mean includes zero. Evidence conclusions: nonzero historical return inconclusive, generalization supported, tradability not supported. Break-even round-trip cost is negative because the mean is negative.

Decade in-sample Sharpes: 1980s −0.28, 1990s −0.41, 2000s −0.13, 2010s −0.06, 2020s 0.37. The premium is not a multi-decade fact on this panel.

A constant 50/50 long AUD / short JPY book, computed as a panel check and not selected, has in-sample Sharpe 0.16. The stitched Verdelhan-plus-Dukascopy panel does not carry the textbook premium even in that simple pair. Bekaert-Panayotov "good carry" was not run. Dropping currencies until the Sharpe appears would be the mistake this program was built to avoid.

### H2 — Global Equity Momentum — `no_edge`

Run `gem_spy_efa_agg`. N = 1, family N = 1, k = 1. Linked as a cousin of `dmfi_antonacci_hyg_lqd_ief_bil` and `si230_tsmom_spy`. Different symbols, so the harness did not add their trials to family N. Program N still counts this test.

| | Sharpe | CAGR | Max DD | Days |
|--|--|--|--|--|
| GEM in sample | 0.612 | 8.4% | −33.7% | 5350 |
| GEM out of sample | 0.839 | 14.6% | −18.8% | 423 |
| 60/40 in sample | 0.729 | 7.9% | −34.9% | 5350 |
| SPY in sample | 0.639 | 10.7% | −55.2% | 5350 |
| SPY out of sample | 1.033 | 17.7% | −18.8% | 423 |
| 60/40 out of sample | 1.107 | 12.1% | −11.3% | 423 |

Lo SE 0.220. 95% interval [0.18, 1.04]. Deflated Sharpe 0.997 at N = 1. HAC t 3.19, p 0.0014. Evidence conclusions: nonzero return supported, generalization supported, tradability supported. In-sample one-way turnover about 1.30. Break-even round-trip about 354 bps, against 19 bps already charged.

The drawdown hurdle against SPY is met (−33.7% versus −55.2%). The Sharpe hurdle against 60/40 is not. Out of sample, GEM also trails both SPY and 60/40. Decade in-sample Sharpes (0.86, 0.54, 0.52) are the same sign, so this is not a one-decade path. It is a timing rule that did not beat the static mix it is supposed to improve. The 12-month window was not shortened, and EFA was not swapped for VEU.

### H3 — Halloween — `no_edge`

Run `halloween_spy`. One symbol, SPY. N = 1, family N = 1, k = 1.

| | Sharpe | CAGR | Max DD |
|--|--|--|--|
| Halloween in sample | 0.577 | 7.0% | −33.9% |
| Halloween out of sample | 0.116 | 0.6% | −18.8% |
| SPY in sample | 0.628 | 10.5% | −55.2% |
| SPY out of sample | 1.033 | 17.7% | −18.8% |

Lo SE 0.179. 95% interval [0.23, 0.93]. Deflated Sharpe 0.999 at N = 1. HAC t 3.77, p 0.00016. Evidence conclusions: nonzero return supported, generalization inconclusive, tradability supported. Break-even round-trip about 372 bps. Turnover is about one round trip a year, which is why tradability looks fine.

The pre-committed hurdle was beating buy-and-hold. It does not, in sample or out of sample. A positive Sharpe with a shallower drawdown is still a miss under that rule. The months were not edited. This lines up with the later result that the calendar rule does not clear a buy-and-hold benchmark.

### H4 — Vol-managed 60/40 — `needs_robustness`

Run `vm_spy_tlt_6040`. N = 1, family N = 1, k = 2 (60% SPY and 40% TLT). Sample is the overlap of the yfinance daily caches, about 2004 through September 2026. `load_market_data("TLT")` returns a 2020 Alpaca file stamped at 04:00 UTC and joins to nothing against SPY; the strategy reads `data/equities/yfinance/TLT_1d.parquet` and `SPY_1d.parquet` instead. That choice was made because the join was empty, before any Sharpe was known.

| | Sharpe | CAGR | Max DD |
|--|--|--|--|
| Managed in sample | 0.980 | 9.6% | −19.5% |
| Managed out of sample | 0.594 | 5.9% | −8.9% |
| Unscaled 60/40 in sample | 0.790 | 8.3% | −30.1% |
| Unscaled 60/40 out of sample | 0.946 | 11.1% | −11.4% |

Lo SE 0.222. 95% interval [0.55, 1.41]. MinBTL for a Sharpe of 1 is reported as 0 years because the in-sample point estimate is already around 1. Deflated Sharpe 0.999995 at N = 1, and about 0.9996 if the four program hypotheses are charged as N = 4. HAC t 4.74, p about 2e-6. Bootstrap 95% interval for the annualized mean is about [5.6%, 13.7%]. Evidence conclusions: nonzero return supported, generalization supported, tradability supported. Mean in-sample scale 1.18, cap 1.5. In-sample one-way turnover about 3.91. Break-even round-trip about 124 bps, against 19 bps already charged.

The written screen passes: higher in-sample Sharpe than unscaled 60/40, shallower in-sample drawdown, out-of-sample Sharpe above 0, and a Lo interval that sits above 0.

The out-of-sample comparison to the static mix goes the other way (0.59 versus 0.95). That was not a kill condition in the screen. It is the reason this is not a finished rule.

One robustness test, not a new canonical book: double fee and slippage (9 bps + 10 bps). Managed in-sample Sharpe 0.905 versus unscaled 0.777 at the same 2x costs. Managed out-of-sample Sharpe 0.491 versus unscaled 0.939. The in-sample advantage survives the thicker cost. The out-of-sample shortfall versus the static mix does not go away. N stayed 1. PBO is still not computable. No variance window, cap, or target volatility was tried besides the one declared above.

## What was learned

Liquid equity timing that the lab had not already killed still lost to the obvious static alternative when the hurdle was written first. GEM reduces the SPY drawdown and still loses to 60/40. Halloween reduces the drawdown and still loses to buy-and-hold. Both have high deflated Sharpes at N = 1 because a long equity sample with a Sharpe near 0.6 beats a sharp null. That is not evidence they beat the benchmark that matters.

The G10 panel used here does not reproduce carry. The right response was to stop, not to drop AUD, NOK, and JPY.

The vol-managed 60/40 is the only book that cleared its own screen, including a 2x cost check. It is a candidate for a later in-sample parameter plateau and a PBO, on a new turn. It is not a license to change the 21-day window or the 1.5 cap after seeing that out-of-sample 2025–2026 preferred the static mix.

## What this session did not spend

No further hypotheses were opened after these four. A fifth rule chosen because the first three failed would have been the search the pre-commitment was there to block. Usage percent of a Cursor plan is not visible from this agent, so the program stopped on the design instead of on a billing meter.

