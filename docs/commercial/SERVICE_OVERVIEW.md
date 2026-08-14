# TheQuantGPT Cursor Lab — Service Overview

**AI-assisted systematic research on your own server — with a maintained workflow layer, not another chatbot.**

---

## Who this is for

TheQuantGPT Cursor Lab is built for **small systematic research teams** that want to move faster without sacrificing research discipline.

| Persona | Typical situation |
|---------|-------------------|
| **Head of Research / PM** | Strategy ideas pile up in notebooks and one-off AI chats; nothing is reproducible or audit-ready. |
| **Quant researcher** | Has local OHLCV or feature data; wants to iterate on rule-based ideas with proper OOS splits and robustness. |
| **Crypto / multi-asset desk (2–10 people)** | Needs a shared research process — baseline → OOS → PSA — without building internal tooling from scratch. |

**Good fit:** teams doing **research and backtesting only**, comfortable with a cloud server and Cursor, and willing to prompt agents rather than hand-write every script.

**Not a fit (today):** live trading, execution infrastructure, guaranteed alpha, or fully custom non-OHLCV data engineering beyond the documented schema.

---

## The problem

AI makes backtests fast. It does **not** make them trustworthy by default.

| What teams see today | What goes wrong |
|----------------------|-----------------|
| Ad-hoc ChatGPT / Cursor sessions | No fixed OOS discipline; parameters tuned on held-out data |
| One-off notebooks per idea | Inconsistent metrics, no shared artifact structure |
| Generic coding agents | Lookahead bugs, missing fees/slippage, no robustness ladder |
| Black-box SaaS backtests | Data and code leave your environment |

**The gap:** speed without a **repeatable research OS**.

---

## What we deliver

**TheQuantGPT Cursor Lab** — a client-owned quant research environment on **your server**, powered by Cursor agents and a maintained **TheQuantGPT workflow layer** delivered via MCP API.

```text
You own:     server · data · generated code · charts · reports
We maintain: workflow layer · validators · PSA catalog · templates · updates
```

You operate the lab day to day. We built and maintain the research operating system that keeps agents on rails.

---

## How it works

### 1. Your server, your data

We bootstrap a thin **wrapper repo** on your cloud instance (typical setup: 1–2 working sessions). Your OHLCV parquet/CSV lives under `data/`. Nothing is bulk-uploaded to our API — workflow instructions only.

### 2. Cursor agents with guardrails

Cursor agents follow a written **constitution** (`AGENTS.md`), always-on rules, and research playbooks:

- Default **out-of-sample** discipline (e.g. cut-off `2025-01-01`)
- **In-sample / OOS** metrics reported separately
- **One robustness test per turn** (baseline first, then PSA, cost stress, Monte Carlo)
- Code isolated under `runs/<strategy_id>/` for audit and follow-ups

### 3. TheQuantGPT workflow layer (MCP)

Connected MCP tools provide **guidance**, **code validation**, and **robustness specs** tuned for systematic research — not a rigid script the agent must blindly follow.

| Tool | Purpose |
|------|---------|
| `tqg_get_guidance` | Hints for new strategies, follow-ups, and debugging |
| `tqg_validate_strategy_code` | Pre-run checks against quant invariants |
| `tqg_get_robustness_spec` | PSA and stress-test specifications |

### 4. Audit-ready artifacts

Every strategy run produces a durable folder:

```text
runs/<strategy_id>/
  run.json              # status, OOS, validation state
  strategy_spec.json    # symbol, params, costs, workflow
  code/                 # generated backtest scripts
  artifacts/            # metrics.json (IS + OOS), PSA summaries
  charts/               # equity curve, drawdown, heatmaps
  report.md             # human-readable summary
```

Follow-up prompts (“run PSA”, “stress costs”, “package for review”) attach to the same run — agents read `run.json` instead of guessing from chat history.

---

## What you can research (v1 scope)

| In scope | Out of scope |
|----------|--------------|
| Any asset class with OHLCV (crypto, equities, FX, bonds, metals) | Live trading or broker integration |
| Rule-based long/short strategies | Investment advice or performance guarantees |
| Local parquet/CSV + yfinance fallback | Custom data pipelines beyond documented schema |
| Baseline backtest → OOS → PSA → packaging | 24/7 ops or managed strategy development |

---

## What’s included

| Deliverable | Detail |
|-------------|--------|
| **Server bootstrap** | Wrapper repo, Python env, data schema, Cursor + MCP wiring (SOP-driven) |
| **Workflow layer** | MCP API access, validators, PSA catalog, prompt libraries |
| **Agent playbooks** | Research session, robustness follow-up, artifact packaging skills |
| **Onboarding** | Video calls + async support (tier-dependent) |
| **Ongoing updates** | Validator fixes, template improvements, workflow enhancements (while subscribed) |

### What you pay separately

- **Cursor** subscription (Pro or Business recommended)
- **Cloud server** (e.g. Hetzner CX32-class instance)
- **LLM API** usage (Anthropic / OpenAI via your keys)

