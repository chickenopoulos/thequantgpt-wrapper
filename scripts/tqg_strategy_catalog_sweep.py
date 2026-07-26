#!/usr/bin/env python3
"""Run all strategy catalog backtests and print results table."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

import re

from tqg_client.strategy_sweep_core import SweepResult, SkipStrategy  # noqa: E402

RUNNERS_A = importlib.import_module("tqg_client.strategy_catalog_runners_a")
RUNNERS_B = importlib.import_module("tqg_client.strategy_catalog_runners_b")


def _all_runners():
    pat = re.compile(r"^run_[A-Z]+_\d+$")
    runners = []
    for mod in (RUNNERS_A, RUNNERS_B):
        for name in dir(mod):
            if not pat.match(name):
                continue
            runners.append(getattr(mod, name))
    return sorted(runners, key=lambda f: f.__name__)


def _safe_run(fn) -> SweepResult:
    try:
        return fn()
    except SkipStrategy as e:
        rid = fn.__name__.replace("run_", "").replace("_", "-")
        return SweepResult(rid, fn.__name__, "—", "—", status="SKIP", note=str(e.reason))
    except Exception as e:
        rid = fn.__name__.replace("run_", "").replace("_", "-")
        return SweepResult(rid, fn.__name__, "—", "—", status="ERROR", note=str(e)[:100])


def format_table(results: list[SweepResult]) -> str:
    lines = [
        "| ID | Strategy | Sharpe | MaxDD | CAGR | Trades | Universe | Asset Class | Status |",
        "|----|----------|--------|-------|------|--------|----------|-------------|--------|",
    ]
    for r in results:
        sharpe = f"{r.sharpe:.2f}" if r.sharpe is not None else "—"
        maxdd = f"{r.max_dd:.1%}" if r.max_dd is not None else "—"
        cagr = f"{r.cagr:.1%}" if r.cagr is not None else "—"
        trades = str(r.trades) if r.trades is not None else "—"
        note = f" ({r.note})" if r.status != "OK" and r.note else ""
        lines.append(
            f"| {r.id} | {r.name} | {sharpe} | {maxdd} | {cagr} | {trades} | {r.universe} | {r.asset_class} | {r.status}{note} |"
        )
    return "\n".join(lines)


def main() -> int:
    results: list[SweepResult] = []
    for fn in _all_runners():
        results.append(_safe_run(fn))

    results.sort(key=lambda r: r.id)
    table = format_table(results)
    out_dir = _REPO / "docs" / "plans"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "strategy-sweep-results.md"
    ok = sum(1 for r in results if r.status == "OK")
    header = f"""# Strategy Catalog Sweep Results

> **Generated:** batch sweep via `scripts/tqg_strategy_catalog_sweep.py`  
> **Note:** Research-only backtests; full history (not OOS-only). Costs: fee 4.5bps + slip 5bps.  
> **OK:** {ok}/{len(results)} strategies executed.

"""
    md_path.write_text(header + table + "\n", encoding="utf-8")
    print(header)
    print(table)
    print(f"\nWrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
