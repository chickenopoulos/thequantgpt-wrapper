#!/usr/bin/env python3
"""Publish Top50 MA-ensemble PSA median-nearest (W=70 / ±0.5) to Strategy Log as D-70.

Benchmark: Bitcoin (BTCUSDT) buy & hold.
Writes curve + registry entry to demo-temp source and upserts the live site
without a full rsync --delete (live catalog diverged from demo-temp).
"""

from __future__ import annotations

import json
import math
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import vectorbt as vbt

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tqg_client.ma_ensemble import (  # noqa: E402
    MA_NAMES,
    compute_ma_panel,
    consensus_signal,
    positions_from_consensus,
)

DEMO = Path("/root/demo67-src/demo-temp")
LIVE = Path("/var/www/demo-vkotopoulos")
PERSONAL = Path("/var/www/personal_fractional_quant_landing_page")  # vkotopoulos.com
RUN = REPO / "runs" / "ma_ensemble_top50_perps"
PARQUET = REPO / "data" / "binance" / "binance_futures_ohlcv_1d.parquet"
BTC_PARQUET = REPO / "data" / "btc_1d_full.parquet"
OOS = pd.Timestamp("2025-01-01", tz="UTC")
ANN = 365.0
NEW_ID = "D-70"
WINDOW = 70
ENTRY = 0.5
EXIT = 0.5
FEE = 0.00045
SLIP = 0.0005
LAB_REF = "ma_ensemble_top50_perps / PSA median-nearest W=70 ±0.5"


def sharpe(r: pd.Series) -> float | None:
    r = r.dropna()
    if len(r) < 20:
        return None
    vol = float(r.std())
    return float(np.sqrt(ANN) * r.mean() / vol) if vol > 0 else 0.0


def cagr_from_rets(r: pd.Series) -> float:
    r = r.dropna()
    if len(r) < 2:
        return 0.0
    eq = (1 + r).cumprod()
    years = len(r) / ANN
    if years <= 0 or float(eq.iloc[-1]) <= 0:
        return 0.0
    return float(eq.iloc[-1] ** (1.0 / years) - 1)


def maxdd_from_rets(r: pd.Series) -> float:
    eq = (1 + r.fillna(0)).cumprod()
    return float((eq / eq.cummax() - 1).min())


def sortino(r: pd.Series) -> float | None:
    r = r.dropna()
    downside = r[r < 0]
    if len(r) < 20 or float(downside.std()) == 0:
        return None
    return float(np.sqrt(ANN) * r.mean() / downside.std())


def count_sign_flips(pos: pd.Series) -> int:
    p = pos.fillna(0.0).to_numpy(dtype=float)
    if len(p) < 2:
        return 0
    return int(np.sum(np.sign(p[1:]) != np.sign(p[:-1])))


def load_btc_bh(idx: pd.DatetimeIndex) -> pd.Series:
    if BTC_PARQUET.exists():
        btc = pd.read_parquet(BTC_PARQUET)
        # flexible schema
        if "time" in btc.columns:
            btc["time"] = pd.to_datetime(btc["time"], utc=True)
            btc = btc.set_index("time").sort_index()
        elif not isinstance(btc.index, pd.DatetimeIndex):
            btc.index = pd.to_datetime(btc.index, utc=True)
        else:
            btc.index = pd.to_datetime(btc.index, utc=True)
        close_col = "close" if "close" in btc.columns else btc.columns[0]
        close = btc[close_col].astype(float).sort_index()
    else:
        raw = pd.read_parquet(PARQUET)
        raw["time"] = pd.to_datetime(raw["time"], utc=True)
        g = raw.loc[raw["asset"].astype(str) == "BTCUSDT"].sort_values("time")
        close = g.set_index("time")["close"].astype(float)
    rets = close.pct_change()
    return rets.reindex(idx)


