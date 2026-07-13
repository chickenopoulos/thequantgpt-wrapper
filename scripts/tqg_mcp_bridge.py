#!/usr/bin/env python3
"""Stdio MCP bridge: exposes TheQuantGPT remote API tools to Cursor."""

from __future__ import annotations

import json
import os
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


@mcp.tool()
def tqg_create_strategy_plan(
    user_request: str,
    run_id: str,
    run_root: str,
    data_summary: str = "",
) -> str:
    """Return a structured strategy plan: files, steps, validation checks, artifacts."""
    result = _client().create_strategy_plan(
        user_request=user_request,
        run_id=run_id,
        run_root=run_root,
        data_summary=data_summary or None,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def tqg_validate_strategy_code(
    code: str,
    user_request: str,
    strategy_spec_json: str = "",
) -> str:
    """Static validation checks before/after running strategy code."""
    spec = json.loads(strategy_spec_json) if strategy_spec_json.strip() else None
    result = _client().validate_strategy_code(
        code=code,
        user_request=user_request,
        strategy_spec=spec,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
def tqg_get_psa_workflow(
    strategy_type: str,
    parameters_json: str = "[]",
    oos_start: str = "",
) -> str:
    """Parameter sensitivity workflow from the robustness catalog."""
    params = json.loads(parameters_json) if parameters_json.strip() else []
    result = _client().get_psa_workflow(
        strategy_type=strategy_type,
        parameters=params,
        oos_start=oos_start or None,
    )
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run()
