#!/usr/bin/env python3
"""Tests for N/k selection log, DSR, null baseline, and Phase 3 helpers."""

from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.cs_shuffle import label_shuffle_cs  # noqa: E402
from tqg_client.lab_index import extract_run_card, rebuild_index, search_runs  # noqa: E402
from tqg_client.manufacturing import lookup_cell, manufacturing_surface  # noqa: E402
from tqg_client.novy_marx import combination_multiplier, novy_marx_note  # noqa: E402
from tqg_client.null_baseline import random_entry_matched_hold  # noqa: E402
from tqg_client.selection import (  # noqa: E402
    _norm_cdf,
    _norm_ppf,
    after_execution,
    count_legs,
    deflated_sharpe,
    detect_grid_from_obj,
    expected_max_sharpe,
    family_n,
    load_selection,
    persist_is_returns,
    probabilistic_sharpe,
    record_event,
    seed_selection,
    sharpe_from_returns,
)


_CFG = {"defaults": {"interval": "1d"}}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_norm_ppf_roundtrip() -> None:
    for p in (0.01, 0.025, 0.5, 0.975, 0.99):
        x = _norm_ppf(p)
        back = _norm_cdf(x)
        assert abs(back - p) < 1e-5, (p, x, back)


def test_dsr_n1_equals_psr_vs_zero() -> None:
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.001, 0.01, size=500))
    dsr = deflated_sharpe(r, n_trials=1, annualization=252)
    sr_period = dsr["sharpe_is"] / math.sqrt(252)
    psr0 = probabilistic_sharpe(sr_period, 0.0, dsr["n_obs"], dsr["skew"], dsr["excess_kurtosis"] + 3.0)
    assert dsr["sr0"] == 0.0
    assert abs(dsr["dsr"] - psr0) < 1e-12
    assert abs(dsr["dsr"] - dsr["psr"]) < 1e-12


def test_dsr_large_n_shrinks() -> None:
    rng = np.random.default_rng(1)
    r = pd.Series(rng.normal(0.001, 0.01, size=500))
    small = deflated_sharpe(r, n_trials=2, annualization=252)
    large = deflated_sharpe(r, n_trials=400, annualization=252)
    assert large["sr0"] > small["sr0"]
    assert large["dsr"] < small["dsr"]
    assert large["dsr"] >= 0.0


def test_expected_max_n1_zero() -> None:
    assert expected_max_sharpe(1, 252, 0.05) == 0.0


def test_count_legs() -> None:
    assert count_legs({})[0] == 1
    k, legs = count_legs({"signals": ["a", "b", "c"]})
    assert k == 3
    assert len(legs) == 3
    k, _ = count_legs({"ensemble_weights": {"x": 0.5, "y": 0.5, "z": 0.0}})
    assert k == 2
    k, _ = count_legs({"ranking": {"sub_scores": ["mom", "value", "quality"]}})
    assert k == 3


def test_counting_baseline_replay_psa_family() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp) / "runs"
        a = runs / "run_a"
        b = runs / "run_b"
        for root, related in ((a, ["run_b"]), (b, [])):
            (root / "artifacts").mkdir(parents=True)
            (root / "code").mkdir(parents=True)
            seed_selection(root)
            _write_json(
                root / "run.json",
                {
                    "run_id": root.name,
                    "title": root.name,
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "root": f"runs/{root.name}",
                    "status": "created",
                    "symbol": "QQQ",
                    "strategy_type": "MEAN_REVERSION",
                    "related_runs": related,
                },
            )
            _write_json(
                root / "strategy_spec.json",
                {
                    "workflow": "single_asset_signals",
                    "strategy_type": "MEAN_REVERSION",
                    "symbol": "QQQ",
                    "interval": "1d",
                    "asset_class": "equity",
                    "params": {"lookback": 20},
                },
            )
            _write_json(
                root / "artifacts" / "metrics.json",
                {"in_sample": {"Sharpe": 0.8}, "out_of_sample": {"Sharpe": 0.1}},
            )

        after_execution(a, run_id="run_a", script="backtest.py", completed_step="baseline")
        sel = load_selection(a)
        assert sel["n_trials"] == 1, sel
        after_execution(a, run_id="run_a", script="backtest.py", completed_step="baseline")
        sel = load_selection(a)
        assert sel["n_trials"] == 1, sel["events"]  # replay same fingerprint

        _write_json(
            a / "strategy_spec.json",
            {
                "workflow": "single_asset_signals",
                "strategy_type": "MEAN_REVERSION",
                "symbol": "QQQ",
                "interval": "1d",
                "asset_class": "equity",
                "params": {"lookback": 40},
            },
        )
        after_execution(a, run_id="run_a", script="backtest.py", completed_step="baseline")
        sel = load_selection(a)
        assert sel["n_trials"] == 2, sel["events"]

        _write_json(a / "artifacts" / "psa_summary.json", {"grid_cells": 36})
        after_execution(a, run_id="run_a", script="psa.py", completed_step="psa")
        sel = load_selection(a)
        assert sel["n_trials"] == 38, sel  # 2 baselines + 36 cells
        assert sel["breakdown"]["psa_cells"] == 36

        record_event(b, kind="baseline_eval", n_increment=10)
        fam, priors = family_n("run_a", a, sel["n_trials"], runs_dir=runs)
        assert priors == 10
        assert fam == 48


