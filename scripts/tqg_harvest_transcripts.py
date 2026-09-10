#!/usr/bin/env python3
"""Harvest Cursor agent transcripts into lesson candidates + transcript_map.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.lessons import merge_lessons, transcript_map_path  # noqa: E402
from tqg_client.transcript_harvest import (  # noqa: E402
    default_transcript_root,
    harvest_transcripts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine chats for lessons linked to TQG runs")
    parser.add_argument("--root", type=Path, help="Override transcript directory")
    parser.add_argument("--no-subagents", action="store_true")
    parser.add_argument("--no-merge", action="store_true", help="Do not write candidates into the lesson corpus")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = args.root or default_transcript_root()
    if not root.is_dir():
        print(f"error: transcript root not found: {root}", file=sys.stderr)
        return 1

    lessons, tmap = harvest_transcripts(
        transcript_root=root,
        include_subagents=not args.no_subagents,
    )
    map_path = transcript_map_path()
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(json.dumps(tmap, indent=2) + "\n", encoding="utf-8")

    meta = {}
    if not args.no_merge:
        meta = merge_lessons(lessons, replace=False)

    payload = {
        "transcript_root": str(root),
        "chats": tmap.get("chat_count"),
        "linked_chats": tmap.get("linked_chats"),
        "candidates": len(lessons),
        "map_path": str(map_path),
        "corpus": meta,
    }
    print(json.dumps(payload, indent=2) if args.json else (
        f"chats={payload['chats']} linked={payload['linked_chats']} "
        f"candidates={payload['candidates']} map={map_path}"
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
