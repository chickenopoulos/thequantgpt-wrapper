#!/usr/bin/env python3
"""Extract structured lessons from the lab index, reports, and catalog CSV."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.lesson_extract import (  # noqa: E402
    apply_catalog_tags,
    extract_all_lessons,
    link_known_families,
)
from tqg_client.lessons import load_lessons, merge_lessons, save_lessons  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build runs/_lab/lessons from indexed runs")
    parser.add_argument("--merge", action="store_true", help="Merge into existing corpus (default: replace run/catalog rows)")
    parser.add_argument("--apply-catalog-tags", action="store_true", help="Tag catalog_* runs from catalog CSV")
    parser.add_argument("--link-families", action="store_true", help="Link known related_runs families")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    hygiene: dict = {}
    if args.apply_catalog_tags:
        hygiene["catalog_tags"] = apply_catalog_tags(write=True)
    if args.link_families:
        hygiene["families"] = link_known_families(write=True)

    incoming = extract_all_lessons(include_catalog=True)
    if args.merge:
        # Keep transcript/manual lessons; replace run/catalog by rebuilding those sources
        existing = [
            row
            for row in load_lessons()
            if row.get("source") in {"transcript", "manual", "policy"}
        ]
        meta = save_lessons(existing + incoming)
    else:
        meta = merge_lessons(incoming, replace=True)

    payload = {"meta": meta, "hygiene": hygiene, "extracted": len(incoming)}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"lessons: {meta.get('lesson_count')} (dropped {meta.get('dropped')})")
        if hygiene:
            print(json.dumps(hygiene, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
