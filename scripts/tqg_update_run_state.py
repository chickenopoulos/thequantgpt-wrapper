#!/usr/bin/env python3
"""Merge execution or validation results into runs/<id>/run.json."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.lab_index import touch_run_index  # noqa: E402
from tqg_client.run_state import (  # noqa: E402
    RunState,
    load_run_state,
    merge_execution_feedback,
    save_run_state,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def apply_patch(state: RunState, patch: dict) -> RunState:
    for key, value in patch.items():
        if hasattr(state, key):
            setattr(state, key, value)
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="Update runs/<id>/run.json")
    parser.add_argument("run_id")
    parser.add_argument("--feedback-json", help="Path to execution feedback JSON file")
    parser.add_argument("--set-status", choices=["created", "baseline_complete", "psa_complete", "packaged", "failed"])
    parser.add_argument("--mark-step", help="Append a completed step name")
    parser.add_argument("--validation-passed", choices=["true", "false"])
    parser.add_argument("--patch-json", help="Inline JSON object with RunState fields to merge")
    args = parser.parse_args()

    try:
        state = load_run_state(args.run_id)

        if args.feedback_json:
            raw = json.loads(Path(args.feedback_json).read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("feedback JSON must be an object")
            state = merge_execution_feedback(state, raw)

        if args.patch_json:
            patch = json.loads(args.patch_json)
            if not isinstance(patch, dict):
                raise ValueError("patch JSON must be an object")
            state = apply_patch(state, patch)

        if args.set_status:
            state.status = args.set_status

        if args.mark_step:
            state.mark_step(args.mark_step)

        if args.validation_passed == "true":
            state.validation_passed = True
            state.last_validation_at = _utc_now()
        elif args.validation_passed == "false":
            state.validation_passed = False

        path = save_run_state(state)
        touch_run_index(args.run_id)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