def test_detect_grid() -> None:
    assert detect_grid_from_obj({"grid_cells": 36}) == ("psa_grid", 36)
    assert detect_grid_from_obj({"parameter_grid": {"a": [1, 2], "b": [3, 4, 5]}}) == ("psa_grid", 6)
    assert detect_grid_from_obj({"cost_levels": [0.0, 0.0005, 0.001]}) == ("cea_grid", 3)
    assert detect_grid_from_obj({"n_simulations": 500}) == ("mc_sims", 500)


def test_null_baseline_percentile() -> None:
    idx = pd.date_range("2020-01-01", periods=200, freq="D", tz="UTC")
    asset = pd.Series(0.001 + np.random.default_rng(0).normal(0, 0.01, 200), index=idx)
    pos = pd.Series(0.0, index=idx)
    pos.iloc[::10] = 1.0
    strat = pos.shift(1).fillna(0.0) * asset
    out = random_entry_matched_hold(
        asset_returns=asset,
        position=pos,
        strategy_returns=strat,
        n_sims=50,
        seed=0,
        annualization=252,
        strategy_sharpe_is=sharpe_from_returns(strat, 252),
    )
    assert "sharpe_is_p95" in out
    assert 0.0 <= out["strategy_is_percentile"] <= 1.0


def test_novy_marx_multiplier() -> None:
    assert combination_multiplier(1) == 1.0
    m = combination_multiplier(12, 0.45)
    assert 1.3 < m < 1.6
    note = novy_marx_note(k=3)
    assert note["k"] == 3
    assert "NBER 21329" in note["citation"]


def test_cs_shuffle_zero_mean() -> None:
    rng = np.random.default_rng(2)
    dates = pd.date_range("2020-01-01", periods=80, freq="D", tz="UTC")
    names = [f"a{i}" for i in range(12)]
    fwd = pd.DataFrame(rng.normal(0, 0.02, size=(80, 12)), index=dates, columns=names)
    sig = pd.DataFrame(rng.normal(0, 1, size=(80, 12)), index=dates, columns=names)
    out = label_shuffle_cs(sig, fwd, n_sims=30, seed=2, annualization=252, observed_sharpe=0.0)
    assert "sharpe_is_mean" in out
    assert abs(out["sharpe_is_mean"]) < 1.0


def test_manufacturing_surface_lookup() -> None:
    rng = np.random.default_rng(3)
    r = pd.Series(rng.normal(0, 0.01, size=300))
    surface = manufacturing_surface(r, n_values=[50, 100], k_values=[1, 3], n_pool=100, seed=3, annualization=252)
    assert surface["cells"]
    v = lookup_cell(surface, 50, 1)
    assert isinstance(v, float)


def test_index_exposes_selection() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp) / "runs"
        root = runs / "qqq_a"
        (root / "artifacts").mkdir(parents=True)
        _write_json(
            root / "run.json",
            {
                "run_id": "qqq_a",
                "title": "QQQ A",
                "created_at": "2026-01-01T00:00:00+00:00",
                "root": "runs/qqq_a",
                "status": "baseline_complete",
                "symbol": "QQQ",
                "strategy_type": "MEAN_REVERSION",
                "validation_passed": True,
                "defaults": {"interval": "1d"},
            },
        )
        _write_json(
            root / "strategy_spec.json",
            {
                "workflow": "w",
                "strategy_type": "MEAN_REVERSION",
                "symbol": "QQQ",
                "asset_class": "equity",
                "interval": "1d",
                "params": {"lookback": 20},
            },
        )
        _write_json(
            root / "artifacts" / "metrics.json",
            {"in_sample": {"Sharpe": 1.2}, "out_of_sample": {"Sharpe": 0.2}},
        )
        persist_is_returns(root, pd.Series(np.random.default_rng(4).normal(0.001, 0.01, 200)))
        seed_selection(root)
        after_execution(root, run_id="qqq_a", script="backtest.py", completed_step="baseline")
        rebuild_index(cfg=_CFG, runs_dir=runs)
        card = extract_run_card("qqq_a", cfg=_CFG, runs_dir=runs)
        assert card["n_trials"] == 1
        assert card["n_legs"] == 1
        hits = search_runs(n_trials_gte=1, cfg=_CFG, runs_dir=runs)
        assert any(c["run_id"] == "qqq_a" for c in hits)


def main() -> int:
    tests = [
        test_norm_ppf_roundtrip,
        test_dsr_n1_equals_psr_vs_zero,
        test_dsr_large_n_shrinks,
        test_expected_max_n1_zero,
        test_count_legs,
        test_counting_baseline_replay_psa_family,
        test_detect_grid,
        test_null_baseline_percentile,
        test_novy_marx_multiplier,
        test_cs_shuffle_zero_mean,
        test_manufacturing_surface_lookup,
        test_index_exposes_selection,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"ok  {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}", file=sys.stderr)
            import traceback

            traceback.print_exc()
    if failed:
        print(f"{failed} failed", file=sys.stderr)
        return 1
    print(f"{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
