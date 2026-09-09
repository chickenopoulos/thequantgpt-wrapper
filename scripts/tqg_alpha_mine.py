#!/usr/bin/env python3
"""Evaluate formulaic alphas on a universe panel (IS ranking; OOS on request)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.alpha_mine import load_formulas_file, run_alpha_mine  # noqa: E402
from tqg_client.alpha_ops import catalog_payload  # noqa: E402
from tqg_client.lab_index import touch_run_index  # noqa: E402
from tqg_client.selection import load_selection  # noqa: E402


def _csv_list(raw: str | None) -> list[str] | None:
    if raw is None or not str(raw).strip():
        return None
    return [p.strip() for p in str(raw).split(",") if p.strip()]


def _int_list(raw: str | None) -> list[int] | None:
    parts = _csv_list(raw)
    if not parts:
        return None
    return [int(p) for p in parts]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mine formulaic alphas on a panel. Rank on IS Rank IC; pass --reveal-oos only when fishing stops."
    )
    parser.add_argument("run_id", help="Existing runs/<id>/ folder")
    parser.add_argument("--panel", help="Long-format OHLCV parquet/CSV with an asset column")
    parser.add_argument("--formulas", help="JSON list of {id, expr, description} or {formulas: [...]}")
    parser.add_argument("--seeds", help="Comma-separated packs: leftover,volume,wick,momentum")
    parser.add_argument("--drop", help="Comma-separated alpha ids to drop")
    parser.add_argument("--keep", help="Comma-separated alpha ids to keep (others dropped)")
    parser.add_argument("--neutralize", action="store_true", help="Wrap active formulas in cs_demean(...)")
    parser.add_argument("--mutate", help="Alpha id whose last integer window is mutated")
    parser.add_argument("--windows", default="10,20,40", help="Mutation windows (default 10,20,40)")
    parser.add_argument("--book", help="Comma-separated ids to combine into a k-leg book")
    parser.add_argument(
        "--reveal-oos",
        action="store_true",
        help="Write OOS metrics. Do not use this to pick winners.",
    )
    parser.add_argument("--top-n", type=int, default=50, help="Keep N most liquid names on IS (default 50)")
    parser.add_argument("--min-bars", type=int, default=60)
    parser.add_argument("--oos", help="OOS start (default from run.json / 2025-01-01)")
    parser.add_argument("--asset-class", help="equity|crypto|... for annualization")
    parser.add_argument("--catalog", action="store_true", help="Print the operator catalog and exit")
    args = parser.parse_args()

    if args.catalog:
        print(json.dumps(catalog_payload(), indent=2))
        return 0

    formulas = load_formulas_file(Path(args.formulas)) if args.formulas else None
    try:
        result = run_alpha_mine(
            args.run_id,
            panel_path=args.panel,
            formulas=formulas,
            packs=_csv_list(args.seeds),
            drop_ids=_csv_list(args.drop),
            keep_ids=_csv_list(args.keep),
            neutralize=args.neutralize,
            mutate_id=args.mutate,
            windows=_int_list(args.windows) if args.mutate else None,
            book_ids=_csv_list(args.book),
            reveal_oos=args.reveal_oos,
            top_n=args.top_n,
            min_bars=args.min_bars,
            asset_class=args.asset_class,
            oos_start=args.oos,
        )
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    touch_run_index(args.run_id)
    sel = load_selection(_REPO / "runs" / args.run_id)
    payload = {
        "run_id": args.run_id,
        "n_assets": result["n_assets"],
        "n_new_formulas": result["n_new_formulas"],
        "oos_revealed": result["oos_revealed"],
        "n_trials": sel.get("n_trials"),
        "n_legs": sel.get("n_legs"),
        "dsr": (sel.get("dsr") or {}).get("dsr") if isinstance(sel.get("dsr"), dict) else None,
        "leaderboard": result["leaderboard"],
        "alphas_path": f"runs/{args.run_id}/artifacts/alphas.json",
        "selection_path": f"runs/{args.run_id}/artifacts/selection.json",
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
