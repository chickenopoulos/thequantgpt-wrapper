#!/usr/bin/env python3
"""Rebuild runs/_lab/index.json from all runs/*/run.json folders."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.lab_index import index_path, rebuild_index  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Full rebuild of the cross-run lab memory index (runs/_lab/index.json)"
    )
    parser.add_argument("--json", action="store_true", help="Print full index JSON to stdout")
    args = parser.parse_args()

    try:
        index = rebuild_index()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    path = index_path()
    errors = index.pop("_rebuild_errors", None)
    n = len(index.get("runs") or {})
    print(f"rebuilt {path} ({n} runs)")
    if errors:
        print(f"warnings: skipped {len(errors)} run(s)", file=sys.stderr)
        for err in errors:
            print(f"  - {err.get('run_id')}: {err.get('error')}", file=sys.stderr)
    if args.json:
        print(json.dumps(index, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
