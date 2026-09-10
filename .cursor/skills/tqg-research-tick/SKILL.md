---
name: tqg-research-tick
description: >-
  Execute one TQG lab research-loop tick (search, tag, one robustness test,
  baseline, extract, or halt). Use when the user says run program, research
  loop, lab loop, next tick, tqg_research_loop, or settle prior runs from
  lessons. Do not use for a named new strategy unless a charter is active.
---

# TQG research tick

This is the **lab operator** surface. TheQuantGPT remains the bench
(`tqg-research-session`, backtest, N/k/DSR). This skill takes **exactly one**
action from the policy engine, then stops.

Packaging is never part of a tick. Do not clone OOS winners. Do not retune on OOS.

## Start of tick

```bash
cd /root/thequantgpt-wrapper && source .venv/bin/activate
python scripts/tqg_research_loop.py status --program <program_id>
python scripts/tqg_research_loop.py tick --program <program_id>
```

If no charter exists:

```bash
python scripts/tqg_research_loop.py init --program qqq_mr_settle --symbol QQQ --max-ticks 8 --max-new-runs 2
```

Read `runs/_lab/programs/<program_id>/next_tick.md` and do **only** that action.

## Before any new baseline

```bash
python scripts/tqg_lesson_brief.py --symbol <SYMBOL> --text "<idea>" --with-runs
```

If blockers include `do_not_repeat` / fingerprint of `no_edge`/`killed`, **halt**.
Prefer `--related-to` over a silent duplicate.

## Action table

| Action | Do |
|--------|----|
| `halt` | Stop. Print `halt_reason`. Do not backtest. |
| `tag` | `python scripts/tqg_tag_run.py <run_id> --verdict … --reason "…" --tag loop_settled` |
| `one_robustness` | Skill `tqg-robustness-followup` on that run_id — **one** test |
| `baseline` | Skill `tqg-research-session` for the queued idea only if brief has no kill |
| `extract` | `python scripts/tqg_extract_lessons.py --merge` then harvest if asked |

## Reply

```
Program: …
Action: …   halt_reason: …
Run: …
IS Sharpe: …   OOS Sharpe: …
N / family N / k / DSR: …
Lessons applied: <ids or none>
```

Then stop. Do not start the next tick unless the user asks.
