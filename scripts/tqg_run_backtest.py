#!/usr/bin/env python3
"""Execute strategy code for a run folder and update run state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.execution import run_strategy_script  # noqa: E402
from tqg_client.mcp_validate import try_mcp_validate  # noqa: E402
from tqg_client.run_state import (  # noqa: E402
    load_run_state,
    merge_execution_feedback,
    save_run_state,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run strategy code under runs/<id>/code/")
    parser.add_argument("run_id", help="Run folder name")
    parser.add_argument("--code", help="Optional path to script relative to run root or absolute")
    parser.add_argument("--no-validate", action="store_true", help="Skip local static validation")
    parser.add_argument(
        "--mcp-validate",
        action="store_true",
        help="After a successful run, call MCP tqg_validate_strategy_code and update run.json",
    )
    parser.add_argument("--user-request", default="", help="Original user prompt (for validation context)")
    args = parser.parse_args()

    feedback: dict = {}
    try:
        state = load_run_state(args.run_id)
        code_path = Path(args.code) if args.code else None
        feedback = run_strategy_script(
            state,
            code_path=code_path,
            user_request=args.user_request,
            validate=not args.no_validate,
        )
        state = merge_execution_feedback(state, feedback)

        if args.mcp_validate and feedback.get("success"):
            review = try_mcp_validate(
                state,
                code_path=code_path,
                user_request=args.user_request,
                persist=False,
            )
            feedback["mcp_validation"] = review
            state.validation_passed = bool(review.get("approved"))
            if not review.get("approved"):
                feedback["validation_passed"] = False

        save_run_state(state)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(feedback, indent=2))
    ok = bool(feedback.get("success"))
    if args.mcp_validate and feedback.get("mcp_validation"):
        ok = ok and bool(feedback["mcp_validation"].get("approved"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
