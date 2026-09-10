#!/usr/bin/env python3
"""Compact lesson brief for MCP / research-session (blockers + process notes)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.lessons import lesson_brief, load_lessons, query_lessons  # noqa: E402
from tqg_client.mcp_helpers import lab_context_for_mcp  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Brief prior lessons before a new TQG baseline")
    parser.add_argument("--symbol")
    parser.add_argument("--text", help="Idea / keyword substring")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--with-runs", action="store_true", help="Also attach lab_context_for_mcp prior_runs")
    parser.add_argument("--failure-mode")
    parser.add_argument("--action-hint")
    args = parser.parse_args()

    if args.failure_mode or args.action_hint:
        rows = query_lessons(
            symbol=args.symbol,
            text=args.text,
            failure_mode=args.failure_mode,
            action_hint=args.action_hint,
            limit=args.limit,
        )
        payload = {"lessons": rows, "lesson_count_total": len(load_lessons())}
    else:
        payload = lesson_brief(symbol=args.symbol, text=args.text, limit=args.limit)

    if args.with_runs:
        payload["lab_context"] = lab_context_for_mcp(
            symbol=args.symbol, limit=args.limit, include_lessons=False
        )

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
