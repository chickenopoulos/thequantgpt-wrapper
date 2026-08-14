#!/usr/bin/env python3
"""Set verdict / tags / related_runs / hypothesis on a run (lab memory)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.lab_index import (  # noqa: E402
    VERDICTS,
    load_lab_meta,
    save_lab_meta,
    upsert_run,
)
from tqg_client.run_state import load_run_state, save_run_state  # noqa: E402


def _uniq_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def tag_run(
    run_id: str,
    *,
    verdict: str | None = None,
    reason: str | None = None,
    add_tags: list[str] | None = None,
    remove_tags: list[str] | None = None,
    related_to: list[str] | None = None,
    unlink_related: list[str] | None = None,
    hypothesis: str | None = None,
    write_run_json: bool = True,
) -> dict:
    state = load_run_state(run_id)
    from tqg_client.run_state import run_root_from_state

    root = run_root_from_state(state)
    meta = load_lab_meta(root)

    if verdict is not None:
        if verdict not in VERDICTS:
            raise ValueError(f"Invalid verdict {verdict!r}; choose from {sorted(VERDICTS)}")
        state.verdict = verdict
        meta["verdict"] = verdict
        if verdict in {"no_edge", "killed"} and reason:
            state.kill_reason = reason
            meta["kill_reason"] = reason
        elif reason:
            # Non-kill reason still stored as kill_reason only when abandoning;
            # otherwise stash on hypothesis note if hypothesis empty — keep simple:
            meta["note"] = reason

    if reason and verdict in {"no_edge", "killed"}:
        state.kill_reason = reason
        meta["kill_reason"] = reason

    if hypothesis is not None:
        state.hypothesis = hypothesis
        meta["hypothesis"] = hypothesis

    tags = list(state.tags or meta.get("tags") or [])
    if add_tags:
        tags.extend(add_tags)
    if remove_tags:
        drop = set(remove_tags)
        tags = [t for t in tags if t not in drop]
    tags = _uniq_preserve([str(t).strip() for t in tags if str(t).strip()])
    state.tags = tags
    meta["tags"] = tags

    related = list(state.related_runs or meta.get("related_runs") or [])
    if related_to:
        related.extend(related_to)
    if unlink_related:
        drop = set(unlink_related)
        related = [r for r in related if r not in drop]
    related = _uniq_preserve([str(r).strip() for r in related if str(r).strip() and r != run_id])
    state.related_runs = related
    meta["related_runs"] = related

    if write_run_json:
        save_run_state(state)
    save_lab_meta(root, meta)
    card = upsert_run(run_id)
    return {"run_id": run_id, "lab_meta": meta, "card": card}


def main() -> int:
    parser = argparse.ArgumentParser(description="Tag a run with verdict / tags / relationships")
    parser.add_argument("run_id")
    parser.add_argument(
        "--verdict",
        choices=sorted(VERDICTS),
        help="Institutional memory verdict",
    )
    parser.add_argument("--reason", help="Kill / no_edge reason (or note)")
    parser.add_argument("--tag", action="append", default=[], help="Add tag (repeatable)")
    parser.add_argument("--untag", action="append", default=[], help="Remove tag (repeatable)")
    parser.add_argument(
        "--related-to",
        action="append",
        default=[],
        help="Link related run_id (repeatable)",
    )
    parser.add_argument(
        "--unlink-related",
        action="append",
        default=[],
        help="Remove related run_id (repeatable)",
    )
    parser.add_argument("--hypothesis", help="One-line research question")
    parser.add_argument(
        "--sidecar-only",
        action="store_true",
        help="Write lab_meta.json only (do not update run.json fields)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        result = tag_run(
            args.run_id,
            verdict=args.verdict,
            reason=args.reason,
            add_tags=args.tag,
            remove_tags=args.untag,
            related_to=args.related_to,
            unlink_related=args.unlink_related,
            hypothesis=args.hypothesis,
            write_run_json=not args.sidecar_only,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        card = result["card"]
        print(
            f"{card['run_id']}: verdict={card.get('verdict')} "
            f"tags={card.get('tags')} related={card.get('related_runs')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
