"""Static smells for look-ahead that regex/AST can see in strategy code.

Unshifted rolling stays in local_validate.py (AST). This module covers future
shifts, bfill, shuffled CV, and full-sample scalers.
"""

from __future__ import annotations

import ast
import re

_REGEX_RULES: list[tuple[str, str, str, str, str]] = [
    (
        "bfill",
        "issue",
        r"\.bfill\(|method\s*=\s*['\"]bfill['\"]|fillna\(\s*method\s*=\s*['\"]b",
        "backward fill propagates future observations into earlier timestamps",
        "Use .ffill() for time series. bfill is almost never correct on a price panel.",
    ),
    (
        "shuffle-split",
        "issue",
        r"train_test_split\((?![^)]*shuffle\s*=\s*False)",
        "train_test_split defaults to shuffle=True, which destroys time ordering",
        "Pass shuffle=False, or use a time-series split with a purge/embargo.",
    ),
    (
        "kfold-shuffle",
        "warning",
        r"(KFold|StratifiedKFold)\([^)]*shuffle\s*=\s*True",
        "shuffled k-fold interleaves test rows among their temporal neighbours",
        "Use TimeSeriesSplit or a purged split with an embargo.",
    ),
    (
        "scaler-before-split",
        "warning",
        r"(StandardScaler|MinMaxScaler|RobustScaler|QuantileTransformer)\(\)\s*\.fit\(",
        "fitting a scaler before splitting leaks the test-set distribution into training",
        "Fit inside a Pipeline so it refits on each training fold.",
    ),
    (
        "resample-last",
        "warning",
        r"\.resample\([^)]*\)\s*\.\s*last\(\)",
        "resample().last() stamps a period with its end value, known only after the period",
        "Use .first(), or shift the resampled series forward one period.",
    ),
]


def _live_text(code: str) -> str:
    lines = []
    for ln in (code or "").splitlines():
        if ln.lstrip().startswith("#"):
            continue
        lines.append(re.sub(r"#.*", "", ln))
    return "\n".join(lines)


def negative_shift_lines(code: str) -> list[int]:
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return []
    hits: list[int] = []

    class _V(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else ""
            if name == "shift" and node.args:
                arg = node.args[0]
                neg = False
                if isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub):
                    neg = True
                elif isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)) and arg.value < 0:
                    neg = True
                if neg:
                    hits.append(int(getattr(node, "lineno", 0) or 0))
            self.generic_visit(node)

    _V().visit(tree)
    return sorted({n for n in hits if n})


def lookahead_smell_review(code: str) -> dict[str, list[str]]:
    issues: list[str] = []
    required_fixes: list[str] = []
    warnings: list[str] = []
    live = _live_text(code)

    neg = negative_shift_lines(code)
    if neg:
        msg = (
            "Negative .shift(...) pulls future values into the current row. "
            f"Lines: {', '.join(str(n) for n in neg)}. "
            "Only shift features backward (positive). Forward labels belong on a separate series."
        )
        issues.append(msg)
        required_fixes.append(msg)

    for rid, sev, pattern, why, fix in _REGEX_RULES:
        if re.search(pattern, live):
            text = f"[{rid}] {why} — {fix}"
            if sev == "issue":
                issues.append(text)
                required_fixes.append(fix)
            else:
                warnings.append(text)
    return {"issues": issues, "required_fixes": required_fixes, "warnings": warnings}
