#!/usr/bin/env python3
"""Fast HF BTC strategy search with diverse families and low-correlation ensemble selection."""

from __future__ import annotations

import itertools
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "runs" / "6" / "code"))

from btc_hf_data import build_all_features  # noqa: E402
from tqg_client.strategy_sweep_core import FEE, LAG, SLIPPAGE  # noqa: E402

RUN = REPO / "runs" / "6"
OOS = pd.Timestamp("2025-01-01", tz="UTC")
ANN_MAP = {"1h": 365 * 24, "4h": 365 * 6, "8h": 365 * 3}
MIN_TRADES = 40
MAX_PAIR_CORR = 0.30
MIN_TRADES_PER_YEAR = 24  # at least ~2x/month vs daily


@dataclass
class Hit:
    id: str
    interval: str
    family: str
    style: str
    name: str
    params: dict
    sharpe: float
    max_dd: float
    sharpe_is: float
    sharpe_oos: float
    trades: int
    exposure: float
    trades_per_year: float


def pos_from_signals(entries: np.ndarray, exits: np.ndarray) -> np.ndarray:
    n = len(entries)
    pos = np.zeros(n, dtype=np.float64)
    state = 0.0
    for i in range(n):
        if state == 0.0 and entries[i]:
            state = 1.0
        elif state > 0.0 and exits[i]:
            state = 0.0
        pos[i] = state
    return pos


def eval_pos_np(close: np.ndarray, pos: np.ndarray, index: pd.DatetimeIndex, ann: int) -> dict:
    asset = np.zeros_like(close)
    asset[1:] = close[1:] / close[:-1] - 1.0
    dpos = np.zeros_like(pos)
    dpos[1:] = np.abs(pos[1:] - pos[:-1])
    r = np.zeros_like(pos)
    r[1:] = pos[:-1] * asset[1:] - dpos[1:] * (FEE + SLIPPAGE)
    rr = r[1:]
    idx = index[1:]
    if len(rr) < 200 or rr.std() == 0:
        return {"sharpe": 0.0, "max_dd": 0.0, "sharpe_is": 0.0, "sharpe_oos": 0.0, "trades": 0, "exposure": 0.0, "trades_per_year": 0.0, "returns": pd.Series(r, index=index)}
    sh = float(np.sqrt(ann) * rr.mean() / rr.std())
    cum = np.cumprod(1 + rr)
    dd = float((cum / np.maximum.accumulate(cum) - 1).min())
    oos_mask = idx >= OOS
    is_r, oos_r = rr[~oos_mask], rr[oos_mask]

    def _sh(s: np.ndarray) -> float:
        return float(np.sqrt(ann) * s.mean() / s.std()) if len(s) > 50 and s.std() > 0 else 0.0

    years = max((idx[-1] - idx[0]).total_seconds() / (365.25 * 86400), 0.5)
    trades = int(dpos.sum())
    return {
        "sharpe": sh,
        "max_dd": dd,
        "sharpe_is": _sh(is_r),
        "sharpe_oos": _sh(oos_r),
        "trades": trades,
        "exposure": float(pos.mean()),
        "trades_per_year": trades / years,
        "returns": pd.Series(r, index=index),
    }


def lag_bool(arr: np.ndarray) -> np.ndarray:
    out = np.zeros_like(arr, dtype=bool)
    out[LAG:] = arr[:-LAG] if LAG else arr
    return out


def consider(hits: list[Hit], hid: str, interval: str, family: str, style: str, name: str, params: dict, m: dict) -> None:
    if m["sharpe"] >= 0.7 and m["max_dd"] > -0.28 and m["trades"] >= MIN_TRADES and m["trades_per_year"] >= MIN_TRADES_PER_YEAR:
        hits.append(
            Hit(hid, interval, family, style, name, params, m["sharpe"], m["max_dd"], m["sharpe_is"], m["sharpe_oos"], m["trades"], m["exposure"], m["trades_per_year"])
        )


