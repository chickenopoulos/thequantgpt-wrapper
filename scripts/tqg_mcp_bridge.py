#!/usr/bin/env python3
"""Stdio MCP bridge: exposes TheQuantGPT remote API tools to Cursor."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from tqg_client.api import TqgApiClient  # noqa: E402
from tqg_client.config import api_settings, load_config  # noqa: E402

mcp = FastMCP("TheQuantGPT")


def _client() -> TqgApiClient:
    cfg = load_config(_REPO / "config.yaml")
    base_url, api_key = api_settings(cfg)
    return TqgApiClient(base_url, api_key)


def _parse_json(text: str) -> dict | None:
    if not text.strip():
        return None
    data = json.loads(text)
    return data if isinstance(data, dict) else None


@mcp.tool()
def tqg_get_guidance(
    user_request: str,
    run_context_json: str = "",
    code_snippet: str = "",
    last_error: str = "",
    data_summary: str = "",
) -> str:
    """Advisory quant workflow hints for the current request and run context (not a rigid step list)."""
    result = _client().get_guidance(
        user_request=user_request,
        run_context=_parse_json(run_context_json),
        code_snippet=code_snippet,
        last_error=last_error,
        data_summary=data_summary or None,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def tqg_validate_strategy_code(
    code: str,
    user_request: str,
    strategy_spec_json: str = "",
    run_context_json: str = "",
) -> str:
    """Static validation checks before/after running strategy code."""
    result = _client().validate_strategy_code(
        code=code,
        user_request=user_request,
        strategy_spec=_parse_json(strategy_spec_json),
        run_context=_parse_json(run_context_json),
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def tqg_get_robustness_spec(
    user_request: str,
    test_name: str = "",
    run_context_json: str = "",
    parameters_json: str = "[]",
) -> str:
    """Robustness catalog metadata, constraints, and PSA grid hints for one test."""
    params = json.loads(parameters_json) if parameters_json.strip() else []
    result = _client().get_robustness_spec(
        test_name=test_name or None,
        user_request=user_request,
        run_context=_parse_json(run_context_json),
        parameters=params,
    )
    return json.dumps(result, indent=2)


# Legacy aliases
@mcp.tool()
def tqg_create_strategy_plan(
    user_request: str,
    run_id: str,
    run_root: str,
    data_summary: str = "",
) -> str:
    """[Legacy] Prefer tqg_get_guidance. Returns structured planning hints."""
    result = _client().create_strategy_plan(
        user_request=user_request,
        run_id=run_id,
        run_root=run_root,
        data_summary=data_summary or None,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def tqg_get_psa_workflow(
    strategy_type: str,
    parameters_json: str = "[]",
    oos_start: str = "",
) -> str:
    """[Legacy] Prefer tqg_get_robustness_spec(test_name=parameter_sensitivity)."""
    params = json.loads(parameters_json) if parameters_json.strip() else []
    result = _client().get_psa_workflow(
        strategy_type=strategy_type,
        parameters=params,
        oos_start=oos_start or None,
    )
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run()
