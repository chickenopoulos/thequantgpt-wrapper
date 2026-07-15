#!/usr/bin/env python3
"""Run MCP validation on runs/<id>/code/ and update run.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.mcp_validate import try_mcp_validate  # noqa: E402
from tqg_client.run_state import load_run_state  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP validate strategy code for a run")
    parser.add_argument("run_id")
    parser.add_argument("--code", help="Optional script path relative to run root")
    parser.add_argument("--user-request", default="", help="Original user prompt")
    args = parser.parse_args()

    try:
        state = load_run_state(args.run_id)
        code_path = Path(args.code) if args.code else None
        review = try_mcp_validate(
            state,
            code_path=code_path,
            user_request=args.user_request,
            persist=True,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(review, indent=2))
    return 0 if review.get("approved") else 1


if __name__ == "__main__":
    raise SystemExit(main())