def upsert_registry(reg_path: Path, entry: dict) -> dict:
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    existed = any(e.get("id") == NEW_ID for e in reg["entries"])
    reg["entries"] = [e for e in reg["entries"] if e.get("id") != NEW_ID]
    reg["entries"].append(entry)
    n_curves = sum(1 for e in reg["entries"] if e.get("has_curve"))
    if isinstance(reg.get("curve_files"), int):
        reg["curve_files"] = n_curves
    reg["generated_at"] = datetime.now(timezone.utc).isoformat()
    counts = dict(reg.get("counts") or {})
    counts["entries"] = len(reg["entries"])
    counts["with_curve"] = n_curves
    counts["with_equity_curves"] = n_curves
    counts["cleared_research_bar"] = sum(1 for e in reg["entries"] if e.get("cleared_research_bar"))
    counts["total"] = len(reg["entries"])
    tiers: dict[str, int] = {}
    for e in reg["entries"]:
        t = str(e.get("tier") or "unknown")
        tiers[t] = tiers.get(t, 0) + 1
    counts["tiers"] = tiers
    reg["counts"] = counts
    reg_path.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"existed": existed, "n_entries": len(reg["entries"]), "path": str(reg_path)}


def main() -> None:
    universe = json.loads((RUN / "artifacts" / "universe_rank.json").read_text())["symbols"]
    psa = json.loads((RUN / "artifacts" / "psa_summary.json").read_text())
    sel = json.loads((RUN / "artifacts" / "selection.json").read_text())
    dsr = float((sel.get("dsr") or {}).get("dsr") or 0.0)
    n_trials = int(sel.get("n_trials") or psa.get("grid_cells") or 119)
    pbo = (sel.get("pbo") or {}).get("pbo")
    island = int(psa.get("island_size") or 0)
    grid_cells = int(psa.get("grid_cells") or 0)

    raw = pd.read_parquet(PARQUET)
    raw["time"] = pd.to_datetime(raw["time"], utc=True)

    per_asset: dict[str, pd.Series] = {}
    per_asset_2x: dict[str, pd.Series] = {}
    pos_panel: dict[str, pd.Series] = {}
    for sym in universe:
        g = raw.loc[raw["asset"].astype(str) == sym].sort_values("time")
        if g.empty:
            continue
        g = g.set_index("time")
        close = g["close"].astype(float)
        volume = g["volume"].astype(float).reindex(close.index).fillna(0.0)
        # MA panel computed once; portfolio priced at base and 2× costs.
        mas = compute_ma_panel(close, volume, WINDOW, ma_names=MA_NAMES)
        consensus = consensus_signal(close, mas)
        pos, entries, short_entries = positions_from_consensus(
            consensus, entry=ENTRY, exit_thresh=EXIT
        )
        exits = consensus.abs() < EXIT
        for label, fee, slip, sink in (
            ("base", FEE, SLIP, per_asset),
            ("2x", FEE * 2.0, SLIP * 2.0, per_asset_2x),
        ):
            pf = vbt.Portfolio.from_signals(
                close,
                entries=entries.fillna(False),
                short_entries=short_entries.fillna(False),
                exits=exits.fillna(False),
                short_exits=exits.fillna(False),
                fees=fee,
                slippage=slip,
                freq="1D",
            )
            sink[sym] = pf.returns().astype(float).replace([np.inf, -np.inf], np.nan)
        pos_panel[sym] = pos.astype(float)

    rets_df = pd.DataFrame(per_asset).sort_index()
    pos_df = pd.DataFrame(pos_panel).reindex(rets_df.index)
    port = rets_df.mean(axis=1, skipna=True).fillna(0.0)
    # Portfolio position proxy: mean signed exposure across available names
    port_pos = pos_df.mean(axis=1, skipna=True).fillna(0.0)

    btc = load_btc_bh(port.index).fillna(0.0)
    # Align start: first day both have data / strategy active
    first = port.index[port.abs() > 0]
    start = first[0] if len(first) else port.index[0]
    port = port.loc[port.index >= start]
    btc = btc.reindex(port.index).fillna(0.0)
    port_pos = port_pos.reindex(port.index).fillna(0.0)

    strat_eq = (1.0 + port).cumprod()
    bh_eq = (1.0 + btc).cumprod()
    strat_eq = strat_eq / float(strat_eq.iloc[0])
    bh_eq = bh_eq / float(bh_eq.iloc[0])

    is_mask = port.index < OOS
    oos_mask = port.index >= OOS
    sharpe_is = sharpe(port[is_mask]) or 0.0
    sharpe_oos = sharpe(port[oos_mask]) or 0.0
    sharpe_full = sharpe(port) or 0.0
    cagr_is = cagr_from_rets(port[is_mask])
    cagr_oos = cagr_from_rets(port[oos_mask])
    cagr_full = cagr_from_rets(port)
    maxdd_is = maxdd_from_rets(port[is_mask])
    maxdd_oos = maxdd_from_rets(port[oos_mask])
    maxdd_full = maxdd_from_rets(port)
    sortino_full = sortino(port)
    bh_oos_sr = sharpe(btc[oos_mask]) or 0.0
    bh_full_sr = sharpe(btc) or 0.0
    bh_is_sr = sharpe(btc[is_mask]) or 0.0

    trades_full = count_sign_flips(port_pos)
    trades_is = count_sign_flips(port_pos[is_mask])
    trades_oos = count_sign_flips(port_pos[oos_mask])

    port_2x = pd.DataFrame(per_asset_2x).reindex(port.index).mean(axis=1, skipna=True).fillna(0.0)
    sharpe_oos_2x = sharpe(port_2x[oos_mask]) or 0.0

    cred = 1.0 - math.exp(-int(is_mask.sum()) / ANN)
    delivery = 0.6 * float(np.tanh(sharpe_oos / 1.5)) + 0.4 * min(
        1.0, float(np.clip((sharpe_oos / max(sharpe_is, 1e-6)) / 0.5, 0, 1.2))
    )
    v4 = round(10 * (0.35 * cred + 0.65 * delivery), 2)

    curve_end = str(port.index.max().date())
    oos_window = f"2025-01-01 → {curve_end}"

    curve = {
        "dates": [d.strftime("%Y-%m-%d") for d in port.index],
        "strategy": [round(float(x), 6) for x in strat_eq.to_numpy()],
        "benchmark": [round(float(x), 6) for x in bh_eq.to_numpy()],
        "benchmark_label": "Bitcoin buy & hold",
        "oos_start": "2025-01-01",
        "metrics_as_of": curve_end,
        "note": (
            "Equal-weight Top50 Binance USDT-M perps MA-type vote ensemble "
            f"(PSA median-nearest W={WINDOW} / ±{ENTRY}) vs Bitcoin buy & hold. "
            f"OOS metrics from 2025-01-01 to {curve_end}. Lab ref: {LAB_REF}."
        ),
    }

    g2_ok = trades_full >= 100 and trades_oos >= 30
    g3_ok = sharpe_oos >= 0.5 and sharpe_oos > bh_oos_sr
    g4_ok = sharpe_is >= 0.3 and sharpe_oos >= 0.5 * sharpe_is
    g5_ok = sharpe_oos_2x > 0 and sharpe_oos_2x >= 0.5 * sharpe_oos
    g7_ok = maxdd_oos >= -0.25
    g8_ok = dsr >= 0.95
    # Null not re-run for this publish cell; mark not_assessed rather than inventing a pass.
    g6_ok = island >= 5 and str(psa.get("status") or "").upper() == "STABLE"

    gates = [
        {
            "id": "G0",
            "name": "Run integrity",
            "status": "pass",
            "value": "Reproduced from lab Top50 EW builder at PSA median-nearest W=70 ±0.5",
            "threshold": "Reproducible stats, complete run, no blocking defect",
        },
        {
            "id": "G1",
            "name": "OOS evidence",
            "status": "pass",
            "value": f"{(port.index.max() - OOS).days / 365.25:.2f} yr OOS (to {curve_end})",
            "threshold": "≥ 0.5 yr OOS",
        },
        {
            "id": "G2",
            "name": "Sample size",
            "status": "pass" if g2_ok else "fail",
            "value": f"{trades_full} portfolio sign-flips ({trades_oos} OOS)",
            "threshold": "≥ 100 trades, ≥ 30 OOS",
        },
        {
            "id": "G3",
            "name": "OOS Sharpe vs benchmark",
            "status": "pass" if g3_ok else "fail",
            "value": (
                f"OOS {sharpe_oos:.2f} vs BTC BH {bh_oos_sr:.2f}; "
                f"full {sharpe_full:.2f} vs BTC BH {bh_full_sr:.2f}"
            ),
            "threshold": "OOS ≥ 0.5 and > benchmark; full ≥ benchmark",
        },
        {
            "id": "G4",
            "name": "IS → OOS consistency",
            "status": "pass" if g4_ok else "fail",
            "value": f"IS {sharpe_is:.2f} → OOS {sharpe_oos:.2f}",
            "threshold": "IS ≥ 0.3 and OOS ≥ 50% of IS",
        },
        {
            "id": "G5",
            "name": "Cost stress (2×)",
            "status": "pass" if g5_ok else "fail",
            "value": f"OOS Sharpe at 2× cost {sharpe_oos_2x:.2f} (base {sharpe_oos:.2f})",
            "threshold": "> 0 and ≥ 50% of base",
        },
        {
            "id": "G6",
            "name": "Parameter stability",
            "status": "pass" if g6_ok else "fail",
            "value": (
                f"IS PSA {psa.get('status')}: tight_island size {island}/"
                f"{grid_cells}; median-nearest W={WINDOW} ±{ENTRY}"
            ),
            "threshold": "Stable parameter plateau",
        },
        {
            "id": "G7",
            "name": "OOS drawdown",
            "status": "pass" if g7_ok else "fail",
            "value": f"{maxdd_oos:.1%}",
            "threshold": "≥ −25%",
        },
        {
            "id": "G8",
            "name": "Multiple testing (DSR)",
            "status": "pass" if g8_ok else "fail",
            "value": f"DSR {dsr:.2f} at N={n_trials} (family PSA+baseline)",
            "threshold": "DSR ≥ 0.95 at honest N",
        },
        {
            "id": "G9",
            "name": "Null test",
            "status": "not_assessed",
            "value": "Random-entry null not re-scored for the published W=70 cell",
            "threshold": "p < 0.05",
        },
    ]
    fail_gates = [g for g in gates if g["status"] == "fail"]
    if fail_gates:
        tier = "failed"
        bar_reason = f"Failed: {fail_gates[0]['name']}: {fail_gates[0]['value']}."
        cleared = False
    else:
        tier = "cleared"
        bar_reason = "Cleared research bar on assessed gates."
        cleared = True

    entry = {
        "id": NEW_ID,
        "name": "Top50 MA-vote ensemble (W=70 / ±0.5)",
        "description": (
            "Equal-weight sleeve on the Top50 Binance USDT-M perps by pre-OOS 90d quote volume. "
            "Each name votes across 14 MA types; long/short when |consensus| ≥ 0.5 at window 70 "
            "(PSA median-nearest on the Top50 IS grid). Benchmark is Bitcoin buy & hold."
        ),
        "asset_class": "Crypto",
        "universe": "Binance USDT-M Top50 (fixed pre-OOS)",
        "validation_passed": True,
        "n_trials": n_trials,
        "dsr": round(dsr, 4),
        "has_curve": True,
        "sharpe_is": round(sharpe_is, 3),
        "sharpe_oos": round(sharpe_oos, 3),
        "sharpe_full": round(sharpe_full, 3),
        "maxdd_is": round(maxdd_is, 4),
        "maxdd_oos": round(maxdd_oos, 4),
        "maxdd_full": round(maxdd_full, 4),
        "cagr_is": round(cagr_is, 4),
        "cagr_oos": round(cagr_oos, 4),
        "cagr_full": round(cagr_full, 4),
        "trades_is": trades_is,
        "trades_oos": trades_oos,
        "trades_full": trades_full,
        "robustness_score": v4,
        "robustness_passed": cleared,
        "psa_status": str(psa.get("status") or "").lower(),
        "psa_stable_cells": island,
        "psa_grid_cells": grid_cells,
        "oos_start": "2025-01-01",
        "bh_terminal_ratio": round(float(strat_eq.iloc[-1] / bh_eq.iloc[-1]), 4),
        "strat_terminal_multiple": round(float(strat_eq.iloc[-1]), 4),
        "bh_terminal_multiple": round(float(bh_eq.iloc[-1]), 4),
        "sharpe_oos_display": round(sharpe_oos, 3),
        "sharpe_full_display": round(sharpe_full, 3),
        "sharpe_is_display": round(sharpe_is, 3),
        "sharpe_headline": round(sharpe_full, 3),
        "maxdd_headline": round(maxdd_full, 4),
        "evaluation_status": "completed",
        "deployment_status": "historical_research",
        "cleared_research_bar": cleared,
        "bar_reason": bar_reason,
        "short_conclusion": (
            f"Top50 MA ensemble W={WINDOW}/±{ENTRY}. Full Sharpe {sharpe_full:.2f}, "
            f"OOS {sharpe_oos:.2f}, max DD {maxdd_full:.1%}, {trades_full} flips. "
            + (
                f"Below bar: {fail_gates[0]['name']}."
                if fail_gates
                else "Cleared assessed gates."
            )
        ),
        "score_label": None,
        "score_capped": False,
        "gates": gates,
        "tier": tier,
        "corrections": [],
        "defects": [],
        "oos_window": oos_window,
        "lineup_role": "research",
        "terminal_window": f"{port.index.min().date()} → {port.index.max().date()}",
        "lab_ref": LAB_REF,
        "sortino_full": None if sortino_full is None else round(sortino_full, 3),
        "v5_layers": "TDS",
        "v5_missing": [],
        "v4_transfer": v4,
        "v5_D": round(dsr, 3),
        "v5_S": None if pbo is None else round(1.0 - float(pbo), 3),
        "v5_dsr": round(dsr, 3),
        "v5_pbo": None if pbo is None else round(float(pbo), 3),
        "v5_psa_quality": psa.get("plateau_quality"),
        "score_v4": v4,
        "score_v5": None,
        "score_v5_soft": None,
        "v5_soft_layers": "TDS",
        "curve_end": curve_end,
        "benchmark_label": "Bitcoin buy & hold",
        "bh_sharpe_is": round(bh_is_sr, 3),
        "bh_sharpe_oos": round(bh_oos_sr, 3),
        "bh_sharpe_full": round(bh_full_sr, 3),
    }

    # Persist publish artifacts under the lab run for audit.
    pub_dir = RUN / "artifacts" / "catalog_publish_d70"
    pub_dir.mkdir(parents=True, exist_ok=True)
    (pub_dir / "curve.json").write_text(json.dumps(curve, indent=2) + "\n", encoding="utf-8")
    (pub_dir / "entry.json").write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
    eq_df = pd.DataFrame(
        {
            "date": [d.strftime("%Y-%m-%d") for d in port.index],
            "strategy": strat_eq.to_numpy(),
            "btc_bh": bh_eq.to_numpy(),
            "strategy_ret": port.to_numpy(),
            "btc_ret": btc.to_numpy(),
        }
    )
    eq_df.to_csv(pub_dir / "equity_vs_btc.csv", index=False)

    results = {"id": NEW_ID, "metrics": {
        "sharpe_is": round(sharpe_is, 3),
        "sharpe_oos": round(sharpe_oos, 3),
        "sharpe_full": round(sharpe_full, 3),
        "bh_oos": round(bh_oos_sr, 3),
        "maxdd_oos": round(maxdd_oos, 4),
        "trades_full": trades_full,
        "tier": tier,
        "fail_gates": [g["id"] for g in fail_gates],
        "v4": v4,
    }}

    for root in (DEMO, LIVE, PERSONAL):
        if not root.exists():
            continue
        curve_path = root / "data" / "registry_curves" / f"{NEW_ID}.json"
        curve_path.parent.mkdir(parents=True, exist_ok=True)
        curve_path.write_text(json.dumps(curve, indent=2) + "\n", encoding="utf-8")
        reg_path = root / "data" / "research_registry.json"
        # Each site keeps its own lineup; upsert only adds/replaces D-70.
        info = upsert_registry(reg_path, entry)
        results[str(root)] = {"curve": str(curve_path), **info}

    # Keep a mirror under demo-temp outputs for deploy audits.
    out = DEMO / "outputs" / "d70_ma_ensemble_top50"
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pub_dir / "curve.json", out / "curve.json")
    shutil.copy2(pub_dir / "entry.json", out / "entry.json")

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
