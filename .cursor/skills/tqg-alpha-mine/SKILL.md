---
name: tqg-alpha-mine
description: >-
  Mine formulaic alphas on a universe panel from a qualitative hunch (leftover,
  volume confirmation, wicks), score them by in-sample Rank IC, steer in English,
  then reveal OOS on a representative book. Use when the user says mine alphas,
  formulaic alpha, factor zoo, Rank IC, find signals in this dataset, or has a
  panel plus a hunch rather than a named single-asset rule.
---

# Formulaic alpha mining

Use this instead of `tqg-research-session` when the input is a **universe + hunch**
and the output is a **leaderboard of formulas**, not one ticker’s equity curve.

Single-name “build RSI on QQQ” stays on `tqg-research-session`.

## Loop

1. Inspect `data/` for a **long** OHLCV panel (`asset`/`symbol` column). Bundled: `data/binance/binance_futures_ohlcv_1d.parquet`.
2. Search lab memory; create a run.
3. Call `tqg_get_guidance` with the user request + `run.json`.
4. Confirm OOS if omitted (default `2025-01-01`).
5. **Turn 1 — seeds, IS only.** Do not pass `--reveal-oos`.
6. Report the leaderboard in English. Quote **N** from `artifacts/selection.json`. **k = 1** until a book is formed.
7. **Later turns — steer** with `--drop` / `--keep` / `--neutralize` / `--mutate`. Each *new* formula increments N. Replay of the same fingerprint does not.
8. **Stop fishing, then** `--book id1,id2 --reveal-oos`. Quote IS/OOS Rank IC and Sharpe, N, k, DSR. Do not promote the max-IS mutant; use the representative window.
9. Package with `tqg-package-run` when asked. Robustness of the book is `tqg-robustness-followup` (one test per message).

## Commands

```bash
python scripts/tqg_alpha_mine.py --catalog

python scripts/tqg_create_run.py --title "Nasdaq leftover / volume alphas"

python scripts/tqg_alpha_mine.py <run_id> \
  --panel data/binance/binance_futures_ohlcv_1d.parquet \
  --seeds leftover,volume,wick,momentum \
  --oos 2025-01-01 --top-n 50

python scripts/tqg_alpha_mine.py <run_id> --drop A_MO1,A_MO2 --neutralize

python scripts/tqg_alpha_mine.py <run_id> --mutate A_VP1 --windows 10,20,40

python scripts/tqg_alpha_mine.py <run_id> --keep A_LO1n,A_VP1n --book A_LO1n,A_VP1n --reveal-oos
```

Custom formulas: `inputs/alphas.json` as a list of `{id, expr, description}` and `--formulas runs/<id>/inputs/alphas.json`.

Expressions may only use the catalog (`python scripts/tqg_alpha_mine.py --catalog`). The harness **always lags the finished signal by 1 bar**.

`--neutralize` wraps formulas in `cs_demean(...)` (cross-sectional / market demean). There is no GICS map on the Binance panel.

## Ranking rules

- Rank and drop using **in-sample Rank IC** only until the user stops fishing.
- Flag `momentum_like` when `|corr_momentum| >= 0.70` vs `cs_rank(ts_sum(ret, 20))`.
- Never read OOS out of `alphas.json` to choose winners (`oos` is null until `--reveal-oos`).
- Every newly scored fingerprint is an N increment. Combining into `--book` sets **k**.
- Reply with IS/OOS Rank IC (and Sharpe of the rank L/S), N, k, DSR. DSR is not an OOS forecast.

## Reply shape

```
Run: <id>  status: …
Universe: <n> names from <panel>
IS Rank IC (best / book): … / …
OOS Rank IC: …   (n/a until --reveal-oos)
N / k / DSR: … / … / …
```

Table: id, expr, one-line description, IS Rank IC, corr vs momentum, flags.

Paths: `artifacts/alphas.json`, `artifacts/selection.json`.

## Custom seeds

Write Python **only** if the catalog cannot express the idea. Prefer `--formulas` JSON. If you write `runs/<id>/code/*.py`, still score through `tqg_alpha_mine.py` so N and the OOS freeze stay honest.

Operator details: [operators.md](operators.md).
