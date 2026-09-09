#!/usr/bin/env python3
"""Build an (N, k) manufacturing surface on a zero-mean return stream."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.manufacturing import lookup_cell, manufacturing_surface  # noqa: E402
from tqg_client.selection import load_is_returns, load_selection  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Empirical top-k-of-N manufacturing surface")
    parser.add_argument("run_id", nargs="?", help="Optional run to read IS returns / write surface")
    parser.add_argument("--runs-dir", type=Path, default=_REPO / "runs")
    parser.add_argument("--n-pool", type=int, default=400)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--annualization", type=float, default=365)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.run_id:
        print("error: pass a run_id that has artifacts/returns_is.json", file=sys.stderr)
        return 1
    root = args.runs_dir / args.run_id
    rets = load_is_returns(root)
    if rets is None:
        print(f"error: missing {root / 'artifacts' / 'returns_is.json'}", file=sys.stderr)
        return 1
    surface = manufacturing_surface(
        rets,
        n_pool=args.n_pool,
        seed=args.seed,
        annualization=args.annualization,
    )
    sel = load_selection(root)
    n = int(sel.get("n_trials") or 0)
    k = int(sel.get("n_legs") or 1)
    surface["lookup_at_operating_point"] = {
        "n_trials": n,
        "n_legs": k,
        "manufactured_sharpe": lookup_cell(surface, n, k),
    }
    out_path = root / "artifacts" / "manufacturing_surface.json"
    out_path.write_text(json.dumps(surface, indent=2) + "\n", encoding="utf-8")
    sel["manufacturing"] = {
        "path": "artifacts/manufacturing_surface.json",
        "lookup_at_operating_point": surface["lookup_at_operating_point"],
        "note": surface.get("note"),
    }
    from tqg_client.selection import save_selection

    save_selection(root, sel)
    if args.json:
        print(json.dumps(surface["lookup_at_operating_point"], indent=2))
    else:
        print(out_path)
        point = surface["lookup_at_operating_point"]
        print(
            f"operating (N={n}, k={k}) manufactured IS Sharpe ≈ {point.get('manufactured_sharpe')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
