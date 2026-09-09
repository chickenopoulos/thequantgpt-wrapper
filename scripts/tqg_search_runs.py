#!/usr/bin/env python3
"""Search the cross-run lab memory index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.lab_index import (  # noqa: E402
    format_cards_table,
    load_index,
    rebuild_index,
    search_runs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Query runs/_lab/index.json")
    parser.add_argument("--symbol")
    parser.add_argument("--asset-class")
    parser.add_argument("--workflow")
    parser.add_argument("--strategy-type")
    parser.add_argument("--status")
    parser.add_argument(
        "--validation-passed",
        choices=["true", "false"],
        help="Filter by validation_passed",
    )
    parser.add_argument("--verdict")
    parser.add_argument("--tag")
    parser.add_argument("--text", help="Substring search over title/hypothesis/report/flow")
    parser.add_argument("--related-to", help="Runs linked to this run_id")
    parser.add_argument("--since", help="ISO date/time lower bound on created_at")
    parser.add_argument("--until", help="ISO date/time upper bound on created_at")
    parser.add_argument("--is-sharpe-gt", type=float)
    parser.add_argument("--is-sharpe-lt", type=float)
    parser.add_argument("--oos-sharpe-gt", type=float)
    parser.add_argument("--oos-sharpe-lt", type=float)
    parser.add_argument("--n-trials-gte", type=int, help="Minimum this-run trial count N")
    parser.add_argument("--dsr-lt", type=float)
    parser.add_argument("--dsr-gt", type=float)
    parser.add_argument("--fingerprint-match", help="Exact params_fingerprint string")
    parser.add_argument(
        "--fingerprint-of",
        help="Find runs with the same params_fingerprint as this run_id (excludes self)",
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument(
        "--rebuild-if-missing",
        action="store_true",
        help="Rebuild index when runs/_lab/index.json is absent",
    )
    args = parser.parse_args()

    try:
        index = load_index()
        if args.rebuild_if_missing and not index.get("runs"):
            # Empty index may mean never built — rebuild once.
            from tqg_client.lab_index import index_path

            if not index_path().exists():
                index = rebuild_index()

        validation = None
        if args.validation_passed == "true":
            validation = True
        elif args.validation_passed == "false":
            validation = False

        cards = search_runs(
            symbol=args.symbol,
            asset_class=args.asset_class,
            workflow=args.workflow,
            strategy_type=args.strategy_type,
            status=args.status,
            validation_passed=validation,
            verdict=args.verdict,
            tag=args.tag,
            text=args.text,
            related_to=args.related_to,
            since=args.since,
            until=args.until,
            is_sharpe_gt=args.is_sharpe_gt,
            is_sharpe_lt=args.is_sharpe_lt,
            oos_sharpe_gt=args.oos_sharpe_gt,
            oos_sharpe_lt=args.oos_sharpe_lt,
            n_trials_gte=args.n_trials_gte,
            dsr_lt=args.dsr_lt,
            dsr_gt=args.dsr_gt,
            fingerprint_match=args.fingerprint_match,
            fingerprint_of=args.fingerprint_of,
            limit=args.limit,
            index=index,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"count": len(cards), "runs": cards}, indent=2))
    else:
        print(format_cards_table(cards))
        print(f"\n{len(cards)} run(s)")
        if args.fingerprint_of and cards:
            print(
                f"\nnote: {len(cards)} fingerprint match(es) for {args.fingerprint_of} "
                "(review before re-baselining)",
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
