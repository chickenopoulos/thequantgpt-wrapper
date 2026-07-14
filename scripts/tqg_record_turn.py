#!/usr/bin/env python3
"""Append a turn record to runs/<id>/flow.json."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.config import resolve_path, load_config  # noqa: E402


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_turn(
    run_id: str,
    *,
    user_message: str = "",
    assistant_summary: str = "",
    status: str = "success",
) -> Path:
    runs_dir = resolve_path(load_config(), "runs_dir")
    flow_path = runs_dir / run_id / "flow.json"
    if not flow_path.exists():
        raise FileNotFoundError(f"Missing flow.json for run {run_id}")

    data = json.loads(flow_path.read_text(encoding="utf-8"))
    turns = data.get("turns") or []
    turn_index = len(turns)
    turns.append(
        {
            "turn_index": turn_index,
            "recorded_at": _utc_now(),
            "user_message": user_message,
            "assistant_summary": assistant_summary,
            "status": status,
        }
    )
    data["turns"] = turns
    data["updated_at"] = _utc_now()
    flow_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return flow_path


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
