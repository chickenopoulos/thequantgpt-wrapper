#!/usr/bin/env python3
"""Run CSCV / PBO on artifacts/psa_returns_matrix.csv for a lab run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.pbo import load_psa_returns_matrix, maybe_run_pbo, persist_psa_returns_matrix  # noqa: E402
from tqg_client.run_state import load_run_state, run_root_from_state  # noqa: E402
from tqg_client.selection import load_selection, save_selection  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="CSCV probability of backtest overfitting")
    parser.add_argument("run_id", help="runs/<id>")
    parser.add_argument("--matrix", help="Optional CSV path (config columns, period rows)")
    parser.add_argument("--splits", type=int, default=None)
    args = parser.parse_args()

    state = load_run_state(args.run_id)
    run_root = run_root_from_state(state)
    if args.matrix:
        import pandas as pd

        frame = pd.read_csv(args.matrix, index_col=0)
        persist_psa_returns_matrix(run_root, frame.select_dtypes("number"))
    if load_psa_returns_matrix(run_root) is None:
        print(
            json.dumps(
                {
                    "error": "missing_psa_returns_matrix",
                    "hint": "Persist IS period returns per PSA cell via persist_psa_returns_matrix(frame).",
                    "path": "artifacts/psa_returns_matrix.csv",
                },
                indent=2,
            )
        )
        return 1
    result = maybe_run_pbo(run_root)
    sel = load_selection(run_root)
    sel["pbo"] = result
    save_selection(run_root, sel)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result and result.get("pbo") is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
