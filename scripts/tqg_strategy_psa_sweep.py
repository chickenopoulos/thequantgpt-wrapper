#!/usr/bin/env python3
"""Run PSA across strategy catalog; output stable-plateau table ranked by representative Sharpe."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.strategy_psa_core import PsaResult, run_psa  # noqa: E402
from tqg_client.strategy_psa_registry import all_psa_specs  # noqa: E402


def _fmt_params(params: dict | None) -> str:
    if not params:
        return "—"
    return ", ".join(f"{k}={v}" for k, v in sorted(params.items()))


def format_stable_table(results: list[PsaResult]) -> str:
    stable = [r for r in results if r.status == "STABLE"]
    stable.sort(key=lambda r: r.rep_sharpe or -999, reverse=True)

    lines = [
        "| Rank | ID | Strategy | Rep Sharpe | Rep PF | Rep Trades | Stable Cells | Rep Params | Universe | Asset Class |",
        "|------|-----|----------|------------|--------|------------|--------------|------------|----------|-------------|",
    ]
    for i, r in enumerate(stable, 1):
        sharpe = f"{r.rep_sharpe:.2f}" if r.rep_sharpe is not None else "—"
        pf = f"{r.rep_pf:.2f}" if r.rep_pf is not None else "—"
        trades = f"{int(r.rep_trades)}" if r.rep_trades is not None else "—"
        cells = f"{r.stable_cells}/{r.grid_cells}"
        lines.append(
            f"| {i} | {r.id} | {r.name} | {sharpe} | {pf} | {trades} | {cells} | {_fmt_params(r.rep_params)} | {r.universe} | {r.asset_class} |"
        )
    return "\n".join(lines)


def format_summary(results: list[PsaResult]) -> str:
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    parts = [f"{k}: {v}" for k, v in sorted(counts.items())]
    return ", ".join(parts)


def main() -> int:
    specs = all_psa_specs()
    results: list[PsaResult] = []
    total = len(specs)
    for i, spec in enumerate(specs, 1):
        print(f"[{i}/{total}] PSA {spec.id}...", flush=True)
        results.append(run_psa(spec))

    stable_n = sum(1 for r in results if r.status == "STABLE")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = f"""# Strategy PSA — Stable Plateau Results

> **Generated:** {now} via `scripts/tqg_strategy_psa_sweep.py`  
> **Sample:** in-sample only (before 2025-01-01)  
> **Stable criteria:** Sharpe ≥ baseline − 0.05, PF ≥ 1.2, trades ≥ spec min; ≥3 stable cells (2 for rare-event specs)  
> **Rep Sharpe:** plateau center (score = Sharpe + 0.25×PF), not grid peak  
> **Summary:** {format_summary(results)} — **{stable_n}** strategies with stable regions

"""
    table = format_stable_table(results)
    out_dir = _REPO / "docs" / "plans"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "strategy-psa-stable-results.md"
    md_path.write_text(header + table + "\n", encoding="utf-8")

    print()
    print(header)
    print(table)
    print(f"\nWrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
