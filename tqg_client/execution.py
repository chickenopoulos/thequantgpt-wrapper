"""Execute strategy scripts inside a run folder with injected namespace."""

from __future__ import annotations

import contextlib
import io
import json
import runpy
import sys
import traceback
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import vectorbt as vbt  # noqa: E402

from .config import repo_root
from .local_validate import local_validate_code
from .market_data import load_ohlcv_panel, load_symbol_close, load_symbol_from_parquet
from .alpha_ops import evaluate_expr
from .portfolio import build_portfolio_from_strategy_spec
from .run_state import RunState, load_strategy_spec, run_root_from_state
from .selection import persist_is_returns as _persist_is_returns
from .selection import record_trials as _record_trials


class ExecutionError(RuntimeError):
    pass


def _portable_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root().resolve()))
    except ValueError:
        return str(path)


def resolve_code_path(run_root: Path, code_path: Path | None = None) -> Path:
    if code_path is not None:
        path = code_path if code_path.is_absolute() else run_root / code_path
        if not path.exists():
            raise FileNotFoundError(path)
        return path.resolve()

    code_dir = run_root / "code"
    if not code_dir.is_dir():
        raise FileNotFoundError(f"Missing code directory: {code_dir}")

    py_files = sorted(code_dir.glob("*.py"))
    if not py_files:
        raise FileNotFoundError(f"No Python files under {code_dir}")

    preferred = [p for p in py_files if p.name not in {"__init__.py", "conftest.py"}]
    return (preferred[0] if preferred else py_files[0]).resolve()


def _collect_artifacts(run_root: Path) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    metrics = run_root / "artifacts" / "metrics.json"
    if metrics.exists():
        artifacts["metrics"] = _portable_path(metrics)

    for chart in sorted((run_root / "charts").glob("*.png")):
        key = chart.stem
        artifacts[key] = _portable_path(chart)

    spec = run_root / "strategy_spec.json"
    if spec.exists():
        artifacts["strategy_spec"] = _portable_path(spec)

    report = run_root / "report.md"
    if report.exists():
        artifacts["report"] = _portable_path(report)

    selection = run_root / "artifacts" / "selection.json"
    if selection.exists():
        artifacts["selection"] = _portable_path(selection)

    alphas = run_root / "artifacts" / "alphas.json"
    if alphas.exists():
        artifacts["alphas"] = _portable_path(alphas)

    return artifacts


def _infer_completed_step(run_root: Path, before: set[str]) -> str | None:
    after = set(_collect_artifacts(run_root).keys())
    new_keys = after - before
    names = " ".join(new_keys).lower()
    if "psa" in names:
        return "psa"
    if "metrics" in new_keys and "baseline" not in before:
        return "baseline"
    if new_keys:
        return "robustness"
    return None


def build_namespace(
    *,
    run_root: Path,
    state: RunState,
    strategy_spec: dict[str, Any] | None,
) -> dict[str, Any]:
    spec = strategy_spec or load_strategy_spec(run_root) or {}
    return {
        "__builtins__": __builtins__,
        "REPO_ROOT": repo_root(),
        "RUN_ROOT": run_root,
        "RUN_ID": state.run_id,
        "strategy_spec": spec,
        "persistent_run_state": state.to_dict(),
        "artifact_manifest": state.artifact_manifest(),
        "pd": pd,
        "np": np,
        "plt": plt,
        "vbt": vbt,
        "load_symbol_from_parquet": load_symbol_from_parquet,
        "load_symbol_close": load_symbol_close,
        "load_ohlcv_panel": load_ohlcv_panel,
        "evaluate_expr": evaluate_expr,
        "build_portfolio_from_strategy_spec": build_portfolio_from_strategy_spec,
        "record_trials": lambda n, kind="inline_grid", **meta: _record_trials(run_root, n, kind=kind, **meta),
        "persist_is_returns": lambda series: _persist_is_returns(run_root, series),
    }


def run_strategy_script(
    state: RunState,
    *,
    code_path: Path | None = None,
    user_request: str = "",
    validate: bool = True,
) -> dict[str, Any]:
    run_root = run_root_from_state(state)
    script = resolve_code_path(run_root, code_path)
    code = script.read_text(encoding="utf-8")

    validation: dict[str, Any] | None = None
    if validate:
        validation = local_validate_code(code, user_request)
        if not validation.get("approved"):
            return {
                "success": False,
                "error": "validation failed",
                "validation": validation,
                "code_path": _portable_path(script),
            }

    logs_dir = run_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{script.stem}.log"

    before_artifacts = set(_collect_artifacts(run_root).keys())
    namespace = build_namespace(run_root=run_root, state=state, strategy_spec=load_strategy_spec(run_root))

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    success = False
    error: str | None = None

    try:
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            runpy.run_path(str(script), init_globals=namespace, run_name="__main__")
        success = True
    except Exception as exc:
        error = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    log_body = (
        f"# execution: {script.name}\n\n"
        f"## stdout\n{stdout_capture.getvalue()}\n\n"
        f"## stderr\n{stderr_capture.getvalue()}\n\n"
    )
    if error:
        log_body += f"## traceback\n{error}\n"
    log_path.write_text(log_body, encoding="utf-8")

    if not success:
        return {
            "success": False,
            "error": error or "execution failed",
            "log_path": _portable_path(log_path),
            "code_path": _portable_path(script),
            "validation": validation,
        }

    pf = namespace.get("pf")
    snapshot = (
        namespace.get("_strategy_snapshot")
        or namespace.get("strategy_snapshot")
        or {}
    )
    if not isinstance(snapshot, dict):
        snapshot = {}

    strategy_spec = load_strategy_spec(run_root)
    completed_step = _infer_completed_step(run_root, before_artifacts)

    metrics_path = run_root / "artifacts" / "metrics.json"
    has_metrics = metrics_path.exists()
    if pf is None and not has_metrics:
        return {
            "success": False,
            "error": "No portfolio `pf` in namespace and no artifacts/metrics.json written.",
            "log_path": _portable_path(log_path),
            "code_path": _portable_path(script),
            "validation": validation,
        }

    try:
        from .selection import after_execution

        after_execution(
            run_root,
            run_id=state.run_id,
            script=script.name,
            completed_step=completed_step,
            namespace=namespace,
        )
    except Exception:
        pass
    artifacts = _collect_artifacts(run_root)

    feedback: dict[str, Any] = {
        "success": True,
        "log_path": _portable_path(log_path),
        "code_path": _portable_path(script),
        "artifacts": artifacts,
        "validation_passed": bool(validation.get("approved")) if validation else True,
        "strategy_snapshot": snapshot,
        "has_pf": pf is not None,
    }
    if strategy_spec:
        feedback["strategy_spec"] = strategy_spec
    if completed_step:
        feedback["completed_step"] = completed_step
    if has_metrics:
        try:
            feedback["metrics"] = json.loads(metrics_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    return feedback
