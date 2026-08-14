#!/usr/bin/env python3
"""Export compact lab memory context for MCP guidance calls."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.lab_index import index_path, lab_context_for_mcp, rebuild_index  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compact prior-run context for MCP (lab_context_for_mcp)"
    )
    parser.add_argument("--for-mcp", action="store_true", help="Alias kept for plan compatibility")
    parser.add_argument("--symbol", help="Filter prior runs by symbol")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--rebuild-if-missing",
        action="store_true",
        help="Rebuild index when runs/_lab/index.json is absent",
    )
    args = parser.parse_args()

    try:
        if args.rebuild_if_missing and not index_path().exists():
            rebuild_index()
        ctx = lab_context_for_mcp(symbol=args.symbol, limit=args.limit)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(ctx, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
