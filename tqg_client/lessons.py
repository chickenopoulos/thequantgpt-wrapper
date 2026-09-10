"""Cross-run lesson corpus — derived memory beside runs/_lab/index.json.

Lessons are structured claims (process, data, code, hypothesis, anti-pattern).
OOS numbers may document a settled run; they must not steer neighbor search.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import load_config
from .lab_index import lab_index_dir

log = logging.getLogger(__name__)

LESSONS_SCHEMA_VERSION = 1

LESSON_KINDS = frozenset({"process", "data", "code", "hypothesis", "anti_pattern"})
FAILURE_MODES = frozenset(
    {
        "no_edge_oos",
        "is_oos_collapse",
        "sparse_signals",
        "cost_sensitivity",
        "no_trades",
        "missing_data",
        "runner_error",
        "multiple_testing",
        "reconstruction_miss",
        "duplicate_killed",
        "runner_only_not_oos",
        "unsettled",
    }
)
ACTION_HINTS = frozenset(
    {
        "do_not_repeat",
        "extend_related",
        "acquire_data",
        "register_new_oos",
        "halt_for_human",
        "needs_robustness",
        "tag_unsettled",
    }
)
SOURCES = frozenset({"run", "catalog", "transcript", "manual", "policy"})

# Human-reviewed only — never auto-promote from OOS Sharpe.
PROMISING_REVIEWED = frozenset(
    {
        "spy_ldom_seasonal",
        "qqq_rsi2_mr",
        "qqq_pullback_reversal",
        "triangular_pairs",
        "mulvaney_concretum_replica",
        "idioskew_quintile_ls",
        "etf_concretum_tf_rank",
        "catalog_taa_06",
        "catalog_taa_01",
        "catalog_q_09",
        "catalog_mr_13",
        "sso_tlt_2x_rebalance",
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def lessons_dir(*, cfg: dict[str, Any] | None = None, runs_dir: Path | None = None) -> Path:
    return lab_index_dir(cfg=cfg, runs_dir=runs_dir) / "lessons"


def lessons_jsonl_path(*, cfg: dict[str, Any] | None = None, runs_dir: Path | None = None) -> Path:
    return lessons_dir(cfg=cfg, runs_dir=runs_dir) / "lessons.jsonl"


def lessons_meta_path(*, cfg: dict[str, Any] | None = None, runs_dir: Path | None = None) -> Path:
    return lessons_dir(cfg=cfg, runs_dir=runs_dir) / "lessons.meta.json"


def transcript_map_path(*, cfg: dict[str, Any] | None = None, runs_dir: Path | None = None) -> Path:
    return lab_index_dir(cfg=cfg, runs_dir=runs_dir) / "transcript_map.json"


def programs_dir(*, cfg: dict[str, Any] | None = None, runs_dir: Path | None = None) -> Path:
    return lab_index_dir(cfg=cfg, runs_dir=runs_dir) / "programs"


def active_tick_path(*, cfg: dict[str, Any] | None = None, runs_dir: Path | None = None) -> Path:
    return lab_index_dir(cfg=cfg, runs_dir=runs_dir) / "active_tick.json"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("failed to read %s: %s", path, exc)
        return None
    return data if isinstance(data, dict) else None


def lesson_dedup_key(lesson: dict[str, Any]) -> str:
    related = ",".join(sorted(str(r) for r in (lesson.get("related_runs") or []) if r))
    raw = "|".join(
        [
            str(lesson.get("source") or ""),
            str(lesson.get("kind") or ""),
            str(lesson.get("failure_mode") or ""),
            str(lesson.get("symbol") or ""),
            related,
            str(lesson.get("claim") or "")[:180],
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def validate_lesson(lesson: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not isinstance(lesson, dict):
        return ["lesson is not an object"]
    kind = lesson.get("kind")
    if kind not in LESSON_KINDS:
        issues.append(f"invalid kind {kind!r}")
    mode = lesson.get("failure_mode")
    if mode not in FAILURE_MODES:
        issues.append(f"invalid failure_mode {mode!r}")
    hint = lesson.get("action_hint")
    if hint not in ACTION_HINTS:
        issues.append(f"invalid action_hint {hint!r}")
    src = lesson.get("source")
    if src not in SOURCES:
        issues.append(f"invalid source {src!r}")
    claim = lesson.get("claim")
    if not isinstance(claim, str) or not claim.strip():
        issues.append("claim is required")
    if "oos_contaminated" not in lesson or not isinstance(lesson.get("oos_contaminated"), bool):
        issues.append("oos_contaminated must be bool")
    return issues


def new_lesson(
    *,
    kind: str,
    failure_mode: str,
    claim: str,
    action_hint: str,
    source: str,
    symbol: str | None = None,
    asset_class: str | None = None,
    workflow: str | None = None,
    strategy_type: str | None = None,
    related_runs: Iterable[str] | None = None,
    transcript_ids: Iterable[str] | None = None,
    evidence: str | None = None,
    oos_contaminated: bool = False,
    confidence: float = 0.7,
    params_fingerprint: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lesson: dict[str, Any] = {
        "lesson_id": "",
        "schema_version": LESSONS_SCHEMA_VERSION,
        "created_at": _utc_now(),
        "source": source,
        "kind": kind,
        "failure_mode": failure_mode,
        "symbol": symbol,
        "asset_class": asset_class,
        "workflow": workflow,
        "strategy_type": strategy_type,
        "related_runs": [str(r) for r in (related_runs or []) if str(r).strip()],
        "transcript_ids": [str(t) for t in (transcript_ids or []) if str(t).strip()],
        "claim": claim.strip(),
        "evidence": (evidence or "").strip()[:800] or None,
        "oos_contaminated": bool(oos_contaminated),
        "action_hint": action_hint,
        "confidence": float(max(0.0, min(1.0, confidence))),
        "params_fingerprint": params_fingerprint or None,
    }
    if extra:
        lesson.update(extra)
    lesson["lesson_id"] = f"L{lesson_dedup_key(lesson)}"
    issues = validate_lesson(lesson)
    if issues:
        raise ValueError("invalid lesson: " + "; ".join(issues))
    return lesson


def load_lessons(*, cfg: dict[str, Any] | None = None, runs_dir: Path | None = None) -> list[dict[str, Any]]:
    path = lessons_jsonl_path(cfg=cfg, runs_dir=runs_dir)
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and not validate_lesson(row):
                out.append(row)
    except OSError as exc:
        log.warning("failed to read lessons %s: %s", path, exc)
    return out


def merge_lessons(
    incoming: Iterable[dict[str, Any]],
    *,
    cfg: dict[str, Any] | None = None,
    runs_dir: Path | None = None,
    replace: bool = False,
) -> dict[str, Any]:
    existing = [] if replace else load_lessons(cfg=cfg, runs_dir=runs_dir)
    return save_lessons(list(existing) + list(incoming), cfg=cfg, runs_dir=runs_dir)


def save_lessons(
    lessons: Iterable[dict[str, Any]],
    *,
    cfg: dict[str, Any] | None = None,
    runs_dir: Path | None = None,
) -> dict[str, Any]:
    """Replace the corpus with deduplicated validated lessons."""
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    dropped = 0
    for lesson in lessons:
        if not isinstance(lesson, dict):
            dropped += 1
            continue
        issues = validate_lesson(lesson)
        if issues:
            dropped += 1
            log.debug("drop lesson: %s", issues)
            continue
        key = lesson_dedup_key(lesson)
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        if not lesson.get("lesson_id"):
            lesson = dict(lesson)
            lesson["lesson_id"] = f"L{key}"
        rows.append(lesson)

    path = lessons_jsonl_path(cfg=cfg, runs_dir=runs_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(body, encoding="utf-8")
    meta = {
        "schema_version": LESSONS_SCHEMA_VERSION,
        "updated_at": _utc_now(),
        "lesson_count": len(rows),
        "dropped": dropped,
    }
    _write_json(lessons_meta_path(cfg=cfg, runs_dir=runs_dir), meta)
    return meta


def query_lessons(
    *,
    symbol: str | None = None,
    workflow: str | None = None,
    strategy_type: str | None = None,
    kind: str | None = None,
    failure_mode: str | None = None,
    action_hint: str | None = None,
    source: str | None = None,
    related_run: str | None = None,
    text: str | None = None,
    oos_contaminated: bool | None = None,
    steering_only: bool = False,
    limit: int | None = 20,
    lessons: list[dict[str, Any]] | None = None,
    cfg: dict[str, Any] | None = None,
    runs_dir: Path | None = None,
) -> list[dict[str, Any]]:
    rows = lessons if lessons is not None else load_lessons(cfg=cfg, runs_dir=runs_dir)
    text_l = text.lower() if text else None
    matched: list[dict[str, Any]] = []
    for row in rows:
        if symbol:
            row_sym = str(row.get("symbol") or "").strip()
            if row_sym.lower() != symbol.lower():
                continue
        if workflow and str(row.get("workflow") or "").lower() != workflow.lower():
            continue
        if strategy_type and str(row.get("strategy_type") or "").lower() != strategy_type.lower():
            continue
        if kind and row.get("kind") != kind:
            continue
        if failure_mode and row.get("failure_mode") != failure_mode:
            continue
        if action_hint and row.get("action_hint") != action_hint:
            continue
        if source and row.get("source") != source:
            continue
        if related_run:
            related = [str(r) for r in (row.get("related_runs") or [])]
            if related_run not in related:
                continue
        if oos_contaminated is not None and bool(row.get("oos_contaminated")) != oos_contaminated:
            continue
        if steering_only and row.get("oos_contaminated") and row.get("action_hint") not in {
            "do_not_repeat",
            "halt_for_human",
            "acquire_data",
        }:
            # Contaminated lessons may only block, not suggest new baselines.
            continue
        if text_l:
            blob = " ".join(
                str(x)
                for x in (
                    row.get("claim"),
                    row.get("evidence"),
                    row.get("symbol"),
                    row.get("failure_mode"),
                    " ".join(str(r) for r in (row.get("related_runs") or [])),
                )
                if x
            ).lower()
            if text_l not in blob:
                continue
        matched.append(row)

    def _rank(row: dict[str, Any]) -> tuple:
        # Blockers and high-confidence kills first.
        hint = row.get("action_hint")
        hint_rank = 0 if hint in {"do_not_repeat", "halt_for_human", "acquire_data"} else 1
        src_rank = 0 if row.get("source") in {"run", "catalog", "manual"} else 1
        return (hint_rank, src_rank, -float(row.get("confidence") or 0), str(row.get("created_at") or ""))

    matched.sort(key=_rank)
    if limit is not None and limit >= 0:
        matched = matched[:limit]
    return matched


def _slim_lesson(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "lesson_id": row.get("lesson_id"),
        "kind": row.get("kind"),
        "failure_mode": row.get("failure_mode"),
        "claim": row.get("claim"),
        "action_hint": row.get("action_hint"),
        "related_runs": row.get("related_runs") or [],
        "oos_contaminated": bool(row.get("oos_contaminated")),
        "symbol": row.get("symbol"),
        "source": row.get("source"),
        "confidence": row.get("confidence"),
    }


def lesson_brief(
    *,
    symbol: str | None = None,
    text: str | None = None,
    limit: int = 8,
    cfg: dict[str, Any] | None = None,
    runs_dir: Path | None = None,
) -> dict[str, Any]:
    """Compact payload for MCP / skill briefing. Includes blockers even when OOS-tainted."""
    cfg = cfg or load_config()
    all_rows = load_lessons(cfg=cfg, runs_dir=runs_dir)
    blockers = query_lessons(
        symbol=symbol,
        lessons=all_rows,
        action_hint="do_not_repeat",
        limit=limit,
    )
    text_hits = (
        query_lessons(symbol=symbol, text=text, lessons=all_rows, limit=limit) if text else []
    )
    if symbol:
        extra_halt = query_lessons(symbol=symbol, lessons=all_rows, action_hint="halt_for_human", limit=4)
        extra_data = query_lessons(symbol=symbol, lessons=all_rows, action_hint="acquire_data", limit=4)
    else:
        extra_halt = query_lessons(lessons=all_rows, action_hint="halt_for_human", limit=3)
        extra_data = query_lessons(lessons=all_rows, action_hint="acquire_data", limit=3)

    # Steering slice: process/data/code without using OOS as a search prior.
    steering = query_lessons(
        symbol=symbol,
        text=text,
        lessons=all_rows,
        steering_only=True,
        limit=limit,
    )
    steering = [
        r
        for r in steering
        if r.get("action_hint") not in {"do_not_repeat", "halt_for_human"}
        or not r.get("oos_contaminated")
    ]

    seen: set[str] = set()
    lessons_out: list[dict[str, Any]] = []
    for row in blockers + extra_halt + extra_data + text_hits + steering:
        lid = str(row.get("lesson_id") or "")
        if not lid or lid in seen:
            continue
        seen.add(lid)
        lessons_out.append(_slim_lesson(row))
        if len(lessons_out) >= max(limit, 8):
            break

    return {
        "lessons": lessons_out,
        "blockers": [_slim_lesson(r) for r in blockers[:limit]],
        "lesson_count_total": len(all_rows),
        "symbol": symbol,
        "steering_note": (
            "OOS-contaminated claims are blockers for that exact sample/fingerprint. "
            "Do not clone neighbors from past OOS Sharpe. Prefer extend_related or halt."
        ),
    }


def claim_is_oos_contaminated(text: str | None) -> bool:
    if not text:
        return False
    blob = text.lower()
    return bool(
        re.search(
            r"\boos\b|out[- ]of[- ]sample|holdout|sharpe_oos|oos sharpe",
            blob,
        )
    )
