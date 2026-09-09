#!/usr/bin/env python3
"""Tests for formulaic alpha mining: safe eval, lag, OOS freeze, N counting."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.alpha_eval import lag_signal, score_signal  # noqa: E402
from tqg_client.alpha_mine import run_alpha_mine  # noqa: E402
from tqg_client.alpha_ops import evaluate_expr, last_int_literal, replace_last_int  # noqa: E402
from tqg_client.alpha_seeds import seeds_for_packs  # noqa: E402
from tqg_client.market_data import load_ohlcv_panel  # noqa: E402
from tqg_client.run_state import RunState, save_run_state  # noqa: E402
from tqg_client.selection import load_selection, seed_selection  # noqa: E402


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def test_safe_eval_rejects_imports() -> None:
    close = pd.DataFrame({"A": [1.0, 2.0, 3.0]}, index=pd.date_range("2020-01-01", periods=3, tz="UTC"))
    fields = {
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": close,
    }
    try:
        evaluate_expr("__import__('os').system('pwd')", fields)
    except ValueError as exc:
        assert "Disallowed" in str(exc) or "Unknown" in str(exc) or "attribute" in str(exc).lower()
    else:
        raise AssertionError("dangerous expression was allowed")


def test_last_int_mutate() -> None:
    expr = "-cs_zscore(ts_corr(close, volume, 20))"
    assert last_int_literal(expr) == 20
    assert replace_last_int(expr, 40) == "-cs_zscore(ts_corr(close, volume, 40))"


def test_lag_breaks_same_bar_lookahead() -> None:
    idx = pd.date_range("2020-01-01", periods=8, tz="UTC")
    signal = pd.DataFrame({"A": np.arange(8.0), "B": np.arange(8.0)[::-1]}, index=idx)
    lagged = lag_signal(signal, 1)
    assert pd.isna(lagged.iloc[0, 0])
    assert lagged.iloc[1, 0] == 0.0


def _synthetic_panel(n_names: int = 24, n_days: int = 220) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(7)
    idx = pd.date_range("2023-01-02", periods=n_days, freq="B", tz="UTC")
    names = [f"N{i:02d}" for i in range(n_names)]
    noise = rng.normal(0.0, 0.01, size=(n_days, n_names))
    leftover = rng.normal(0.0, 1.0, size=(n_days, n_names))
    leftover[0] = 0.0
    # Next-day residual return is minus yesterday's leftover (mean reversion).
    rets = noise.copy()
    rets[1:] = rets[1:] - 0.15 * leftover[:-1]
    close = 100.0 * np.exp(np.cumsum(rets, axis=0))
    open_ = close * (1.0 - 0.001 * leftover)
    high = np.maximum(open_, close) * 1.001
    low = np.minimum(open_, close) * 0.999
    volume = rng.uniform(1e6, 2e6, size=close.shape)
    cols = names
    return {
        "open": pd.DataFrame(open_, index=idx, columns=cols),
        "high": pd.DataFrame(high, index=idx, columns=cols),
        "low": pd.DataFrame(low, index=idx, columns=cols),
        "close": pd.DataFrame(close, index=idx, columns=cols),
        "volume": pd.DataFrame(volume, index=idx, columns=cols),
        "intra": pd.DataFrame(close - open_, index=idx, columns=cols),
        "ret": pd.DataFrame(pd.DataFrame(close, index=idx, columns=cols).pct_change()),
        "rng": pd.DataFrame(high - low, index=idx, columns=cols),
        "upper_wick": pd.DataFrame(high - np.maximum(open_, close), index=idx, columns=cols),
        "lower_wick": pd.DataFrame(np.minimum(open_, close) - low, index=idx, columns=cols),
        "typical": pd.DataFrame((high + low + close) / 3.0, index=idx, columns=cols),
        "dollar_volume": pd.DataFrame(close * volume, index=idx, columns=cols),
    }


def test_leftover_has_positive_is_rank_ic() -> None:
    fields = _synthetic_panel()
    signal = evaluate_expr("-cs_zscore(intra)", fields)
    out = score_signal(
        signal,
        fields["close"],
        oos_start="2023-10-01",
        annualization=252,
        lag=1,
        include_oos=False,
    )
    assert out["oos"] is None
    assert out["is"]["rank_ic"] is not None
    assert out["is"]["rank_ic"] > 0.02


def _stub_run(tmp: Path, run_id: str = "alpha_test") -> Path:
    root = tmp / "runs" / run_id
    for sub in ("code", "artifacts", "charts", "logs", "inputs"):
        (root / sub).mkdir(parents=True)
    state = RunState(
        run_id=run_id,
        title="alpha test",
        created_at="2026-01-01T00:00:00+00:00",
        root=str(root.resolve()),
        status="created",
        oos_start_ts="2023-10-01",
        defaults={"oos_start": "2023-10-01", "interval": "1d", "fee": 0.0, "slippage": 0.0},
    )
    save_run_state(state)
    seed_selection(root)
    return root


def test_mine_counts_n_and_hides_oos() -> None:
    from tqg_client import alpha_mine as am

    fields = _synthetic_panel()
    idx = fields["close"].index
    names = list(fields["close"].columns)
    rows = []
    for ts in idx:
        for name in names:
            rows.append(
                {
                    "time": ts,
                    "asset": name,
                    "open": float(fields["open"].at[ts, name]),
                    "high": float(fields["high"].at[ts, name]),
                    "low": float(fields["low"].at[ts, name]),
                    "close": float(fields["close"].at[ts, name]),
                    "volume": float(fields["volume"].at[ts, name]),
                }
            )
    long = pd.DataFrame(rows)

    with tempfile.TemporaryDirectory() as tmp_s:
        tmp = Path(tmp_s)
        panel_path = tmp / "panel.parquet"
        long.to_parquet(panel_path, index=False)
        root = _stub_run(tmp)
        run_id = root.name
        orig_load = am.load_run_state

        def _load(rid: str, **kwargs):
            return orig_load(rid, runs_dir=tmp / "runs")

        am.load_run_state = _load  # type: ignore[assignment]
        try:
            result = am.run_alpha_mine(
                run_id,
                panel_path=panel_path,
                packs=["leftover", "momentum"],
                top_n=24,
                min_bars=40,
                oos_start="2023-10-01",
                asset_class="equity",
                reveal_oos=False,
            )
            art = json.loads((root / "artifacts" / "alphas.json").read_text())
            assert art["oos_revealed"] is False
            for row in art["alphas"]:
                if row.get("status") == "active":
                    assert row.get("oos") is None
            sel = load_selection(root)
            n_active = sum(1 for r in art["alphas"] if r.get("status") == "active")
            assert sel["n_trials"] == n_active, sel
            assert result["n_new_formulas"] == n_active

            am.run_alpha_mine(
                run_id,
                panel_path=panel_path,
                packs=["leftover", "momentum"],
                top_n=24,
                min_bars=40,
                oos_start="2023-10-01",
                asset_class="equity",
                reveal_oos=False,
            )
            sel2 = load_selection(root)
            assert sel2["n_trials"] == n_active, sel2["events"]

            dropped = next(r["id"] for r in art["alphas"] if "momentum" in (r.get("tags") or []))
            am.run_alpha_mine(
                run_id,
                panel_path=panel_path,
                drop_ids=[dropped],
                mutate_id="A_LO3",
                windows=[10, 20],
                top_n=24,
                min_bars=40,
                oos_start="2023-10-01",
                asset_class="equity",
                reveal_oos=False,
            )
            sel3 = load_selection(root)
            assert sel3["n_trials"] > n_active

            book_result = am.run_alpha_mine(
                run_id,
                panel_path=panel_path,
                keep_ids=["A_LO1", "A_LO3"],
                book_ids=["A_LO1", "A_LO3"],
                top_n=24,
                min_bars=40,
                oos_start="2023-10-01",
                asset_class="equity",
                reveal_oos=True,
            )
            art2 = json.loads((root / "artifacts" / "alphas.json").read_text())
            assert art2["oos_revealed"] is True
            assert art2["book"] is not None
            assert art2["book"]["oos"] is not None
            spec = json.loads((root / "strategy_spec.json").read_text())
            assert spec["signals"] == ["A_LO1", "A_LO3"]
            assert book_result["oos_revealed"] is True
        finally:
            am.load_run_state = orig_load  # type: ignore[assignment]


def test_load_ohlcv_panel_top_n() -> None:
    rng = np.random.default_rng(1)
    idx = pd.date_range("2024-01-01", periods=80, tz="UTC")
    rows = []
    for i, name in enumerate(["AAA", "BBB", "CCC", "DDD"]):
        px = 10.0 + i
        vol = 100.0 * (i + 1)
        for ts in idx:
            rows.append(
                {
                    "time": ts,
                    "asset": name,
                    "open": px,
                    "high": px + 0.1,
                    "low": px - 0.1,
                    "close": px,
                    "volume": vol,
                }
            )
    with tempfile.TemporaryDirectory() as tmp_s:
        path = Path(tmp_s) / "p.parquet"
        pd.DataFrame(rows).to_parquet(path, index=False)
        fields = load_ohlcv_panel(path, min_bars=20, top_n=2)
        assert list(fields["close"].columns) == ["DDD", "CCC"]


def test_seed_packs_known() -> None:
    seeds = seeds_for_packs(["leftover", "volume"])
    ids = {s["id"] for s in seeds}
    assert "A_LO1" in ids
    assert "A_VP1" in ids
    assert "A_MO1" not in ids


if __name__ == "__main__":
    test_safe_eval_rejects_imports()
    test_last_int_mutate()
    test_lag_breaks_same_bar_lookahead()
    test_leftover_has_positive_is_rank_ic()
    test_seed_packs_known()
    test_load_ohlcv_panel_top_n()
    test_mine_counts_n_and_hides_oos()
    print("ok")
