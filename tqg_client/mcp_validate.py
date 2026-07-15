"""MCP validation helpers for local scripts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .api import TqgApiClient, TqgApiError
from .config import api_settings, load_config
from .run_state import RunState, load_strategy_spec, run_root_from_state, save_run_state


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mcp_validate_code(
    state: RunState,
    *,
    code_path: Path | None = None,
    user_request: str = "",
) -> dict[str, Any]:
    """Call remote tqg_validate_strategy_code for a run's strategy code."""
    run_root = run_root_from_state(state)
    if code_path is None:
        code_dir = run_root / "code"
        py_files = sorted(code_dir.glob("*.py"))
        if not py_files:
            raise FileNotFoundError(f"No Python files under {code_dir}")
        code_path = py_files[0]
    code = code_path.read_text(encoding="utf-8")
    cfg = load_config()
    base_url, api_key = api_settings(cfg)
    client = TqgApiClient(base_url, api_key)
    return client.validate_strategy_code(
        code=code,
        user_request=user_request,
        strategy_spec=load_strategy_spec(run_root),
        run_context=state.to_dict(),
    )


def apply_mcp_validation(state: RunState, review: dict[str, Any]) -> RunState:
    state.validation_passed = bool(review.get("approved"))
    if state.validation_passed:
        state.last_validation_at = _utc_now()
    else:
        issues = review.get("issues") or []
        state.last_error = "; ".join(str(i) for i in issues[:3]) if issues else "MCP validation failed"
    return state


def try_mcp_validate(
    state: RunState,
    *,
    code_path: Path | None = None,
    user_request: str = "",
    persist: bool = True,
) -> dict[str, Any]:
    try:
        review = mcp_validate_code(state, code_path=code_path, user_request=user_request)
    except TqgApiError as exc:
        review = {"approved": False, "issues": [str(exc)], "source": "mcp_unreachable"}
    state = apply_mcp_validation(state, review)
    if persist:
        save_run_state(state)
    return review
