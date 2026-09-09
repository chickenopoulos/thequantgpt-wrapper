"""Closed formulaic-alpha operator catalog and a safe expression evaluator."""

from __future__ import annotations

import ast
import math
from typing import Any, Callable

import numpy as np
import pandas as pd

_EPS = 1e-8
_ALLOWED_AST = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.Call,
    ast.Name,
    ast.Constant,
    ast.Load,
    ast.keyword,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.And,
    ast.Or,
    ast.Eq,
    ast.NotEq,
    ast.Gt,
    ast.Lt,
    ast.GtE,
    ast.LtE,
    ast.Not,
    ast.Invert,
)


def _as_frame(x: Any) -> pd.DataFrame:
    if isinstance(x, pd.DataFrame):
        return x
    if isinstance(x, pd.Series):
        return x.to_frame()
    raise TypeError(f"Operator expected a panel DataFrame, got {type(x).__name__}")


def _int_window(n: Any) -> int:
    if isinstance(n, bool) or not isinstance(n, (int, float, np.integer, np.floating)):
        raise TypeError(f"Window must be a number, got {type(n).__name__}")
    n_int = int(n)
    if n_int < 1:
        raise ValueError(f"Window must be >= 1, got {n_int}")
    return n_int


def _minp(n: int) -> int:
    return max(2, n // 2)


def ts_delay(x: Any, n: Any) -> pd.DataFrame:
    return _as_frame(x).shift(_int_window(n))


def ts_delta(x: Any, n: Any) -> pd.DataFrame:
    w = _int_window(n)
    frame = _as_frame(x)
    return frame - frame.shift(w)


def ts_sum(x: Any, n: Any) -> pd.DataFrame:
    w = _int_window(n)
    return _as_frame(x).rolling(w, min_periods=_minp(w)).sum()


def ts_mean(x: Any, n: Any) -> pd.DataFrame:
    w = _int_window(n)
    return _as_frame(x).rolling(w, min_periods=_minp(w)).mean()


def ts_std(x: Any, n: Any) -> pd.DataFrame:
    w = _int_window(n)
    return _as_frame(x).rolling(w, min_periods=_minp(w)).std()


def ts_zscore(x: Any, n: Any) -> pd.DataFrame:
    w = _int_window(n)
    frame = _as_frame(x)
    mu = frame.rolling(w, min_periods=_minp(w)).mean()
    sd = frame.rolling(w, min_periods=_minp(w)).std().replace(0.0, np.nan)
    return (frame - mu) / sd


def ts_rank(x: Any, n: Any) -> pd.DataFrame:
    w = _int_window(n)
    return _as_frame(x).rolling(w, min_periods=_minp(w)).rank(pct=True)


def ts_min(x: Any, n: Any) -> pd.DataFrame:
    w = _int_window(n)
    return _as_frame(x).rolling(w, min_periods=_minp(w)).min()


def ts_max(x: Any, n: Any) -> pd.DataFrame:
    w = _int_window(n)
    return _as_frame(x).rolling(w, min_periods=_minp(w)).max()


def ts_ema(x: Any, n: Any) -> pd.DataFrame:
    w = _int_window(n)
    return _as_frame(x).ewm(span=w, min_periods=_minp(w), adjust=False).mean()


def ts_corr(x: Any, y: Any, n: Any) -> pd.DataFrame:
    w = _int_window(n)
    return _as_frame(x).rolling(w, min_periods=_minp(w)).corr(_as_frame(y))


def cs_rank(x: Any) -> pd.DataFrame:
    return _as_frame(x).rank(axis=1, pct=True)


def cs_zscore(x: Any) -> pd.DataFrame:
    frame = _as_frame(x)
    mu = frame.mean(axis=1)
    sd = frame.std(axis=1).replace(0.0, np.nan)
    return frame.sub(mu, axis=0).div(sd, axis=0)


def cs_demean(x: Any) -> pd.DataFrame:
    frame = _as_frame(x)
    return frame.sub(frame.mean(axis=1), axis=0)


def cs_winsorize(x: Any, p: Any = 0.05) -> pd.DataFrame:
    q = float(p)
    q = min(max(q, 0.0), 0.45)
    frame = _as_frame(x)
    lo = frame.quantile(q, axis=1)
    hi = frame.quantile(1.0 - q, axis=1)
    return frame.clip(lower=lo, upper=hi, axis=0)


def log(x: Any) -> pd.DataFrame:
    return np.log(_as_frame(x).abs() + _EPS)


def abs_(x: Any) -> pd.DataFrame:
    return _as_frame(x).abs()


def sign(x: Any) -> pd.DataFrame:
    return np.sign(_as_frame(x))


def neg(x: Any) -> pd.DataFrame:
    return -_as_frame(x)


def relu(x: Any) -> pd.DataFrame:
    return _as_frame(x).clip(lower=0.0)


def div(x: Any, y: Any) -> pd.DataFrame:
    return _as_frame(x) / _as_frame(y).replace(0.0, np.nan)


def cwise_max(x: Any, y: Any) -> pd.DataFrame:
    return pd.DataFrame(
        np.maximum(_as_frame(x).to_numpy(), _as_frame(y).to_numpy()),
        index=_as_frame(x).index,
        columns=_as_frame(x).columns,
    )


def cwise_min(x: Any, y: Any) -> pd.DataFrame:
    return pd.DataFrame(
        np.minimum(_as_frame(x).to_numpy(), _as_frame(y).to_numpy()),
        index=_as_frame(x).index,
        columns=_as_frame(x).columns,
    )


OPERATORS: dict[str, Callable[..., pd.DataFrame]] = {
    "ts_delay": ts_delay,
    "ts_shift": ts_delay,
    "ts_delta": ts_delta,
    "ts_sum": ts_sum,
    "ts_mean": ts_mean,
    "ts_std": ts_std,
    "ts_zscore": ts_zscore,
    "ts_rank": ts_rank,
    "ts_min": ts_min,
    "ts_max": ts_max,
    "ts_ema": ts_ema,
    "ts_corr": ts_corr,
    "cs_rank": cs_rank,
    "cs_zscore": cs_zscore,
    "cs_demean": cs_demean,
    "cs_winsorize": cs_winsorize,
    "log": log,
    "abs": abs_,
    "sign": sign,
    "neg": neg,
    "relu": relu,
    "div": div,
    "cwise_max": cwise_max,
    "cwise_min": cwise_min,
}

OPERANDS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "ret",
    "intra",
    "rng",
    "upper_wick",
    "lower_wick",
    "typical",
    "dollar_volume",
)