---

## Pricing

| Stage | Price | Best for |
|-------|-------|----------|
| **7-day trial** | Free | Evaluate full workflow + MCP before committing |
| **Beta (design partner)** | €1,000 setup + €250/month (3-month minimum) | Early adopters shaping the product |
| **Standard Lab** | €3,500 setup + €500/month | Teams running ongoing research sessions |

**Trial terms:** full MCP access for 7 calendar days. No card required if agreed otherwise. You **keep** server, data, code, and artifacts after trial; MCP access ends unless you convert.

**Cancellation:** you retain all generated outputs; MCP access and updates cease.

---

## Why not just use Cursor in a blank repo?

A generic repo gives you an AI coder. TheQuantGPT Cursor Lab gives you a **research lab**:

| Blank repo / ad-hoc chat | TheQuantGPT Cursor Lab |
|--------------------------|------------------------|
| Agent improvises structure each time | Fixed `runs/<id>/` layout and `run.json` state |
| OOS often skipped or misapplied | Enforced IS/OOS split and no OOS tuning by default |
| One script, no robustness ladder | Baseline → PSA → cost stress → Monte Carlo, one step per turn |
| No domain validation | MCP validators catch lookahead, drift, and spec violations |
| Chat history is the memory | Durable strategy spec + artifacts survive compaction |
| You maintain the workflow | We maintain the workflow layer |

---

## Data & privacy

- **Your OHLCV files stay on your server.** They are not sent to the MCP API by default.
- Workflow requests (prompts, code snippets, run metadata) go to the MCP API for guidance and validation.
- **You own** all strategy code, metrics, charts, and reports generated on your server.
- **We own** the workflow layer, MCP service, and prompt libraries (internal research use license while subscribed).

---

## Typical journey

1. **Trial or beta signup** — API key issued, bootstrap SOP shared.
2. **Server setup** — clone wrapper (Binance daily OHLCV included), configure MCP, smoke test passes.
3. **First run** — agent builds a baseline backtest (e.g. BTC mean reversion or equity pullback), IS/OOS metrics + charts saved under `runs/`.
4. **Robustness** — PSA on in-sample parameters; review heatmap and stability.
5. **Iterate** — new strategies from your backlog; each gets its own run folder.
6. **Package** — validated runs bundled to `reports/` for internal review or investor updates.

**Time to first completed run (baseline + PSA):** typically one guided session after prerequisites are met.

---

## Proof — what a completed run looks like

