"""Budgeted next-action policy for the TQG research loop.

The loop settles hypotheses. It must not maximize next-run OOS Sharpe.
Each tick is one research action (robustness ladder).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .lab_index import _metric_value, search_runs
from .lessons import PROMISING_REVIEWED, load_lessons, query_lessons

ACTIONS = frozenset(
    {
        "halt",
        "search",
        "tag",
        "one_robustness",
        "extend_related",
        "baseline",
        "extract",
    }
)

DEFAULT_BUDGETS = {
    "max_ticks": 8,
    "max_new_runs": 2,
    "max_n_increment": 20,
    "max_family_n": 50,
}


def suggest_verdict(card: dict[str, Any]) -> str | None:
    """Settle *this* run from its own artifacts. Not a search prior for neighbors."""
    rid = str(card.get("run_id") or "")
    if rid in PROMISING_REVIEWED:
        return "promising"
    status = str(card.get("status") or "")
    err = str(card.get("last_error") or "").lower()
    blob = " ".join(
        str(x)
        for x in (card.get("kill_reason"), card.get("title"), err, " ".join(str(t) for t in (card.get("tags") or [])))
        if x
    ).lower()
    if status == "failed" or err:
        if any(w in blob for w in ("missing", "not local", "skip", "column")):
            return "killed"
        if "no_trades" in blob or "no trades" in blob:
            return "no_edge"
        if err:
            return "killed"
    is_s = _metric_value(card, "in_sample")
    oos = _metric_value(card, "out_of_sample")
    if is_s is not None and oos is not None:
        gap = is_s - oos
        if is_s >= 0.4 and (oos <= 0 or gap > 1.0):
            return "no_edge"
        if (
            oos >= 0.5
            and bool(card.get("validation_passed"))
            and gap <= 0.5
            and status in {"psa_complete", "robustness_complete"}
        ):
            return "promising"
    if status == "baseline_complete" and not card.get("verdict"):
        return "needs_robustness"
    if status in {"psa_complete", "robustness_complete"} and not card.get("verdict"):
        if oos is not None and oos <= 0:
            return "no_edge"
        if oos is not None and oos >= 0.5 and bool(card.get("validation_passed")):
            return "promising"
        return "needs_robustness"
    return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_charter(
    program_id: str,
    *,
    symbols: list[str],
    asset_classes: list[str] | None = None,
    max_ticks: int = 8,
    max_new_runs: int = 2,
    hypothesis_queue: list[dict[str, str]] | None = None,
    include_catalog: bool = False,
    title: str | None = None,
) -> dict[str, Any]:
    return {
        "program_id": program_id,
        "title": title or program_id,
        "created_at": _utc_now(),
        "status": "active",
        "universe": {
            "symbols": symbols,
            "asset_classes": asset_classes or [],
        },
        "allowed_actions": [
            "search",
            "extend_related",
            "baseline",
            "one_robustness",
            "tag",
            "extract",
        ],
        "budgets": {
            **DEFAULT_BUDGETS,
            "max_ticks": max_ticks,
            "max_new_runs": max_new_runs,
        },
        "allow_variant": False,
        "include_catalog": include_catalog,
        "hypothesis_queue": hypothesis_queue or [],
        "notes": (
            "Packaging is never automatic. OOS-contaminated lessons are blockers. "
            "One robustness test per tick."
        ),
    }


def default_state() -> dict[str, Any]:
    return {
        "ticks_used": 0,
        "new_runs": 0,
        "n_increment": 0,
        "halt_reason": None,
        "last_action": None,
        "active_run_id": None,
        "robustness_this_tick": False,
        "updated_at": _utc_now(),
    }


def _in_universe(card: dict[str, Any], charter: dict[str, Any]) -> bool:
    uni = charter.get("universe") or {}
    symbols = {str(s).lower() for s in (uni.get("symbols") or []) if s}
    classes = {str(s).lower() for s in (uni.get("asset_classes") or []) if s}
    if symbols:
        sym = str(card.get("symbol") or "").lower()
        if sym not in symbols:
            return False
    elif classes:
        ac = str(card.get("asset_class") or "").lower()
        if ac not in classes:
            return False
    rid = str(card.get("run_id") or "")
    if rid.startswith("catalog_") and not charter.get("include_catalog"):
        return False
    return True


def _is_allowed(charter: dict[str, Any], action: str) -> bool:
    allowed = charter.get("allowed_actions") or list(ACTIONS)
    return action in allowed


def _decision(
    action: str,
    *,
    reason: str,
    run_id: str | None = None,
    halt_reason: str | None = None,
    blockers: list[dict[str, Any]] | None = None,
    verdict: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "action": action,
        "reason": reason,
        "run_id": run_id,
        "halt_reason": halt_reason,
        "verdict": verdict,
        "blockers": blockers or [],
        "one_action": True,
        "may_package": False,
    }
    if extra:
        out.update(extra)
    return out


def fingerprint_blockers(
    *,
    fingerprint: str | None,
    symbol: str | None,
    lessons: list[dict[str, Any]],
    cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    if fingerprint:
        for card in cards:
            if card.get("params_fingerprint") == fingerprint and card.get("verdict") in {
                "no_edge",
                "killed",
            }:
                hits.append(
                    {
                        "run_id": card.get("run_id"),
                        "verdict": card.get("verdict"),
                        "kill_reason": card.get("kill_reason"),
                        "kind": "fingerprint_killed",
                    }
                )
        for row in lessons:
            if row.get("params_fingerprint") == fingerprint and row.get("action_hint") in {
                "do_not_repeat",
                "halt_for_human",
            }:
                hits.append(
                    {
                        "lesson_id": row.get("lesson_id"),
                        "claim": row.get("claim"),
                        "kind": "fingerprint_lesson",
                    }
                )
    if symbol:
        for row in query_lessons(symbol=symbol, action_hint="do_not_repeat", lessons=lessons, limit=12):
            hits.append(
                {
                    "lesson_id": row.get("lesson_id"),
                    "claim": row.get("claim"),
                    "related_runs": row.get("related_runs"),
                    "kind": "symbol_blocker",
                }
            )
    # Dedup by lesson_id/run_id
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for hit in hits:
        key = str(hit.get("lesson_id") or hit.get("run_id") or hit.get("claim") or "")
        if key in seen:
            continue
        seen.add(key)
        uniq.append(hit)
    return uniq


def next_action(
    charter: dict[str, Any],
    state: dict[str, Any],
    *,
    cards: list[dict[str, Any]] | None = None,
    lessons: list[dict[str, Any]] | None = None,
    proposed_fingerprint: str | None = None,
    proposed_idea: str | None = None,
    proposed_run_id: str | None = None,
) -> dict[str, Any]:
    budgets = {**DEFAULT_BUDGETS, **(charter.get("budgets") or {})}
    lessons = lessons if lessons is not None else load_lessons()
    if cards is None:
        uni = charter.get("universe") or {}
        symbols = uni.get("symbols") or [None]
        cards = []
        for sym in symbols:
            cards.extend(search_runs(symbol=sym, limit=80) if sym else search_runs(limit=80))
        # Dedup cards
        by_id = {str(c.get("run_id")): c for c in cards if isinstance(c, dict)}
        cards = list(by_id.values())

    universe_cards = [c for c in cards if _in_universe(c, charter)]
    blockers = fingerprint_blockers(
        fingerprint=proposed_fingerprint,
        symbol=(charter.get("universe") or {}).get("symbols", [None])[0]
        if (charter.get("universe") or {}).get("symbols")
        else None,
        lessons=lessons,
        cards=cards,
    )

    if state.get("halt_reason"):
        return _decision("halt", reason=str(state["halt_reason"]), halt_reason=str(state["halt_reason"]), blockers=blockers)

    if int(state.get("ticks_used") or 0) >= int(budgets["max_ticks"]):
        return _decision("halt", reason="max_ticks exhausted", halt_reason="budget_ticks", blockers=blockers)
    if int(state.get("n_increment") or 0) >= int(budgets["max_n_increment"]):
        return _decision("halt", reason="max_n_increment exhausted", halt_reason="budget_n", blockers=blockers)

    if proposed_fingerprint and any(h.get("kind") == "fingerprint_killed" for h in blockers):
        return _decision(
            "halt",
            reason="proposed fingerprint matches a killed / no_edge run",
            halt_reason="duplicate_killed",
            blockers=blockers,
        )

    # OOS leak: using a promising OOS winner as a search prior for a *new* baseline.
    if proposed_idea and not proposed_run_id:
        idea_l = proposed_idea.lower()
        for row in lessons:
            if row.get("action_hint") == "halt_for_human" and row.get("oos_contaminated"):
                title_bits = " ".join(str(r) for r in (row.get("related_runs") or []))
                if title_bits and any(r.lower() in idea_l for r in (row.get("related_runs") or []) if r):
                    return _decision(
                        "halt",
                        reason=(
                            "proposed idea cites a human-reviewed OOS-promising run; "
                            "register a new OOS window or a different asset instead of cloning"
                        ),
                        halt_reason="oos_leak",
                        blockers=blockers,
                        extra={"lesson_id": row.get("lesson_id")},
                    )

    active_id = proposed_run_id or state.get("active_run_id")
    active = next((c for c in cards if str(c.get("run_id")) == str(active_id)), None) if active_id else None

    if active:
        suggestion = suggest_verdict(active)
        rid = str(active.get("run_id"))
        if suggestion == "promising" or rid in PROMISING_REVIEWED:
            return _decision(
                "halt",
                reason=f"{rid} looks promising on this sample — human review before packaging",
                run_id=rid,
                halt_reason="promising_review",
                verdict="promising",
                blockers=blockers,
            )
        if suggestion in {"no_edge", "killed"} and _is_allowed(charter, "tag"):
            return _decision(
                "tag",
                reason=f"settle {rid} as {suggestion}",
                run_id=rid,
                verdict=suggestion,
                blockers=blockers,
            )
        if suggestion == "needs_robustness" and _is_allowed(charter, "one_robustness"):
            if state.get("robustness_this_tick"):
                return _decision(
                    "halt",
                    reason="already ran one robustness test this tick",
                    run_id=rid,
                    halt_reason="one_test_per_tick",
                    blockers=blockers,
                )
            return _decision(
                "one_robustness",
                reason=f"baseline complete on {rid}; run exactly one robustness test",
                run_id=rid,
                verdict="needs_robustness",
                blockers=blockers,
            )

    # Prefer settling existing unverdicted universe runs over creating new ones.
    unsettled = [
        c
        for c in universe_cards
        if not c.get("verdict")
        and str(c.get("run_id") or "") not in PROMISING_REVIEWED
    ]
    unsettled.sort(key=lambda c: str(c.get("updated_at") or c.get("created_at") or ""), reverse=True)

    # Prefer settling kills, then robustness, before any promising halt.
    kill_cards = []
    robust_cards = []
    promising_cards = []
    created_cards = []
    for card in unsettled:
        suggestion = suggest_verdict(card)
        if suggestion in {"no_edge", "killed"}:
            kill_cards.append((card, suggestion))
        elif suggestion == "needs_robustness":
            robust_cards.append(card)
        elif suggestion == "promising":
            promising_cards.append(card)
        elif card.get("status") in {"created", None}:
            created_cards.append(card)

    if kill_cards and _is_allowed(charter, "tag"):
        card, suggestion = kill_cards[0]
        rid = str(card.get("run_id"))
        return _decision(
            "tag",
            reason=f"unsettled run {rid} meets kill rule ({suggestion})",
            run_id=rid,
            verdict=suggestion,
            blockers=blockers,
        )
    if robust_cards and _is_allowed(charter, "one_robustness"):
        card = robust_cards[0]
        rid = str(card.get("run_id"))
        return _decision(
            "one_robustness",
            reason=f"{rid} has a baseline but no robustness yet",
            run_id=rid,
            verdict="needs_robustness",
            blockers=blockers,
        )
    if created_cards and _is_allowed(charter, "baseline"):
        card = created_cards[0]
        rid = str(card.get("run_id"))
        return _decision(
            "baseline",
            reason=f"finish baseline for existing run {rid} rather than opening a duplicate",
            run_id=rid,
            blockers=blockers,
        )
    if promising_cards:
        card = promising_cards[0]
        rid = str(card.get("run_id"))
        return _decision(
            "halt",
            reason=f"{rid} meets promising rule — human review",
            run_id=rid,
            halt_reason="promising_review",
            verdict="promising",
            blockers=blockers,
        )

    queue = list(charter.get("hypothesis_queue") or [])
    if queue and _is_allowed(charter, "baseline"):
        if int(state.get("new_runs") or 0) >= int(budgets["max_new_runs"]):
            return _decision("halt", reason="max_new_runs exhausted", halt_reason="budget_runs", blockers=blockers)
        item = queue[0]
        idea = str(item.get("idea") or item.get("title") or "")
        idea_l = idea.lower()
        for row in lessons:
            if row.get("action_hint") == "halt_for_human" and row.get("oos_contaminated"):
                if any(str(r).lower() in idea_l for r in (row.get("related_runs") or []) if r):
                    return _decision(
                        "halt",
                        reason=(
                            "queue item cites an OOS-promising run; "
                            "register a new OOS window or a different asset instead of cloning"
                        ),
                        halt_reason="oos_leak",
                        blockers=blockers,
                        extra={"lesson_id": row.get("lesson_id")},
                    )
        return _decision(
            "baseline",
            reason=f"charter queue: {item.get('title') or idea}",
            extra={"hypothesis": item},
            blockers=blockers,
        )

    if _is_allowed(charter, "extract"):
        return _decision(
            "extract",
            reason="universe settled for this charter; refresh lessons then halt next tick",
            blockers=blockers,
        )

    return _decision(
        "halt",
        reason="nothing left in universe / queue",
        halt_reason="queue_empty",
        blockers=blockers,
    )


def tick_prompt(decision: dict[str, Any], charter: dict[str, Any]) -> str:
    """Single-action prompt for the Cursor agent this tick."""
    action = decision.get("action")
    rid = decision.get("run_id") or "<run_id>"
    lines = [
        "You are executing one TQG research-loop tick. Do exactly one action, then stop.",
        f"Program: {charter.get('program_id')} — {charter.get('title')}",
        f"Action: {action}",
        f"Reason: {decision.get('reason')}",
        "Constraints: research only; no live trading; one robustness test this tick; "
        "do not retune on OOS; do not package; quote IS Sharpe, OOS Sharpe, N, k, DSR; "
        "link variants with related_runs.",
        "Before any new baseline: python scripts/tqg_lesson_brief.py --symbol <SYMBOL> --text \"<idea>\"",
    ]
    if decision.get("blockers"):
        lines.append("Blockers (do not re-run):")
        for hit in decision["blockers"][:8]:
            lines.append(f"- {hit.get('claim') or hit.get('run_id') or hit}")
    if action == "tag":
        lines.append(
            f"Run: python scripts/tqg_tag_run.py {rid} --verdict {decision.get('verdict')} "
            f"--reason \"{decision.get('reason')}\" --tag loop_settled"
        )
    elif action == "one_robustness":
        lines.append(f"Open runs/{rid}/run.json. Call tqg_get_robustness_spec. Implement one test. Backtest once.")
    elif action == "baseline":
        hypo = (decision.get("hypothesis") or {})
        lines.append(
            f"Search lab memory, then create or extend a run for: {hypo.get('title') or decision.get('reason')}. "
            "If a related no_edge run exists, halt instead of cloning it."
        )
    elif action == "extract":
        lines.append("Run: python scripts/tqg_extract_lessons.py && python scripts/tqg_harvest_transcripts.py")
    elif action == "halt":
        lines.append(f"Halt. halt_reason={decision.get('halt_reason')}. Do not create runs or backtest.")
    lines.append("After the action: python scripts/tqg_extract_lessons.py --merge")
    return "\n".join(lines)
