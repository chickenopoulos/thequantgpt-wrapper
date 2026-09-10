#!/usr/bin/env python3
"""Supervised TQG research loop: charter + one-action ticks.

Does not package. Does not batch robustness tests. Does not clone OOS winners.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.lessons import active_tick_path, programs_dir  # noqa: E402
from tqg_client.research_policy import (  # noqa: E402
    default_charter,
    default_state,
    next_action,
    tick_prompt,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _program_paths(program_id: str) -> tuple[Path, Path, Path]:
    root = programs_dir() / program_id
    return root / "charter.json", root / "state.json", root / "tick_log.jsonl"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _append_log(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def cmd_init(args: argparse.Namespace) -> int:
    symbols = [s.strip() for s in args.symbol.split(",") if s.strip()]
    if not symbols:
        print("error: --symbol is required", file=sys.stderr)
        return 1
    charter = default_charter(
        args.program,
        symbols=symbols,
        max_ticks=args.max_ticks,
        max_new_runs=args.max_new_runs,
        title=args.title or args.program,
        include_catalog=args.include_catalog,
    )
    if args.idea:
        charter["hypothesis_queue"] = [{"title": args.idea, "idea": args.idea}]
    charter_path, state_path, _log = _program_paths(args.program)
    charter_path.parent.mkdir(parents=True, exist_ok=True)
    if charter_path.exists() and not args.force:
        print(f"error: charter exists {charter_path} (pass --force)", file=sys.stderr)
        return 1
    _write_json(charter_path, charter)
    _write_json(state_path, default_state())
    print(json.dumps({"charter": str(charter_path), "state": str(state_path)}, indent=2))
    return 0


def _load_program(program_id: str) -> tuple[dict, dict, Path]:
    charter_path, state_path, log_path = _program_paths(program_id)
    if not charter_path.is_file():
        raise FileNotFoundError(
            f"missing charter {charter_path}; run "
            f"python scripts/tqg_research_loop.py init --program {program_id} --symbol ..."
        )
    charter = _load_json(charter_path)
    state = _load_json(state_path) if state_path.is_file() else default_state()
    return charter, state, log_path


def cmd_status(args: argparse.Namespace) -> int:
    charter, state, log_path = _load_program(args.program)
    decision = next_action(charter, state)
    payload = {
        "charter": {k: charter.get(k) for k in ("program_id", "title", "universe", "budgets", "status")},
        "state": state,
        "next": decision,
        "tick_log": str(log_path),
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_tick(args: argparse.Namespace) -> int:
    charter, state, log_path = _load_program(args.program)
    decision = next_action(
        charter,
        state,
        proposed_fingerprint=args.fingerprint,
        proposed_idea=args.idea,
        proposed_run_id=args.run_id,
    )
    prompt = tick_prompt(decision, charter)
    tick_dir = programs_dir() / args.program
    (tick_dir / "next_tick.md").write_text(prompt + "\n", encoding="utf-8")

    tick_record = {
        "at": _utc_now(),
        "decision": decision,
        "dry_run": bool(args.dry_run),
    }

    if args.dry_run:
        _append_log(log_path, tick_record)
        print(prompt)
        print(f"\n# dry-run; decision={decision.get('action')} halt={decision.get('halt_reason')}")
        return 0

    state["ticks_used"] = int(state.get("ticks_used") or 0) + 1
    state["last_action"] = decision.get("action")
    state["active_run_id"] = decision.get("run_id") or state.get("active_run_id")
    state["robustness_this_tick"] = decision.get("action") == "one_robustness"
    if decision.get("action") == "halt":
        state["halt_reason"] = decision.get("halt_reason")
        charter["status"] = "halted"
    if decision.get("action") == "baseline" and not decision.get("run_id"):
        state["new_runs"] = int(state.get("new_runs") or 0) + 1
    state["updated_at"] = _utc_now()

    active = {
        "program_id": args.program,
        "action": decision.get("action"),
        "run_id": decision.get("run_id"),
        "robustness_this_tick": bool(state.get("robustness_this_tick")),
        "started_at": _utc_now(),
    }
    _write_json(active_tick_path(), active)
    _write_json(_program_paths(args.program)[0], charter)
    _write_json(_program_paths(args.program)[1], state)
    _append_log(log_path, {**tick_record, "state": state})

    if args.invoke_agent:
        api_key = os.environ.get("CURSOR_API_KEY", "").strip()
        if not api_key:
            print("error: --invoke-agent requires CURSOR_API_KEY", file=sys.stderr)
            return 1
        try:
            from cursor_sdk import Agent, AgentOptions, LocalAgentOptions
        except ImportError:
            print("error: cursor_sdk is not installed", file=sys.stderr)
            return 1
        result = Agent.prompt(
            prompt,
            AgentOptions(
                api_key=api_key,
                local=LocalAgentOptions(cwd=str(_REPO)),
            ),
        )
        print(getattr(result, "result", result))
        return 0

    print(prompt)
    print(
        f"\n# tick recorded action={decision.get('action')} "
        f"halt={decision.get('halt_reason')} log={log_path}"
    )
    print("# Follow the prompt in this Cursor session (skill tqg-research-tick), then re-run status.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TQG lab research loop (one action per tick)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Create a program charter")
    p_init.add_argument("--program", required=True)
    p_init.add_argument("--symbol", required=True, help="Comma-separated symbols")
    p_init.add_argument("--title")
    p_init.add_argument("--max-ticks", type=int, default=8)
    p_init.add_argument("--max-new-runs", type=int, default=2)
    p_init.add_argument("--idea", help="Optional hypothesis to queue (not an OOS clone)")
    p_init.add_argument("--include-catalog", action="store_true")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_status = sub.add_parser("status", help="Show charter, budgets, and next_action")
    p_status.add_argument("--program", required=True)
    p_status.set_defaults(func=cmd_status)

    p_tick = sub.add_parser("tick", help="Compute one action and write next_tick.md")
    p_tick.add_argument("--program", required=True)
    p_tick.add_argument("--dry-run", action="store_true")
    p_tick.add_argument("--invoke-agent", action="store_true", help="Call local Cursor SDK if installed")
    p_tick.add_argument("--fingerprint", help="Proposed params fingerprint to check against kills")
    p_tick.add_argument("--idea", help="Proposed idea text (OOS-leak check)")
    p_tick.add_argument("--run-id", help="Force the active run")
    p_tick.set_defaults(func=cmd_tick)

    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
