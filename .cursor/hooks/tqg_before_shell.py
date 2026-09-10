#!/usr/bin/env python3
"""beforeShellExecution: one robustness test per tick; no unvalidated package."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WRAPPER = Path("/root/thequantgpt-wrapper")
ROBUST_MARKERS = (
    "code/psa",
    "code/cea",
    "code/mc",
    "monte_carlo",
    "cost_stress",
    "signal_shift",
    "code/psa.py",
    "code/cea.py",
)


def _deny(message: str) -> dict:
    return {
        "permission": "deny",
        "user_message": message,
        "agent_message": message,
    }


def _allow() -> dict:
    return {"permission": "allow"}


def _active_tick() -> dict:
    path = WRAPPER / "runs" / "_lab" / "active_tick.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _run_validation_passed(run_id: str) -> bool | None:
    path = WRAPPER / "runs" / run_id / "run.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return bool(data.get("validation_passed"))


def decide(command: str) -> dict:
    cmd = command or ""
    low = cmd.lower()

    robust_hits = [m for m in ROBUST_MARKERS if m in low]
    # Unique families (psa.py and code/psa both count as psa)
    families = set()
    for hit in robust_hits:
        if "psa" in hit:
            families.add("psa")
        elif "cea" in hit or "cost_stress" in hit:
            families.add("cea")
        elif "mc" in hit or "monte" in hit:
            families.add("mc")
        elif "signal_shift" in hit:
            families.add("shift")
    if len(families) >= 2:
        return _deny("Lab hook: one robustness test per tick — do not batch PSA/CEA/MC.")

    active = _active_tick()
    if active.get("robustness_this_tick") and families:
        return _deny(
            "Lab hook: this research-loop tick already consumed its robustness test."
        )

    if "tqg_package_artifacts.py" in low:
        match = re.search(r"tqg_package_artifacts\.py\s+([A-Za-z0-9_-]+)", cmd)
        run_id = match.group(1) if match else None
        if run_id:
            passed = _run_validation_passed(run_id)
            if passed is False:
                return _deny(
                    f"Lab hook: refuse package of {run_id} — validation_passed is false."
                )
        if active:
            return _deny("Lab hook: the research loop is not allowed to package.")

    return _allow()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps(_allow()))
        return 0
    command = ""
    if isinstance(payload, dict):
        command = str(payload.get("command") or payload.get("commandLine") or "")
    print(json.dumps(decide(command)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