def search_interval(interval: str) -> tuple[list[Hit], dict[str, pd.Series]]:
    df, f, meta = build_all_features(interval)
    close = df["close"].to_numpy()
    idx = df.index
    ann = ANN_MAP[interval]
    hits: list[Hit] = []
    ret_map: dict[str, pd.Series] = {}
    c_lag = np.roll(close, LAG)
    c_lag[:LAG] = np.nan

    def run(hid: str, family: str, style: str, name: str, params: dict, entries: np.ndarray, exits: np.ndarray) -> None:
        e = lag_bool(entries)
        x = lag_bool(exits)
        pos = pos_from_signals(e, x)
        m = eval_pos_np(close, pos, idx, ann)
        consider(hits, hid, interval, family, style, name, params, m)
        if m["sharpe"] >= 0.4:
            ret_map[hid] = m["returns"]

    n_cfg = 0

    # 1. RSI MR in uptrend
    for rsi_w, ent, tma in itertools.product([14, 20], [28, 32], [100, 200]):
        rsi = f[f"rsi{rsi_w}"].to_numpy()
        ma = f[f"ma{tma}"].to_numpy()
        e = (c_lag > ma) & (rsi < ent)
        x = (rsi > 55) | (c_lag < ma)
        run(f"rsi_{interval}_{rsi_w}_{ent}_{tma}", "mean_reversion", "oscillator", f"RSI{rsi_w}<{ent}/MA{tma}", {"rsi_w": rsi_w, "ent": ent, "tma": tma}, e, x)
        n_cfg += 1

    # 2. Bollinger fade
    for bw in (20, 40):
        lo = f[f"bb_lower_{bw}"].to_numpy()
        mid = f[f"bb_mid_{bw}"].to_numpy()
        ma200 = f["ma200"].to_numpy()
        e = (c_lag < lo) & (c_lag > ma200)
        x = c_lag > mid
        run(f"bb_{interval}_{bw}", "mean_reversion", "band", f"BB{bw} fade", {"bw": bw}, e, x)
        n_cfg += 1

    # 3. Return z-score MR
    for zw, z_ent in ((48, -1.5), (96, -1.5), (168, -2.0)):
        z = f[f"ret_z{zw}"].to_numpy()
        e = z < z_ent
        x = z > 0.5
        run(f"rz_{interval}_{zw}_{z_ent}", "mean_reversion", "zscore", f"retZ{zw}<{z_ent}", {"zw": zw, "z_ent": z_ent}, e, x)
        n_cfg += 1

    # 4. Donchian breakout
    for w in (20, 55):
        hi = f[f"don_high_{w}"].to_numpy()
        lo = f[f"don_low_{w}"].to_numpy()
        e = c_lag > hi
        x = c_lag < lo
        run(f"don_{interval}_{w}", "momentum", "breakout", f"Donchian{w}", {"w": w}, e, x)
        n_cfg += 1

    # 5. EMA cross
    for fast, slow in ((12, 48), (24, 96)):
        ef = f[f"ema{fast}"].to_numpy()
        es = f[f"ema{slow}"].to_numpy()
        e = ef > es
        x = ef < es
        run(f"ema_{interval}_{fast}_{slow}", "momentum", "trend", f"EMA{fast}/{slow}", {"fast": fast, "slow": slow}, e, x)
        n_cfg += 1

    # 6. TSMOM
    for mw in (10, 20, 40):
        mom = f[f"mom{mw}"].to_numpy()
        ma = f["ma200"].to_numpy()
        e = (mom > 0) & (c_lag > ma)
        x = mom < 0
        run(f"mom_{interval}_{mw}", "momentum", "roc", f"TSMOM{mw}", {"mw": mw}, e, x)
        n_cfg += 1

    # 7. BB squeeze breakout
    for bw in (20, 40):
        width = f[f"bb_width_{bw}"].to_numpy()
        upper = f[f"bb_upper_{bw}"].to_numpy()
        mid = f[f"bb_mid_{bw}"].to_numpy()
        thr = pd.Series(width).rolling(48).quantile(0.15).to_numpy()
        e = (width < thr) & (c_lag > upper)
        x = c_lag < mid
        run(f"sqz_{interval}_{bw}", "volatility", "squeeze", f"BBsqz{bw}", {"bw": bw}, e, x)
        n_cfg += 1

    # 8. ER chop MR
    for erw in (20, 40):
        er = f[f"er{erw}"].to_numpy()
        rsi = f["rsi14"].to_numpy()
        e = (er < 0.35) & (rsi < 28)
        x = rsi > 52
        run(f"er_mr_{interval}_{erw}", "mean_reversion", "regime", f"ER{erw} chop", {"erw": erw}, e, x)
        n_cfg += 1

    # 9. ER trend mom
    for erw, mw in ((20, 10), (40, 20)):
        er = f[f"er{erw}"].to_numpy()
        mom = f[f"mom{mw}"].to_numpy()
        e = (er > 0.55) & (mom > 0.015)
        x = mom < 0
        run(f"er_mom_{interval}_{erw}_{mw}", "momentum", "regime", f"ER{erw}+mom{mw}", {"erw": erw, "mw": mw}, e, x)
        n_cfg += 1

    # 10. Volume spike fade
    for vw in (48, 96):
        vr = f[f"vol_ratio{vw}"].to_numpy()
        ret = np.zeros_like(close)
        ret[1:] = close[1:] / close[:-1] - 1
        ret_lag = np.roll(ret, LAG)
        ret_lag[:LAG] = 0
        e = (vr > 2.0) & (ret_lag < -0.03)
        x = ret_lag > 0
        run(f"vspike_{interval}_{vw}", "microstructure", "volume", f"volSpike{vw}", {"vw": vw}, e, x)
        n_cfg += 1

    # 11. Hour seasonality (1h)
    if "hour" in f and interval == "1h":
        hour = f["hour"].to_numpy()
        for h_ent, hold in ((8, 8), (14, 12), (20, 6)):
            pos = np.zeros(len(close))
            hold_left = 0
            for i in range(len(close)):
                if hold_left > 0:
                    hold_left -= 1
                    pos[i] = 1.0
                elif hour[i] == h_ent:
                    pos[i] = 1.0
                    hold_left = hold - 1
            m = eval_pos_np(close, pos, idx, ann)
            hid = f"season_{interval}_h{h_ent}"
            consider(hits, hid, interval, "seasonality", "calendar", f"hour{h_ent} hold{hold}", {"hour": h_ent, "hold": hold}, m)
            if m["sharpe"] >= 0.4:
                ret_map[hid] = m["returns"]
            n_cfg += 1

    print(f"[{interval}] configs={n_cfg} hits={len(hits)} bars={meta['bars']}", flush=True)
    return hits, ret_map


