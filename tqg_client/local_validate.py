"""Minimal static checks for strategy code (MCP-free fallback)."""

from __future__ import annotations

import ast
import re
from typing import Any


_BANNED_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bpf\.stats\s*\("), "Do not call pf.stats(); compute metrics manually."),
    (re.compile(r"\bdownload\s*\("), "Do not download external data inside strategy code."),
    (re.compile(r"requests\.(get|post)\s*\("), "Do not fetch remote data inside strategy code."),
    (re.compile(r"urllib\.request"), "Do not fetch remote data inside strategy code."),
]


def _attr_call_chain(node: ast.AST) -> list[str]:
    """Outermost-first attribute/call names: close.rolling(n).mean().shift(1) -> [shift, mean, rolling]."""
    names: list[str] = []
    cur: ast.AST | None = node
    while cur is not None:
        if isinstance(cur, ast.Call):
            cur = cur.func
            continue
        if isinstance(cur, ast.Attribute):
            names.append(cur.attr)
            cur = cur.value
            continue
        break
    return names


def _rolling_missing_shift(node: ast.AST | None, hits: list[int]) -> None:
    if node is None:
        return
    if isinstance(node, ast.BoolOp):
        for value in node.values:
            _rolling_missing_shift(value, hits)
        return
    if isinstance(node, ast.BinOp):
        _rolling_missing_shift(node.left, hits)
        _rolling_missing_shift(node.right, hits)
        return
    if isinstance(node, ast.UnaryOp):
        _rolling_missing_shift(node.operand, hits)
        return
    if isinstance(node, ast.Compare):
        _rolling_missing_shift(node.left, hits)
        for comparator in node.comparators:
            _rolling_missing_shift(comparator, hits)
        return
    if isinstance(node, ast.IfExp):
        _rolling_missing_shift(node.test, hits)
        _rolling_missing_shift(node.body, hits)
        _rolling_missing_shift(node.orelse, hits)
        return
    if isinstance(node, ast.Subscript):
        _rolling_missing_shift(node.value, hits)
        _rolling_missing_shift(node.slice, hits)
        return
    if isinstance(node, ast.Call):
        names = _attr_call_chain(node)
        if "rolling" in names:
            if "shift" not in names:
                hits.append(int(getattr(node, "lineno", 0) or 0))
            return
        for arg in node.args:
            _rolling_missing_shift(arg, hits)
        for kw in node.keywords:
            _rolling_missing_shift(kw.value, hits)
        return
    if isinstance(node, ast.Attribute):
        names = _attr_call_chain(node)
        if "rolling" in names and "shift" not in names:
            hits.append(int(getattr(node, "lineno", 0) or 0))


def unshifted_rolling_lines(code: str) -> list[int]:
    """Line numbers where a .rolling(...) chain is used without .shift(."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    hits: list[int] = []

    class _Visitor(ast.NodeVisitor):
        def visit_Assign(self, node: ast.Assign) -> None:
            _rolling_missing_shift(node.value, hits)
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            _rolling_missing_shift(node.value, hits)
            self.generic_visit(node)

        def visit_AugAssign(self, node: ast.AugAssign) -> None:
            _rolling_missing_shift(node.value, hits)
            self.generic_visit(node)

        def visit_Return(self, node: ast.Return) -> None:
            _rolling_missing_shift(node.value, hits)
            self.generic_visit(node)

        def visit_Expr(self, node: ast.Expr) -> None:
            _rolling_missing_shift(node.value, hits)
            self.generic_visit(node)

    _Visitor().visit(tree)
    return sorted({n for n in hits if n})


_ROLLING_SHIFT_MSG = (
    "Unshifted .rolling(...) in a signal path — chain .shift(1) on the window "
    "(next-open fill lag is not a substitute)."
)


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

    rolling_lines = unshifted_rolling_lines(code)
    if rolling_lines:
        msg = f"{_ROLLING_SHIFT_MSG} Lines: {', '.join(str(n) for n in rolling_lines)}."
        issues.append(msg)
        required_fixes.append(msg)

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
