"""Minimal static checks for strategy code (MCP-free fallback)."""

from __future__ import annotations

import re
from typing import Any


_BANNED_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bpf\.stats\s*\("), "Do not call pf.stats(); compute metrics manually."),
    (re.compile(r"\bdownload\s*\("), "Do not download external data inside strategy code."),
    (re.compile(r"requests\.(get|post)\s*\("), "Do not fetch remote data inside strategy code."),
    (re.compile(r"urllib\.request"), "Do not fetch remote data inside strategy code."),
]


def local_validate_code(code: str, user_request: str = "") -> dict[str, Any]:
    issues: list[str] = []
    required_fixes: list[str] = []

    for pattern, message in _BANNED_PATTERNS:
        if pattern.search(code):
            issues.append(message)
            required_fixes.append(message)

    if "vbt.Portfolio" not in code and "vectorbt" in code and "from_signals" not in code:
        issues.append("Expected vectorbt Portfolio construction (e.g. vbt.Portfolio.from_signals).")

    approved = not issues
    return {
        "approved": approved,
        "issues": issues,
        "required_fixes": required_fixes,
        "source": "local",
    }
