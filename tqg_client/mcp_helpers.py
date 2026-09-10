"""Helpers for MCP tool calls from local run folders."""

from __future__ import annotations

from tqg_client.lab_index import lab_context_for_mcp as _lab_context_for_mcp
from tqg_client.run_state import load_run_state

__all__ = ["run_context_for_mcp", "lab_context_for_mcp"]


def run_context_for_mcp(run_id: str) -> dict:
    """Load runs/<id>/run.json as MCP run_context payload."""
    return load_run_state(run_id).to_dict()


def lab_context_for_mcp(
    *,
    symbol: str | None = None,
    limit: int = 8,
    include_lessons: bool = True,
    **kwargs,
) -> dict:
    """Prior-run cards plus a lesson brief (blockers + process notes)."""
    ctx = _lab_context_for_mcp(symbol=symbol, limit=limit, **kwargs)
    if include_lessons:
        from tqg_client.lessons import lesson_brief

        ctx["lessons_brief"] = lesson_brief(symbol=symbol, limit=min(8, limit or 8))
    return ctx
