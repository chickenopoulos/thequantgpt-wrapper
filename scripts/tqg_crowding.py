#!/usr/bin/env python3
"""Pairwise IS-return crowding for same-symbol lab runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.crowding import crowding_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Same-symbol IS return crowding")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--runs-dir", type=Path)
    parser.add_argument("--limit", type=int, default=24)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = crowding_report(symbol=args.symbol, runs_dir=args.runs_dir, limit=args.limit)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        mean = report.get("mean_pairwise_corr")
        print(f"symbol={report.get('symbol')} runs={report.get('n_runs_with_returns')} pairs={report.get('n_pairs')}")
        print(f"mean pairwise corr: {mean}")
        for pair in report.get("pairs") or []:
            print(f"  {pair['a']} vs {pair['b']}: {pair['corr']:.3f} (n={pair['n_overlap']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