OPERATOR_HELP = {
    "ts_delay": "Shift panel by n bars (positive n = past).",
    "ts_delta": "x - x.shift(n).",
    "ts_mean": "Rolling mean, window n.",
    "ts_zscore": "Rolling z-score, window n.",
    "ts_rank": "Rolling percentile rank, window n.",
    "ts_corr": "Rolling correlation of two panels, window n.",
    "cs_rank": "Cross-sectional percentile rank (row-wise).",
    "cs_zscore": "Cross-sectional z-score (row-wise).",
    "cs_demean": "Subtract the cross-sectional mean (market neutralize).",
    "intra": "close - open (same-bar leftover; still lag the finished signal).",
    "upper_wick": "high - max(open, close).",
    "lower_wick": "min(open, close) - low.",
}


def derive_fields(ohlcv: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Add derived operand panels. Does not lag — the evaluator lags the finished signal."""
    close = ohlcv["close"]
    high = ohlcv["high"]
    low = ohlcv["low"]
    open_ = ohlcv["open"]
    volume = ohlcv["volume"]
    fields = dict(ohlcv)
    fields["ret"] = close.pct_change()
    fields["intra"] = close - open_
    fields["rng"] = (high - low).replace(0.0, np.nan)
    fields["upper_wick"] = high - np.maximum(open_, close)
    fields["lower_wick"] = np.minimum(open_, close) - low
    fields["typical"] = (high + low + close) / 3.0
    fields["dollar_volume"] = close * volume
    return fields


def catalog_payload() -> dict[str, Any]:
    return {
        "operands": list(OPERANDS),
        "operators": sorted(OPERATORS),
        "help": OPERATOR_HELP,
        "lag": "Evaluator always shifts the finished signal by 1 bar before scoring.",
    }


def _assert_safe(node: ast.AST) -> None:
    for child in ast.walk(node):
        if not isinstance(child, _ALLOWED_AST):
            raise ValueError(f"Disallowed syntax in alpha expression: {type(child).__name__}")
        if isinstance(child, ast.Call) and not isinstance(child.func, ast.Name):
            raise ValueError("Only simple function calls are allowed (no attribute calls)")
        if isinstance(child, ast.Name) and child.id.startswith("__"):
            raise ValueError(f"Disallowed name: {child.id}")


def substitute_params(expr: str, params: dict[str, Any] | None) -> str:
    out = str(expr)
    for key, val in (params or {}).items():
        if not str(key).isidentifier():
            raise ValueError(f"Invalid param name: {key!r}")
        token = "{" + str(key) + "}"
        out = out.replace(token, str(val))
    return out


def evaluate_expr(
    expr: str,
    fields: dict[str, pd.DataFrame],
    *,
    params: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Evaluate a formula against OHLCV-derived panels. No attribute access, no imports."""
    source = substitute_params(expr, params).strip()
    if not source:
        raise ValueError("Empty alpha expression")
    tree = ast.parse(source, mode="eval")
    _assert_safe(tree)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    allowed = set(OPERATORS) | set(fields)
    unknown = sorted(names - allowed)
    if unknown:
        raise ValueError(f"Unknown names in expression: {unknown}")
    ns: dict[str, Any] = {**OPERATORS, **fields}
    value = eval(compile(tree, "<alpha>", "eval"), {"__builtins__": {}}, ns)  # noqa: S307
    frame = _as_frame(value)
    if not math.isfinite(float(np.nanmean(frame.to_numpy()))) and frame.notna().sum().sum() == 0:
        raise ValueError("Expression produced an all-NaN panel")
    return frame


def last_int_literal(expr: str) -> int | None:
    tree = ast.parse(substitute_params(expr, None).strip(), mode="eval")
    ints = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, int)]
    return ints[-1] if ints else None


def replace_last_int(expr: str, new_value: int) -> str:
    """Replace the last integer literal (typically a lookback window)."""
    source = expr.strip()
    tree = ast.parse(source, mode="eval")
    last: ast.Constant | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            last = node
    if last is None:
        raise ValueError(f"No integer window to mutate in {expr!r}")
    lines = source.splitlines()
    lineno = last.lineno - 1
    col = last.col_offset
    end_col = last.end_col_offset if last.end_col_offset is not None else col + len(str(last.value))
    line = lines[lineno]
    lines[lineno] = line[:col] + str(int(new_value)) + line[end_col:]
    return "\n".join(lines)
