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
    warnings: list[str] = []

    for pattern, message in _BANNED_PATTERNS:
        if pattern.search(code):
            issues.append(message)
            required_fixes.append(message)

    if "build_portfolio_from_strategy_spec" not in code and "vbt.Portfolio" not in code and "from_signals" not in code:
        if "vectorbt" in code:
            issues.append("Expected vectorbt Portfolio construction (e.g. vbt.Portfolio.from_signals or build_portfolio_from_strategy_spec).")

    if "record_trials(" in code and "from tqg_client.selection" not in code:
        warnings.append(
            "Inline candidate loop detected — prefer the injected record_trials(n, kind=...) helper "
            "so N is logged in artifacts/selection.json."
        )

    approved = not issues
    return {
        "approved": approved,
        "issues": issues,
        "required_fixes": required_fixes,
        "warnings": warnings,
        "source": "local",
    }


def selection_log_warnings(run_root) -> list[str]:
    """Advisory checks on artifacts/selection.json. Never fail validation on DSR."""
    from pathlib import Path

    from .run_state import load_strategy_spec
    from .selection import load_selection

    root = Path(run_root)
    warnings: list[str] = []
    sel_path = root / "artifacts" / "selection.json"
    if not sel_path.is_file():
        warnings.append("artifacts/selection.json missing — quote N and k only after a harness run.")
        return warnings
    data = load_selection(root)
    spec = load_strategy_spec(root) or {}
    n_legs = int(data.get("n_legs") or 1)
    if n_legs > 1:
        ranking = spec.get("ranking") if isinstance(spec.get("ranking"), dict) else {}
        if not spec.get("signals") and not spec.get("ensemble_weights") and not ranking.get("sub_scores"):
            warnings.append("n_legs > 1 but strategy_spec has no signals / ensemble_weights / ranking.sub_scores.")
    dsr = data.get("dsr") if isinstance(data.get("dsr"), dict) else {}
    if dsr.get("error") == "missing_is_returns":
        warnings.append("DSR not computed — persist IS returns via pf or persist_is_returns(...).")
    return warnings
