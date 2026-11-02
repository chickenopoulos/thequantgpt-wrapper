#!/usr/bin/env python3
"""Reproduce MA-type ensemble consensus BTC baseline + frozen cross-asset transfer.

Writes under runs/ma_ensemble_consensus/ (create the run first via tqg_create_run.py).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    run_id = "ma_ensemble_consensus"
    root = REPO / "runs" / run_id
    if not root.exists():
        subprocess.check_call(
            [
                sys.executable,
                str(REPO / "scripts" / "tqg_create_run.py"),
                "--title",
                "MA-type ensemble consensus (BTC + transfer)",
                "--run-id",
                run_id,
            ],
            cwd=str(REPO),
        )
    rc = subprocess.call(
        [sys.executable, str(REPO / "scripts" / "tqg_run_backtest.py"), run_id],
        cwd=str(REPO),
    )
    if rc != 0:
        return rc
    return subprocess.call(
        [
            sys.executable,
            str(REPO / "scripts" / "tqg_run_backtest.py"),
            run_id,
            "--code",
            "code/transfer_battery.py",
            "--no-validate",
        ],
        cwd=str(REPO),
    )


if __name__ == "__main__":
    raise SystemExit(main())
