#!/usr/bin/env python3
"""Allocate a new strategy run folder under runs/."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
RUNS = _REPO / "runs"
NEXT_ID_FILE = RUNS / ".next_id"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _read_next_id() -> int:
    if NEXT_ID_FILE.exists():
        raw = NEXT_ID_FILE.read_text(encoding="utf-8").strip()
        if raw.isdigit():
            return int(raw)
    return 1


def _write_next_id(n: int) -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    NEXT_ID_FILE.write_text(str(n) + "\n", encoding="utf-8")


def _slug_ok(slug: str) -> bool:
    return bool(SLUG_RE.match(slug))


def create_run(*, title: str, run_id: str | None = None) -> Path:
    RUNS.mkdir(parents=True, exist_ok=True)
    numeric_id = _read_next_id()
    folder_name = run_id if run_id else str(numeric_id)
    if run_id and not _slug_ok(run_id):
        raise ValueError(f"Invalid run_id slug: {run_id!r}")

    root = RUNS / folder_name
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"Run folder already exists and is not empty: {root}")

    for sub in ("code", "artifacts", "charts", "logs"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    created = datetime.now(timezone.utc).isoformat()
    meta = {
        "run_id": folder_name,
        "numeric_id": numeric_id,
        "title": title,
        "source": "cursor_agent",
        "created_at": created,
        "root": str(root.relative_to(_REPO)),
    }
    (root / "run.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (root / "flow.json").write_text(
        json.dumps({"turns": [], "updated_at": created}, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "RUN.md").write_text(
        f"# {title}\n\n**Run ID:** {folder_name}\n**Created:** {created}\n**Root:** `{meta['root']}`\n",
        encoding="utf-8",
    )

    if not run_id:
        _write_next_id(numeric_id + 1)

    return root


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a new runs/<id>/ workspace")
    parser.add_argument("--title", required=True, help="Human-readable run title")
    parser.add_argument("--run-id", help="Optional slug (e.g. demo_btc_mr) instead of numeric id")
    args = parser.parse_args()
    try:
        root = create_run(title=args.title, run_id=args.run_id)
    except (ValueError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
