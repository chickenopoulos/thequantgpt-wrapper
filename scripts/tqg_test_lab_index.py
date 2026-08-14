#!/usr/bin/env python3
"""Smoke tests for cross-run lab memory (self-contained temp fixtures)."""

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

_CFG = {"defaults": {"interval": "1d"}}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _make_run(
    runs: Path,
    run_id: str,
    *,
    symbol: str,
    title: str,
    workflow: str = "single_asset_signals",
    strategy_type: str = "MEAN_REVERSION",
    asset_class: str = "crypto",
    oos_sharpe: float = 0.1,
    params: dict | None = None,
    hypothesis: str | None = None,
) -> Path:
    root = runs / run_id
    (root / "artifacts").mkdir(parents=True)
    _write_json(
        root / "run.json",
        {
            "run_id": run_id,
            "title": title,
            "created_at": "2026-01-01T00:00:00+00:00",
            "root": f"runs/{run_id}",
            "status": "completed",
            "symbol": symbol,
            "workflow": workflow,
            "strategy_type": strategy_type,
            "validation_passed": True,
            "completed_steps": ["baseline"],
            "defaults": {"interval": "1d"},
        },
    )
    _write_json(
        root / "strategy_spec.json",
        {
            "workflow": workflow,
            "strategy_type": strategy_type,
            "symbol": symbol,
            "asset_class": asset_class,
            "interval": "1d",
            "params": params or {"lookback": 20},
        },
    )
    _write_json(
        root / "artifacts" / "metrics.json",
        {
            "in_sample": {"Sharpe": 0.4, "CAGR": 0.1, "MaxDD": -0.2},
            "out_of_sample": {"Sharpe": oos_sharpe, "CAGR": 0.02, "MaxDD": -0.1},
        },
    )
    if hypothesis:
        (root / "report.md").write_text(f"# {title}\n\n{hypothesis}\n", encoding="utf-8")
    return root


def test_list_and_extract() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp) / "runs"
        _make_run(
            runs,
            "btc_mr",
            symbol="BTCUSDT",
            title="BTC mean reversion",
            params={"z_window": 30, "ma_window": 90},
        )
        ids = list_run_ids(cfg=_CFG, runs_dir=runs)
        assert ids == ["btc_mr"], ids
        card = extract_run_card("btc_mr", cfg=_CFG, runs_dir=runs)
        assert card["run_id"] == "btc_mr"
        assert card["symbol"] == "BTCUSDT"
        assert card["workflow"] == "single_asset_signals"
        assert card["strategy_type"] == "MEAN_REVERSION"
        assert card["paths"]["root"] == "runs/btc_mr"
        assert "z_window=30" in card["params_fingerprint"]


def test_rebuild_and_search() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp) / "runs"
        _make_run(
            runs,
            "btc_mr",
            symbol="BTCUSDT",
            title="BTC mean reversion",
            oos_sharpe=0.05,
        )
        _make_run(
            runs,
            "qqq_pullback",
            symbol="QQQ",
            title="QQQ pullback reversal",
            asset_class="equity",
            oos_sharpe=1.2,
            hypothesis="Pullback reversal on QQQ.",
        )
        index = rebuild_index(cfg=_CFG, runs_dir=runs)
        assert set(index["runs"]) == {"btc_mr", "qqq_pullback"}

        qqq = search_runs(symbol="QQQ", cfg=_CFG, runs_dir=runs)
        assert [c["run_id"] for c in qqq] == ["qqq_pullback"], qqq

        weak = search_runs(oos_sharpe_lt=0.2, cfg=_CFG, runs_dir=runs)
        assert [c["run_id"] for c in weak] == ["btc_mr"], [c["run_id"] for c in weak]

        text_hits = search_runs(text="pullback", cfg=_CFG, runs_dir=runs)
        assert any(c["run_id"] == "qqq_pullback" for c in text_hits), text_hits


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
    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp) / "runs"
        _make_run(runs, "qqq_a", symbol="QQQ", title="QQQ A", asset_class="equity")
        rebuild_index(cfg=_CFG, runs_dir=runs)
        ctx = lab_context_for_mcp(symbol="QQQ", limit=5, cfg=_CFG, runs_dir=runs)
        assert "prior_runs" in ctx
        assert ctx["run_count"] >= 1
        assert any(r.get("symbol") == "QQQ" for r in ctx["prior_runs"])


def test_isolated_tmp_index() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp) / "runs"
        _make_run(
            runs,
            "toy",
            symbol="SPY",
            title="Toy",
            strategy_type="MOMENTUM",
            asset_class="equity",
            params={"lookback": 20},
        )
        card = upsert_run("toy", cfg=_CFG, runs_dir=runs)
        assert card["symbol"] == "SPY"
        assert card["asset_class"] == "equity"
        hits = search_runs(symbol="SPY", cfg=_CFG, runs_dir=runs)
        assert len(hits) == 1


def main() -> int:
    tests = [
        test_fingerprint_stable,
        test_list_and_extract,
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
