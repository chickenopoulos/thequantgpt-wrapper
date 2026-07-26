#!/usr/bin/env python3
"""Ensemble catalog strategy signals per traded asset and report performance."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.strategy_ensemble import (  # noqa: E402
    capture_all_strategies,
    format_ensemble_table,
    format_strategy_lists,
    run_asset_ensembles,
)


def main() -> int:
    print("Capturing individual strategy positions...", flush=True)
    captured = capture_all_strategies()
    print(f"Captured {len(captured)} strategies with position series.", flush=True)

    results = run_asset_ensembles(captured)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = f"""# Strategy Catalog — Per-Asset Ensemble Results

> **Generated:** {now} via `scripts/tqg_strategy_ensemble_sweep.py`  
> **Method:** equal-weight mean of daily positions (−1…+1), clipped, across catalog strategies trading the same asset  
> **Costs:** fee 4.5bps + slip 5bps on position changes  
> **Ensembles:** {len(results)} assets with ≥2 strategies

"""
    table = format_ensemble_table(results)
    detail = format_strategy_lists(results)
    out = _REPO / "docs" / "plans" / "strategy-ensemble-results.md"
    out.write_text(header + table + "\n\n" + detail, encoding="utf-8")

    print()
    print(header)
    print(table)
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
