# Lab research loop (operator surface)

TheQuantGPT still runs one experiment honestly (`tqg_run_backtest.py`, N/k/DSR).
This loop decides **which** experiment to settle next, using lessons from prior
runs and chats. It does not live-trade, does not package, and does not clone
OOS winners.

## Refresh the corpus

```bash
cd /root/thequantgpt-wrapper && source .venv/bin/activate
python scripts/tqg_extract_lessons.py --apply-catalog-tags --link-families
python scripts/tqg_harvest_transcripts.py
python scripts/tqg_lesson_brief.py --symbol QQQ --text "rsi pullback"
```

## Interactive research (same as TQG)

Ask for a named strategy as usual. The agent must call `tqg_lesson_brief.py`
before `tqg_create_run.py`. Halt on `do_not_repeat` / fingerprint of `no_edge`.

## Program ticks

```bash
python scripts/tqg_research_loop.py init --program qqq_mr_settle --symbol QQQ --max-ticks 8 --max-new-runs 2
python scripts/tqg_research_loop.py status --program qqq_mr_settle
python scripts/tqg_research_loop.py tick --program qqq_mr_settle --dry-run
python scripts/tqg_research_loop.py tick --program qqq_mr_settle
```

Then follow `runs/_lab/programs/<id>/next_tick.md` (skill `tqg-research-tick`).
One action per tick. Re-run `status` after the action.

Optional unattended invoke (requires `CURSOR_API_KEY` and `cursor_sdk`):

```bash
python scripts/tqg_research_loop.py tick --program qqq_mr_settle --invoke-agent
```

## Halt reasons

| halt_reason | Meaning |
|-------------|---------|
| `duplicate_killed` | Fingerprint matches `no_edge` / `killed` |
| `oos_leak` | Idea cites a human-reviewed OOS-promising run |
| `promising_review` | This sample looks good — human packages |
| `budget_ticks` / `budget_n` / `budget_runs` | Charter budget |
| `one_test_per_tick` | Robustness already used this tick |
| `queue_empty` | Nothing left to settle |
