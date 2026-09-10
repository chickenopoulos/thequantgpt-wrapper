#!/usr/bin/env python3
"""Smoke tests for lesson corpus + research-loop policy."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.lesson_extract import infer_failure_mode, lessons_from_run_card  # noqa: E402
from tqg_client.lessons import lesson_dedup_key, merge_lessons, new_lesson, query_lessons  # noqa: E402
from tqg_client.research_policy import default_charter, default_state, next_action, suggest_verdict  # noqa: E402


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_validate_and_query() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp)
        (runs / "_lab").mkdir()
        cfg = {"runs_dir": str(runs), "defaults": {"interval": "1d"}}
        killed = new_lesson(
            kind="hypothesis",
            failure_mode="no_edge_oos",
            claim="QQQ RSI weekly confirm has no edge on this sample.",
            action_hint="do_not_repeat",
            source="run",
            symbol="QQQ",
            related_runs=["qqq_rsi14_weekly_confirm"],
            oos_contaminated=True,
            confidence=0.9,
        )
        process = new_lesson(
            kind="process",
            failure_mode="missing_data",
            claim="On-chain columns are not local; do not retry the same SKIP.",
            action_hint="acquire_data",
            source="catalog",
            symbol="BTCUSDT",
            oos_contaminated=False,
            confidence=0.8,
        )
        meta = merge_lessons([killed, process], replace=True, cfg=cfg, runs_dir=runs)
        _assert(meta["lesson_count"] == 2, meta)
        qqq = query_lessons(symbol="QQQ", cfg=cfg, runs_dir=runs)
        _assert(len(qqq) == 1, qqq)
        _assert(qqq[0]["action_hint"] == "do_not_repeat", qqq[0])
        _assert(lesson_dedup_key(killed) == lesson_dedup_key(dict(killed)), "dedup unstable")


def test_infer_and_card_lessons() -> None:
    card = {
        "run_id": "qqq_rsi14_weekly_confirm",
        "title": "QQQ RSI14 weekly confirm",
        "symbol": "QQQ",
        "verdict": "no_edge",
        "kill_reason": "sparse signals; weekly confirm adds no edge",
        "tags": ["negative_result", "sparse_signals"],
        "metrics": {"in_sample": {"Sharpe": 0.2}, "out_of_sample": {"Sharpe": -0.4}},
    }
    _assert(infer_failure_mode(card) == "sparse_signals", infer_failure_mode(card))
    lessons = lessons_from_run_card(card)
    _assert(lessons, "expected lessons from killed card")
    _assert(any(r["action_hint"] == "do_not_repeat" for r in lessons), lessons)


def test_policy_duplicate_killed_and_oos_leak() -> None:
    fp = "single_asset_signals|MEAN_REVERSION|QQQ|1d|lookback=14"
    cards = [
        {
            "run_id": "qqq_rsi14_weekly_confirm",
            "symbol": "QQQ",
            "verdict": "no_edge",
            "params_fingerprint": fp,
            "kill_reason": "no edge",
            "status": "robustness_complete",
            "metrics": {"in_sample": {"Sharpe": 0.2}, "out_of_sample": {"Sharpe": -0.3}},
        },
        {
            "run_id": "spy_ldom_seasonal",
            "symbol": "SPY",
            "verdict": None,
            "status": "psa_complete",
            "validation_passed": True,
            "metrics": {"in_sample": {"Sharpe": 0.5}, "out_of_sample": {"Sharpe": 1.4}},
        },
    ]
    lessons = [
        new_lesson(
            kind="hypothesis",
            failure_mode="unsettled",
            claim="spy_ldom_seasonal is human-reviewed promising on this sample.",
            action_hint="halt_for_human",
            source="run",
            symbol="SPY",
            related_runs=["spy_ldom_seasonal"],
            oos_contaminated=True,
        )
    ]
    charter = default_charter("qqq_mr_settle", symbols=["QQQ"])
    state = default_state()
    dup = next_action(
        charter,
        state,
        cards=cards,
        lessons=lessons,
        proposed_fingerprint=fp,
    )
    _assert(dup["halt_reason"] == "duplicate_killed", dup)

    leak_charter = default_charter("spy_clone", symbols=["SPY"])
    leak = next_action(
        leak_charter,
        default_state(),
        cards=cards,
        lessons=lessons,
        proposed_idea="clone spy_ldom_seasonal calendar neighbors on SPY",
    )
    _assert(leak["halt_reason"] == "oos_leak", leak)

    budget = default_state()
    budget["ticks_used"] = 8
    halted = next_action(charter, budget, cards=cards, lessons=lessons)
    _assert(halted["halt_reason"] == "budget_ticks", halted)


def test_suggest_verdict() -> None:
    collapse = {
        "run_id": "x",
        "status": "baseline_complete",
        "metrics": {"in_sample": {"Sharpe": 1.2}, "out_of_sample": {"Sharpe": -0.2}},
        "validation_passed": True,
    }
    _assert(suggest_verdict(collapse) == "no_edge", suggest_verdict(collapse))
    _assert(suggest_verdict({"run_id": "spy_ldom_seasonal"}) == "promising", "reviewed promising")


def main() -> int:
    test_validate_and_query()
    test_infer_and_card_lessons()
    test_policy_duplicate_killed_and_oos_leak()
    test_suggest_verdict()
    print("OK tqg_test_lab_loop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