A fresh clone has **empty** `runs/` and `reports/`. The first strategy is created on the client server (see [`examples/btc_mean_reversion.md`](https://github.com/chickenopoulos/thequantgpt-wrapper/blob/main/examples/btc_mean_reversion.md)). Each completed run looks like this:

```text
runs/<id>/
  run.json                 # status, OOS cut-off, validation_passed
  strategy_spec.json
  code/                    # generated vectorbt strategy
  artifacts/metrics.json   # in_sample + out_of_sample
  charts/equity_curve.png
  charts/drawdown.png
  report.md
reports/<id>/              # packaged bundle after validation
  manifest.json
```

Bundled data for that first run: Binance daily OHLCV under `data/binance/`.

### 90-second demo narrative (for calls)

1. **Prompt** — “Build BTC mean reversion, OOS from 2025-01-01, single asset only.”
2. **Agent** — scaffolds `runs/<id>/`, writes vectorbt code, runs backtest, saves `metrics.json` + charts.
3. **Follow-up** — “Run PSA on z-window and MA window, in-sample only.” → heatmap + `psa_summary.json`.
4. **Package** — `python scripts/tqg_package_artifacts.py <run_id>` → portable bundle under `reports/`.

Prompt scripts for the demo: [`examples/btc_mean_reversion.md`](https://github.com/chickenopoulos/thequantgpt-wrapper/blob/main/examples/btc_mean_reversion.md)

### What proof is *not*

- We do **not** cite these runs as alpha or trade recommendations.
- We **do** show that the lab produces auditable, repeatable research artifacts — including when the answer is “no edge.”

---

## What we do not promise

- Profitable strategies or outperformance
- Live trading connectivity
- Custom data engineering beyond the documented OHLCV schema
- Regulatory or investment advice

This is **research tooling** — designed to make your process faster, more consistent, and more auditable.

---

## Get started

| Step | Action |
|------|--------|
| 1 | **Book a 15-minute demo** — see a live run from prompt to packaged artifacts |
| 2 | **Start a 7-day free trial** — full MCP access, your server, your data |
| 3 | **Convert to beta or standard** — ongoing updates and support |

**Contact:** [your email / booking link]  
**Repo:** [thequantgpt-wrapper](https://github.com/chickenopoulos/thequantgpt-wrapper)  
**First-run prompts:** [`examples/btc_mean_reversion.md`](https://github.com/chickenopoulos/thequantgpt-wrapper/blob/main/examples/btc_mean_reversion.md)  
**Related docs:** [Offer (1-page)](OFFER.md) · [FAQ](../FAQ.md) · [Trial terms](TRIAL_TERMS.md)

---

## Outreach drafts (copy-paste per platform)

Replace `{first_name}`, `{company}`, `{your_name}`, and `[booking link]` before sending.

**Proof link to attach everywhere:**  
`https://github.com/chickenopoulos/thequantgpt-wrapper`  
First-run prompts: `https://github.com/chickenopoulos/thequantgpt-wrapper/blob/main/examples/btc_mean_reversion.md`

---

### Email — cold outreach

**Subject:** Systematic backtests on your server (sample outputs inside)

Hi {first_name},

Quick question for {company}: are strategy ideas still living in one-off notebooks and ChatGPT threads, or do you have a fixed process for out-of-sample testing and parameter sensitivity?

I help small systematic research teams set up **TheQuantGPT Cursor Lab** — a Cursor-powered research environment on **your own server**:

- Prompt agents to build and backtest rule-based strategies (no manual coding)
- Your OHLCV data stays local — not bulk-uploaded anywhere
- Fixed workflow: baseline → OOS split → PSA → saved `runs/<id>/` artifacts
- We maintain the workflow layer (validators, templates, MCP updates)

**Wrapper repo + first-run prompts:**  
https://github.com/chickenopoulos/thequantgpt-wrapper  
https://github.com/chickenopoulos/thequantgpt-wrapper/blob/main/examples/btc_mean_reversion.md

**7-day free trial** — full workflow + MCP access. Beta design partners: €1,000 setup + €250/month after trial.

Worth a 15-minute look? [booking link]

Best,  
{your_name}

---

### Email — follow-up (5–7 days, no reply)

**Subject:** Re: research lab on your server

Hi {first_name},

Bumping this once — happy to skip a call and just send the setup SOP if useful.

Repo + first-run prompts (BTC mean reversion, OOS from 2025-01-01):  
https://github.com/chickenopoulos/thequantgpt-wrapper/blob/main/examples/btc_mean_reversion.md

Still have a few beta slots. Reply “trial” if you want the 7-day setup link.

{your_name}

---

### LinkedIn — InMail / connection note

**Subject:** Research workflow on your own server?

Hi {first_name} — noticed {company}'s work in systematic research.

Are you still running ideas through ad-hoc AI chats, or do you have a fixed OOS + PSA process?

I set up **Cursor research labs on client servers** — backtests via agents, local data, saved artifacts under `runs/<id>/`. We maintain the workflow layer (validators, robustness ladder).

Repo: github.com/chickenopoulos/thequantgpt-wrapper

7-day free trial available. Worth 15 min?

---

### LinkedIn — short comment / DM (warm intro)

Thanks for connecting, {first_name}. If systematic backtesting ever becomes a bottleneck — we help teams run a fixed research workflow (OOS → PSA → packaged artifacts) on their own server via Cursor agents. Repo: github.com/chickenopoulos/thequantgpt-wrapper. Happy to share more if relevant.

---

### WhatsApp / Discord — group post

**Version A (announcement)**

Built something for small quant/crypto research teams tired of one-off AI backtests with no OOS discipline.

**TheQuantGPT Cursor Lab** = Cursor agents + your server + a maintained workflow layer (validators, PSA, saved run folders). Data stays local. Research only — no live trading.

First-run prompts (BTC MR on bundled Binance daily data):  
https://github.com/chickenopoulos/thequantgpt-wrapper/blob/main/examples/btc_mean_reversion.md

7-day free trial. Beta: €1k setup + €250/mo. DM me or email [your email] if you want the setup SOP.

---

**Version B (shorter, reply to “how do you backtest?” threads)**

We run a Cursor lab on our own server — prompt → backtest → OOS split → PSA → saved artifacts in `runs/<id>/`. Not a black-box SaaS; your data stays on the box.

Repo: https://github.com/chickenopoulos/thequantgpt-wrapper

Happy to share the 7-day trial setup if anyone’s evaluating this workflow.

---

**Version C (1:1 DM after group interest)**

Hey — saw your message on backtesting workflow. I can send the 7-day trial SOP + API key if you have a small Linux server and Cursor. Repo: https://github.com/chickenopoulos/thequantgpt-wrapper — takes ~1–2 sessions to get first baseline + PSA running.

---

### Platform tips

| Platform | Length | Attach |
|----------|--------|--------|
| **Email** | 150–200 words; one clear CTA | Repo + `examples/btc_mean_reversion.md` |
| **LinkedIn** | ≤ 300 characters for connection note; InMail can be longer | GitHub repo link only (no file attachments) |
| **WhatsApp / Discord** | 4–6 short lines; link on its own line | Same repo link; offer DM for trial SOP |

---

*TheQuantGPT Cursor Lab — systematic research at agent speed, on infrastructure you control.*