def max_pairwise_corr(ids: list[str], ret_map: dict[str, pd.Series]) -> float:
    mat = pd.DataFrame({i: ret_map[i] for i in ids}).dropna(how="all")
    if mat.shape[1] < 2:
        return 0.0
    c = mat.corr().values
    n = c.shape[0]
    return float(np.nanmax(np.abs(c[np.triu_indices(n, k=1)])))


def select_ensemble(pool: list[Hit], ret_map: dict[str, pd.Series]) -> dict | None:
    pool = sorted(pool, key=lambda h: (-h.sharpe, -h.trades_per_year))
    best = None

    for k in range(4, 8):
        chosen: list[Hit] = []
        ids: list[str] = []
        families: set[str] = set()
        styles: set[str] = set()
        intervals: set[str] = set()

        for h in pool:
            if h.id not in ret_map:
                continue
            if h.family in families or h.style in styles:
                continue
            # prefer mixing intervals
            if len(intervals) >= 2 and h.interval in intervals and len(chosen) >= 2:
                continue
            trial = ids + [h.id]
            if max_pairwise_corr(trial, ret_map) > MAX_PAIR_CORR:
                continue
            chosen.append(h)
            ids.append(h.id)
            families.add(h.family)
            styles.add(h.style)
            intervals.add(h.interval)
            if len(chosen) >= k:
                break

        if len(chosen) < 4:
            continue

        mat = pd.DataFrame({h.id: ret_map[h.id] for h in chosen})
        eq = mat.mean(axis=1).dropna()
        ann = min(ANN_MAP[i] for i in {h.interval for h in chosen})
        sh = float(np.sqrt(ann) * eq.mean() / eq.std())
        cum = (1 + eq).cumprod()
        dd = float((cum / cum.cummax() - 1).min())
        is_r = eq.loc[eq.index < OOS]
        oos_r = eq.loc[eq.index >= OOS]

        def _sh(s: pd.Series) -> float:
            return float(np.sqrt(ann) * s.mean() / s.std()) if len(s) > 50 and s.std() > 0 else 0.0

        res = {
            "k": len(chosen),
            "sharpe": sh,
            "max_dd": dd,
            "sharpe_is": _sh(is_r),
            "sharpe_oos": _sh(oos_r),
            "max_corr": max_pairwise_corr(ids, ret_map),
            "avg_trades_per_year": float(np.mean([h.trades_per_year for h in chosen])),
            "members": [asdict(h) for h in chosen],
            "returns": eq,
        }
        if best is None or (res["sharpe"], res["max_dd"]) > (best["sharpe"], best["max_dd"]):
            best = res
    return best


def main() -> None:
    all_hits: list[Hit] = []
    all_rets: dict[str, pd.Series] = {}
    for interval in ("4h", "8h", "1h"):
        hits, rets = search_interval(interval)
        all_hits.extend(hits)
        all_rets.update(rets)

    all_hits = sorted({h.id: h for h in all_hits}.values(), key=lambda h: -h.sharpe)
    qualifying = [h for h in all_hits if h.sharpe >= 0.9]
    print(f"Total hits={len(all_hits)} sharpe>=0.9={len(qualifying)}", flush=True)

    best = select_ensemble(qualifying if qualifying else all_hits, all_rets)
    out = RUN / "artifacts"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "hf_search_hits.json", "w") as fp:
        json.dump([asdict(h) for h in all_hits[:80]], fp, indent=2)

    if best is None:
        with open(out / "hf_ensemble_result.json", "w") as fp:
            json.dump({"status": "no_ensemble"}, fp)
        print("No diverse ensemble found")
        return

    payload = {k: v for k, v in best.items() if k != "returns"}
    payload["meets_target"] = best["sharpe"] >= 2.0 and best["max_dd"] > -0.15
    with open(out / "hf_ensemble_result.json", "w") as fp:
        json.dump(payload, fp, indent=2)

    print(f"ENSEMBLE k={best['k']} Sharpe={best['sharpe']:.2f} DD={best['max_dd']:.1%} corr={best['max_corr']:.2f} meets={payload['meets_target']}", flush=True)
    for m in best["members"]:
        print(f"  {m['id']}: sharpe={m['sharpe']:.2f} tpy={m['trades_per_year']:.0f} {m['family']}/{m['style']}", flush=True)


if __name__ == "__main__":
    main()
