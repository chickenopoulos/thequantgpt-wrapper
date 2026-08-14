#!/usr/bin/env python3
"""Smoke tests for cross-run lab memory."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.lab_index import (  # noqa: E402
    extract_run_card,
    lab_context_for_mcp,
    list_run_ids,
    params_fingerprint,
    rebuild_index,
    search_runs,
    upsert_run,
)


def test_list_and_extract_triangular() -> None:
    ids = list_run_ids()
    assert "triangular_pairs" in ids, ids
    card = extract_run_card("triangular_pairs")
    assert card["run_id"] == "triangular_pairs"
    assert card["symbol"] == "UNIVERSE"
    assert card["workflow"] == "multi_asset_triangular_pairs"
    assert card["strategy_type"] == "MEAN_REVERSION"
    assert card["metrics"]["out_of_sample"]["Sharpe"] > 1.0
    assert "n_triangles=10" in card["params_fingerprint"]
    assert card["paths"]["root"] == "runs/triangular_pairs"


def test_rebuild_and_search() -> None:
    index = rebuild_index()
    assert len(index["runs"]) >= 1
    assert "triangular_pairs" in index["runs"]

    qqq = search_runs(symbol="QQQ")
    assert any(c["run_id"] == "qqq_pullback_reversal" for c in qqq), qqq

    weak = search_runs(oos_sharpe_lt=0.2)
    assert any(c["run_id"] == "demo_btc_mr" for c in weak), [c["run_id"] for c in weak]

    text_hits = search_runs(text="pullback")
    assert any("pullback" in (c.get("run_id") or "") or "pullback" in (c.get("title") or "").lower() for c in text_hits)


def test_fingerprint_stable() -> None:
    a = params_fingerprint(
        workflow="w",
        strategy_type="MEAN_REVERSION",
        symbol="QQQ",
        interval="1d",
        params={"b": 2, "a": 1},
    )
    b = params_fingerprint(
        workflow="w",
        strategy_type="MEAN_REVERSION",
        symbol="QQQ",
        interval="1d",
        params={"a": 1, "b": 2},
    )
    assert a == b
    assert a.startswith("w|MEAN_REVERSION|QQQ|1d|")


def test_lab_context() -> None:
    rebuild_index()
    ctx = lab_context_for_mcp(symbol="QQQ", limit=5)
    assert "prior_runs" in ctx
    assert ctx["run_count"] >= 1
    assert any(r.get("symbol") == "QQQ" for r in ctx["prior_runs"])


def test_isolated_tmp_index() -> None:
    """Card extract works against a temp runs dir without polluting real index."""
    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp) / "runs"
        rid = "toy"
        root = runs / rid
        root.mkdir(parents=True)
        (root / "artifacts").mkdir()
        (root / "run.json").write_text(
            json.dumps(
                {
                    "run_id": rid,
                    "title": "Toy",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "root": f"runs/{rid}",
                    "status": "created",
                    "symbol": "SPY",
                    "workflow": "single_asset_signals",
                    "strategy_type": "MOMENTUM",
                    "validation_passed": False,
                    "completed_steps": [],
                    "defaults": {"interval": "1d"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "strategy_spec.json").write_text(
            json.dumps(
                {
                    "workflow": "single_asset_signals",
                    "strategy_type": "MOMENTUM",
                    "symbol": "SPY",
                    "asset_class": "equity",
                    "interval": "1d",
                    "params": {"lookback": 20},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        card = upsert_run(rid, runs_dir=runs)
        assert card["symbol"] == "SPY"
        assert card["asset_class"] == "equity"
        hits = search_runs(symbol="SPY", runs_dir=runs)
        assert len(hits) == 1


def main() -> int:
    tests = [
        test_fingerprint_stable,
        test_list_and_extract_triangular,
        test_rebuild_and_search,
        test_lab_context,
        test_isolated_tmp_index,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"ok  {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}", file=sys.stderr)
    if failed:
        print(f"{failed} failed", file=sys.stderr)
        return 1
    print(f"{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
