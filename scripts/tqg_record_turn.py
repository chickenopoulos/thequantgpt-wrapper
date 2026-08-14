#!/usr/bin/env python3
"""Append a turn record to runs/<id>/flow.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.lab_index import touch_run_index  # noqa: E402
from tqg_client.run_state import append_flow_turn  # noqa: E402


def record_turn(
    run_id: str,
    *,
    user_message: str = "",
    assistant_summary: str = "",
    status: str = "success",
) -> Path:
    path = append_flow_turn(
        run_id,
        user_message=user_message,
        assistant_summary=assistant_summary,
        status=status,
    )
    touch_run_index(run_id)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a conversation turn in flow.json")
    parser.add_argument("run_id")
    parser.add_argument("--user", default="", help="User message summary")
    parser.add_argument("--assistant", default="", help="Agent reply summary")
    parser.add_argument("--status", default="success", choices=["success", "failed", "partial"])
    args = parser.parse_args()

    try:
        path = record_turn(
            args.run_id,
            user_message=args.user,
            assistant_summary=args.assistant,
            status=args.status,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
