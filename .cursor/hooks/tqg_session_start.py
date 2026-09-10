#!/usr/bin/env python3
"""sessionStart: remind the agent to brief TQG lab memory."""

from __future__ import annotations

import json
import sys
from pathlib import Path

WRAPPER = Path("/root/thequantgpt-wrapper")

NOTE = (
    "TQG lab memory is active. Before a new baseline run:\n"
    "  cd /root/thequantgpt-wrapper && python scripts/tqg_lesson_brief.py "
    "--symbol <SYMBOL> --text \"<idea>\" --with-runs\n"
    "Do not silently re-run verdict no_edge/killed. Do not clone OOS winners. "
    "One robustness test per turn. Packaging is never automatic. "
    "Autonomous ticks: python scripts/tqg_research_loop.py status --program <id> "
    "and skill tqg-research-tick."
)


def main() -> int:
    try:
        json.load(sys.stdin)
    except json.JSONDecodeError:
        pass
    print(json.dumps({"additional_context": NOTE}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
