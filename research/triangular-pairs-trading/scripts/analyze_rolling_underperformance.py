#!/usr/bin/env python3
"""Diagnose why rolling refresh underperforms frozen triangle lists."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backtest import backtest_triangles, compute_metrics
from src.config import ANCHORS, OOS_START, RESULTS_DIR
from src.data import load_close_panel, resample_to_daily
from src.discovery import discover_triangles, select_triangles
from src.rolling_refresh import backtest_rolling_refresh, build_rolling_schedule
from src.triangles import Triangle, score_triangle_in_sample
from src.data import log_prices

OOS = pd.Timestamp(OOS_START, tz="UTC")
LOAD_START = pd.Timestamp("2023-01-01", tz="UTC")
DISC_LOOKBACK = 365
DISC_WINDOW = 720
BT_WINDOW = 1440
ENTRY_Z = 2.5
EXIT_Z = 0.75
WEIGHT_CAP = 0.15
N_TRI = 10
ADF_MAX = 0.05

FROZEN_KEYS = [
    "SFPUSDT|BTCUSDT|ETHUSDT",
    "SFPUSDT|SOLUSDT|BNBUSDT",
    "SFPUSDT|SOLUSDT|ETHUSDT",
    "SFPUSDT|SOLUSDT|BTCUSDT",
    "SFPUSDT|BTCUSDT|BNBUSDT",
    "ARPAUSDT|SOLUSDT|BNBUSDT",
    "ARPAUSDT|BTCUSDT|ETHUSDT",
    "SFPUSDT|ETHUSDT|BNBUSDT",
    "SPELLUSDT|ETHUSDT|BNBUSDT",
    "ALICEUSDT|ETHUSDT|BNBUSDT",
]
FROZEN = [Triangle(*k.split("|")) for k in FROZEN_KEYS]


def sharpe(r: pd.Series, ann: int = 365) -> float:
    r = r.dropna()
    if r.empty or r.std() == 0:
        return float("nan")
    return float(r.mean() / r.std() * np.sqrt(ann))


def load_schedule(path: Path) -> list[dict]:
    raw = json.loads(path.read_text())
    out = []
    for entry in raw:
        tris = [Triangle(t["target"], t["leg1"], t["leg2"]) for t in entry["triangles"]]
        out.append({"start": pd.Timestamp(entry["start"]), "triangles": tris})
    return out


def segment_metrics(close_h: pd.DataFrame, schedule: list[dict], label: str) -> pd.DataFrame:
    rows = []
    for i, entry in enumerate(schedule):
        start = entry["start"]
        end = schedule[i + 1]["start"] if i + 1 < len(schedule) else close_h.index[-1] + pd.Timedelta(hours=1)
        tris = entry["triangles"]
        assets = sorted({a for t in tris for a in (t.target, t.leg1, t.leg2)})
        mask = (close_h.index >= start) & (close_h.index < end)
        if not mask.any():
            continue
        seg_idx = close_h.index[mask]
        loc0 = close_h.index.get_loc(seg_idx[0])
        warmup_i = max(0, loc0 - BT_WINDOW - 5)
        hist = close_h.iloc[warmup_i : close_h.index.get_loc(seg_idx[-1]) + 1][assets]
        res = backtest_triangles(
            hist,
            tris,
            window=BT_WINDOW,
            min_periods=BT_WINDOW // 2,
            entry_z=ENTRY_Z,
            exit_z=EXIT_Z,
            weight_cap=WEIGHT_CAP,
        )
        daily = resample_to_daily(res.daily_returns.loc[seg_idx])
        targets = sorted({t.target for t in tris})
        rows.append(
            {
                "variant": label,
                "segment": i,
                "start": start,
                "end": end,
                "n_triangles": len(tris),
                "unique_targets": len(targets),
                "top_target": targets[0] if len(targets) == 1 else f"{len(targets)}_targets",
                "target_symbols": ",".join(targets),
                "overlap_frozen": len({t.key for t in tris} & set(FROZEN_KEYS)),
                "daily_sharpe": sharpe(daily),
                "oos_segment": start >= OOS or end > OOS,
                "n_days": len(daily),
            }
        )
    return pd.DataFrame(rows)


def triangle_health(close_h: pd.DataFrame, triangles: list[Triangle], *, window: int = 720) -> pd.DataFrame:
    """Rolling health of frozen triangles: ADF p-value and half-life on trailing windows."""
    log_h = log_prices(close_h)
    rows = []
    eval_dates = pd.date_range(close_h.index[BT_WINDOW], close_h.index[-1], freq="90D", tz="UTC")
    for dt in eval_dates:
        hist_end = dt
        hist_start = hist_end - pd.Timedelta(days=DISC_LOOKBACK)
        hist = log_h.loc[(log_h.index >= hist_start) & (log_h.index <= hist_end)]
        if len(hist) < window:
            continue
        for tri in triangles:
            row = score_triangle_in_sample(
                hist,
                tri,
                oos_start=hist_end + pd.Timedelta(hours=1),
                window=window,
                min_periods=window // 2,
                half_life_cap=60 * 24,
                half_life_norm=120 * 24,
            )
            rows.append(
                {
                    "date": dt,
                    "triangle": tri.key,
                    "target": tri.target,
                    "adf_p": row["adf_p"],
                    "half_life": row["half_life"],
                    "score": row["score"],
                    "adf_pass": row["adf_p"] < ADF_MAX,
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    close_h = load_close_panel(interval="1h", start=LOAD_START)

    # --- Frozen baseline returns ---
    assets_f = sorted({a for t in FROZEN for a in (t.target, t.leg1, t.leg2)})
    frozen_res = backtest_triangles(
        close_h[assets_f],
        FROZEN,
        window=BT_WINDOW,
        min_periods=BT_WINDOW // 2,
        entry_z=ENTRY_Z,
        exit_z=EXIT_Z,
        weight_cap=WEIGHT_CAP,
    )
    frozen_daily = resample_to_daily(frozen_res.daily_returns)

    sched_365 = load_schedule(RESULTS_DIR / "schedule_refresh_365D_sticky_True.json")
    sched_180 = load_schedule(RESULTS_DIR / "schedule_refresh_180D_sticky_True.json")

    seg_365 = segment_metrics(close_h, sched_365, "rolling_365d")
    seg_180 = segment_metrics(close_h, sched_180, "rolling_180d")
    seg_df = pd.concat([seg_365, seg_180], ignore_index=True)
    seg_df.to_csv(RESULTS_DIR / "rolling_segment_attribution.csv", index=False)

    # --- Counterfactual: what if rolling used frozen list each segment? ---
    cf_rows = []
    for i, entry in enumerate(sched_365):
        start = entry["start"]
        end = sched_365[i + 1]["start"] if i + 1 < len(sched_365) else close_h.index[-1] + pd.Timedelta(hours=1)
        mask = (close_h.index >= start) & (close_h.index < end)
        if not mask.any():
            continue
        seg_idx = close_h.index[mask]
        loc0 = close_h.index.get_loc(seg_idx[0])
        warmup_i = max(0, loc0 - BT_WINDOW - 5)
        hist = close_h.iloc[warmup_i : close_h.index.get_loc(seg_idx[-1]) + 1]
        for label, tris in [("rolling_pick", entry["triangles"]), ("frozen_pick", FROZEN)]:
            tri_assets = sorted({a for t in tris for a in (t.target, t.leg1, t.leg2)})
            res = backtest_triangles(
                hist[tri_assets],
                tris,
                window=BT_WINDOW,
                min_periods=BT_WINDOW // 2,
                entry_z=ENTRY_Z,
                exit_z=EXIT_Z,
                weight_cap=WEIGHT_CAP,
            )
            daily = resample_to_daily(res.daily_returns.loc[seg_idx])
            cf_rows.append(
                {
                    "segment": i,
                    "start": start,
                    "list": label,
                    "daily_sharpe": sharpe(daily),
                    "total_return": float((1 + daily).prod() - 1),
                }
            )
    cf_df = pd.DataFrame(cf_rows)
    cf_df.to_csv(RESULTS_DIR / "rolling_counterfactual_frozen_vs_pick.csv", index=False)

    # --- Discovery at each refresh date vs frozen ---
    disc_rows = []
    for entry in sched_365:
        reb = entry["start"]
        disc_end = reb - pd.Timedelta(hours=1)
        disc_start = disc_end - pd.Timedelta(days=DISC_LOOKBACK)
        ranked = discover_triangles(
            close_h,
            oos_start=reb,
            discovery_start=disc_start,
            discovery_end=disc_end,
            liquid_top_n=30,
            window=DISC_WINDOW,
            min_periods=DISC_WINDOW // 2,
            half_life_cap=60 * 24,
            half_life_norm=120 * 24,
            progress_every=0,
        )
        top = select_triangles(ranked, N_TRI, adf_max=ADF_MAX)
        top_keys = {t.key for t in top}
        pick_keys = {t.key for t in entry["triangles"]}
        disc_rows.append(
            {
                "refresh_date": reb,
                "top1_target": ranked.iloc[0]["target"] if len(ranked) else None,
                "top1_score": float(ranked.iloc[0]["score"]) if len(ranked) else None,
                "picked_overlap_top10": len(pick_keys & top_keys),
                "picked_overlap_frozen": len(pick_keys & set(FROZEN_KEYS)),
                "picked_unique_targets": len({t.target for t in entry["triangles"]}),
                "frozen_would_overlap": len(top_keys & set(FROZEN_KEYS)),
                "sfp_in_picked": sum(1 for t in entry["triangles"] if t.target == "SFPUSDT"),
                "usdc_in_picked": sum(1 for t in entry["triangles"] if t.target == "USDCUSDT"),
            }
        )
    disc_df = pd.DataFrame(disc_rows)
    disc_df.to_csv(RESULTS_DIR / "rolling_discovery_vs_frozen.csv", index=False)

    # --- Triangle health monitor for frozen list ---
    health = triangle_health(close_h, FROZEN, window=DISC_WINDOW)
    health.to_csv(RESULTS_DIR / "frozen_triangle_health.csv", index=False)

    # Aggregate health: % triangles passing ADF at each eval date
    health_agg = (
        health.groupby("date")
        .agg(
            n_pass=("adf_pass", "sum"),
            median_adf_p=("adf_p", "median"),
            median_half_life=("half_life", "median"),
            median_score=("score", "median"),
        )
        .reset_index()
    )
    health_agg["pass_rate"] = health_agg["n_pass"] / len(FROZEN)
    health_agg.to_csv(RESULTS_DIR / "frozen_health_summary.csv", index=False)

    # --- Refresh trigger simulation: re-discover when pass_rate < threshold ---
    trigger_rows = []
    for thresh in [0.3, 0.5, 0.7]:
        last_refresh = close_h.index[BT_WINDOW]
        refreshes = [last_refresh]
        for _, row in health_agg.iterrows():
            if row["pass_rate"] < thresh and (row["date"] - last_refresh).days >= 90:
                refreshes.append(row["date"])
                last_refresh = row["date"]
        trigger_rows.append({"adf_pass_threshold": thresh, "n_triggers": len(refreshes) - 1, "dates": [d.isoformat() for d in refreshes[1:]]})
    trigger_df = pd.DataFrame(trigger_rows)

    # --- Yearly comparison frozen vs rolling ---
    roll_res = backtest_rolling_refresh(
        close_h,
        sched_365,
        interval="1h",
        entry_z=ENTRY_Z,
        exit_z=EXIT_Z,
        weight_cap=WEIGHT_CAP,
        bt_window=BT_WINDOW,
        bt_min_periods=BT_WINDOW // 2,
    )
    roll_daily = resample_to_daily(roll_res.daily_returns)
    yearly = []
    for year in sorted(set(frozen_daily.index.year) | set(roll_daily.index.year)):
        for label, series in [("frozen", frozen_daily), ("rolling_365", roll_daily)]:
            sub = series[series.index.year == year]
            if sub.empty:
                continue
            yearly.append({"year": year, "variant": label, "sharpe": sharpe(sub), "return": float((1 + sub).prod() - 1)})
    yearly_df = pd.DataFrame(yearly)

  # --- Print report ---
    print("=" * 70)
    print("ROLLING UNDERPERFORMANCE DIAGNOSTICS")
    print("=" * 70)

    print("\n## 1. Segment attribution (365D refresh)")
    print(seg_365[["start", "end", "top_target", "overlap_frozen", "daily_sharpe", "n_days"]].to_string(index=False))

    print("\n## 2. Counterfactual: same segment dates, frozen list vs rolling pick")
    pivot = cf_df.pivot(index="segment", columns="list", values="daily_sharpe")
    pivot["delta_frozen_minus_pick"] = pivot["frozen_pick"] - pivot["rolling_pick"]
    print(pivot.to_string())
    print(f"  Frozen wins { (pivot['delta_frozen_minus_pick'] > 0).sum() } / {len(pivot)} segments on Sharpe")

    print("\n## 3. Discovery overlap with frozen at each 365D refresh")
    print(disc_df.to_string(index=False))

    print("\n## 4. Yearly Sharpe: frozen vs rolling")
    print(yearly_df.pivot(index="year", columns="variant", values="sharpe").to_string())

    print("\n## 5. Frozen triangle health (ADF pass rate over time)")
    print(health_agg[["date", "pass_rate", "median_adf_p", "median_half_life", "median_score"]].to_string(index=False))

    print("\n## 6. Suggested refresh triggers (ADF pass rate on frozen list)")
    for row in trigger_rows:
        print(f"  threshold={row['adf_pass_threshold']}: {row['n_triggers']} triggers -> {row['dates'][:5]}")

    oos_frozen = frozen_daily[frozen_daily.index >= OOS]
    oos_roll = roll_daily[roll_daily.index >= OOS]
    print(f"\n## OOS Sharpe: frozen={sharpe(oos_frozen):.3f}  rolling_365={sharpe(oos_roll):.3f}")

    summary = {
        "segment_365": seg_365.to_dict(orient="records"),
        "counterfactual": cf_df.to_dict(orient="records"),
        "discovery_overlap": disc_df.to_dict(orient="records"),
        "yearly": yearly_df.to_dict(orient="records"),
        "health_summary": health_agg.to_dict(orient="records"),
        "refresh_triggers": trigger_rows,
        "oos_sharpe": {"frozen": sharpe(oos_frozen), "rolling_365": sharpe(oos_roll)},
    }
    (RESULTS_DIR / "rolling_underperformance_analysis.json").write_text(
        json.dumps(summary, indent=2, default=str)
    )
    print(f"\nWrote analysis to {RESULTS_DIR}/rolling_underperformance_analysis.json")


if __name__ == "__main__":
    main()
