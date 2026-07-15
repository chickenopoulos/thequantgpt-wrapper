"""Helpers for MCP tool calls from local run folders."""

from __future__ import annotations

from tqg_client.run_state import load_run_state


def run_context_for_mcp(run_id: str) -> dict:
    """Load runs/<id>/run.json as MCP run_context payload."""
    return load_run_state(run_id).to_dict()
