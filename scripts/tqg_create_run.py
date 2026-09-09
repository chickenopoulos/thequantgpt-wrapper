#!/usr/bin/env python3
"""Allocate a new strategy run folder under runs/."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.config import load_config  # noqa: E402
from tqg_client.lab_index import touch_run_index  # noqa: E402
from tqg_client.run_state import new_run_state, save_run_state  # noqa: E402
from tqg_client.selection import seed_selection  # noqa: E402

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
    cfg = load_config()
    numeric_id = _read_next_id()
    folder_name = run_id if run_id else str(numeric_id)
    if run_id and not _slug_ok(run_id):
        raise ValueError(f"Invalid run_id slug: {run_id!r}")

    root = RUNS / folder_name
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"Run folder already exists and is not empty: {root}")

    for sub in ("code", "artifacts", "charts", "logs", "inputs"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    state = new_run_state(
        run_id=folder_name,
        title=title,
        root=root,
        numeric_id=numeric_id if not run_id else None,
        cfg=cfg,
    )
    save_run_state(state)
    seed_selection(root)

    flow = {"turns": [], "updated_at": state.created_at}
    (root / "flow.json").write_text(json.dumps(flow, indent=2) + "\n", encoding="utf-8")
    (root / "RUN.md").write_text(
        f"# {title}\n\n"
        f"**Run ID:** {folder_name}\n"
        f"**Created:** {state.created_at}\n"
        f"**Root:** `{state.root}`\n"
        f"**Status:** {state.status}\n",
        encoding="utf-8",
    )

    if not run_id:
        _write_next_id(numeric_id + 1)

    touch_run_index(folder_name)
    return root


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a new runs/<id>/ workspace")
    parser.add_argument("--title", required=True, help="Human-readable run title")
    parser.add_argument("--run-id", help="Optional slug (e.g. btc_mean_reversion) instead of numeric id")
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
