#!/usr/bin/env python3
"""Expanded HF search: trail stops, regime gates, diverse families, low-corr ensemble."""

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
ANN_MAP = {"1h": 365 * 24, "2h": 365 * 12, "4h": 365 * 6, "6h": 365 * 4, "8h": 365 * 3, "12h": 365 * 2}
MAX_PAIR_CORR = 0.28


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
    trades_per_year: float
    exposure: float


def pos_from_signals(entries: np.ndarray, exits: np.ndarray) -> np.ndarray:
    n = len(entries)
    pos = np.zeros(n)
    state = 0.0
    for i in range(n):
        if state == 0.0 and entries[i]:
            state = 1.0
        elif state > 0.0 and exits[i]:
            state = 0.0
        pos[i] = state
    return pos


def trail_pos_np(close: np.ndarray, entry: np.ndarray, trail_pct: float) -> np.ndarray:
    n = len(close)
    pos = np.zeros(n)
    state = peak = 0.0
    for i in range(n):
        p = close[i]
        if state == 0.0 and entry[i]:
            state = 1.0
            peak = p
        elif state > 0.0:
            peak = max(peak, p)
            if p / peak - 1.0 < -trail_pct:
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
    if len(rr) < 300 or rr.std() == 0:
        return {"sharpe": 0.0, "max_dd": -1.0, "sharpe_is": 0.0, "sharpe_oos": 0.0, "trades": 0, "trades_per_year": 0.0, "exposure": 0.0, "returns": pd.Series(r, index=index)}
    sh = float(np.sqrt(ann) * rr.mean() / rr.std())
    cum = np.cumprod(1 + rr)
    dd = float((cum / np.maximum.accumulate(cum) - 1).min())
    oos_mask = idx >= OOS
    is_r, oos_r = rr[~oos_mask], rr[oos_mask]

    def _sh(s: np.ndarray) -> float:
        return float(np.sqrt(ann) * s.mean() / s.std()) if len(s) > 80 and s.std() > 0 else 0.0

    years = max((idx[-1] - idx[0]).total_seconds() / (365.25 * 86400), 0.5)
    trades = int(dpos.sum())
    return {
        "sharpe": sh, "max_dd": dd, "sharpe_is": _sh(is_r), "sharpe_oos": _sh(oos_r),
        "trades": trades, "trades_per_year": trades / years, "exposure": float(pos.mean()),
        "returns": pd.Series(r, index=index),
    }


def lag_bool(arr: np.ndarray) -> np.ndarray:
    out = np.zeros(len(arr), dtype=bool)
    out[LAG:] = arr[:-LAG]
    return out


def record(hits: list[Hit], ret_map: dict, hid: str, interval: str, family: str, style: str, name: str, params: dict, m: dict) -> None:
    if m["sharpe"] >= 0.55 and m["max_dd"] > -0.35 and m["trades"] >= 15:
        hits.append(Hit(hid, interval, family, style, name, params, m["sharpe"], m["max_dd"], m["sharpe_is"], m["sharpe_oos"], m["trades"], m["trades_per_year"], m["exposure"]))
        ret_map[hid] = m["returns"]


def load_interval(interval: str):
    if interval in ("2h", "6h", "12h"):
        from btc_hf_data import load_btc_ohlcv, build_price_features
        rule = {"2h": "2h", "6h": "6h", "12h": "12h"}[interval]
        df = load_btc_ohlcv("1h").resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        f = build_price_features(df)
        meta = {"bars": len(df), "interval": interval}
        return df, f, meta
    return build_all_features(interval)


def search(interval: str) -> tuple[list[Hit], dict[str, pd.Series]]:
    df, f, meta = load_interval(interval)
    close = df["close"].to_numpy()
    idx = df.index
    ann = ANN_MAP[interval]
    hits: list[Hit] = []
    ret_map: dict[str, pd.Series] = {}
    c = np.roll(close, LAG)
    c[:LAG] = np.nan
    n = 0

    def go(hid, family, style, name, params, pos):
        nonlocal n
        n += 1
        m = eval_pos_np(close, pos, idx, ann)
        record(hits, ret_map, hid, interval, family, style, name, params, m)

    # A. RSI MR + trail
    for rsi_w, ent, tma, trail in itertools.product([14, 20], [25, 30, 35], [100, 200], [0.04, 0.06, 0.08]):
        rsi = f[f"rsi{rsi_w}"].to_numpy()
        ma = f[f"ma{tma}"].to_numpy()
        e = lag_bool((c > ma) & (rsi < ent))
        pos = trail_pos_np(close, e, trail)
        go(f"rsi_tr_{interval}_{rsi_w}_{ent}_{trail}", "mean_reversion", "oscillator", f"RSI{rsi_w} trail{trail:.0%}", {"rsi_w": rsi_w, "ent": ent, "tma": tma, "trail": trail}, pos)

    # B. BB fade + trail
    for bw, trail in itertools.product([20, 40], [0.04, 0.06, 0.08]):
        lo, mid, ma200 = f[f"bb_lower_{bw}"].to_numpy(), f[f"bb_mid_{bw}"].to_numpy(), f["ma200"].to_numpy()
        e = lag_bool((c < lo) & (c > ma200))
        pos = trail_pos_np(close, e, trail)
        go(f"bb_tr_{interval}_{bw}_{trail}", "mean_reversion", "band", f"BB{bw} trail{trail:.0%}", {"bw": bw, "trail": trail}, pos)

    # C. Return z MR + fixed hold
    for zw, z_ent, hold in itertools.product([48, 96, 168], [-2.0, -1.5], [6, 12, 24]):
        z = f[f"ret_z{zw}"].to_numpy()
        e = lag_bool(z < z_ent)
        pos = np.zeros(len(close))
        hold_left = 0
        for i in range(len(close)):
            if hold_left > 0:
                hold_left -= 1
                pos[i] = 1.0
            elif e[i]:
                pos[i] = 1.0
                hold_left = hold - 1
        go(f"rz_hold_{interval}_{zw}_{hold}", "mean_reversion", "zscore", f"retZ{zw} hold{hold}", {"zw": zw, "z_ent": z_ent, "hold": hold}, pos)

    # D. Donchian + trail
    for w, trail in itertools.product([20, 55, 100], [0.05, 0.08, 0.10, 0.12]):
        hi = f[f"don_high_{w}"].to_numpy()
        e = lag_bool(c > hi)
        pos = trail_pos_np(close, e, trail)
        go(f"don_tr_{interval}_{w}_{trail}", "momentum", "breakout", f"DON{w} trail{trail:.0%}", {"w": w, "trail": trail}, pos)

    # E. EMA cross + vol gate
    for fast, slow, vw in itertools.product([12, 24], [48, 96], [20, 40]):
        ef, es = f[f"ema{fast}"].to_numpy(), f[f"ema{slow}"].to_numpy()
        vol = f[f"vol{vw}"].to_numpy()
        vmed = pd.Series(vol).rolling(vw * 4).median().to_numpy()
        e = lag_bool((ef > es) & (vol < vmed))
        x = lag_bool(ef < es)
        go(f"ema_vol_{interval}_{fast}_{slow}", "momentum", "trend", f"EMA{fast}/{slow} lowvol", {"fast": fast, "slow": slow, "vw": vw}, pos_from_signals(e, x))

    # F. TSMOM + trail
    for mw, trail in itertools.product([10, 20, 40], [0.06, 0.10, 0.14]):
        mom, ma = f[f"mom{mw}"].to_numpy(), f["ma200"].to_numpy()
        e = lag_bool((mom > 0.01) & (c > ma))
        pos = trail_pos_np(close, e, trail)
        go(f"mom_tr_{interval}_{mw}_{trail}", "momentum", "roc", f"MOM{mw} trail{trail:.0%}", {"mw": mw, "trail": trail}, pos)

    # G. BB squeeze breakout + trail
    for bw, trail in itertools.product([20, 40], [0.06, 0.10]):
        width, upper = f[f"bb_width_{bw}"].to_numpy(), f[f"bb_upper_{bw}"].to_numpy()
        thr = pd.Series(width).rolling(48).quantile(0.15).to_numpy()
        e = lag_bool((width < thr) & (c > upper))
        pos = trail_pos_np(close, e, trail)
        go(f"sqz_tr_{interval}_{bw}", "volatility", "squeeze", f"SQZ{bw}", {"bw": bw, "trail": trail}, pos)

    # H. ER chop MR + hold
    for erw, hold in itertools.product([20, 40], [8, 16, 32]):
        er, rsi = f[f"er{erw}"].to_numpy(), f["rsi14"].to_numpy()
        e = lag_bool((er < 0.35) & (rsi < 28))
        pos = np.zeros(len(close))
        hold_left = 0
        for i in range(len(close)):
            if hold_left > 0:
                hold_left -= 1
                pos[i] = 1.0
            elif e[i]:
                pos[i] = 1.0
                hold_left = hold - 1
        go(f"er_mr_hold_{interval}_{erw}_{hold}", "mean_reversion", "regime", f"ER{erw} hold{hold}", {"erw": erw, "hold": hold}, pos)

    # I. ER trend mom + trail
    for erw, mw, trail in itertools.product([20, 40], [10, 20], [0.08, 0.12]):
        er, mom = f[f"er{erw}"].to_numpy(), f[f"mom{mw}"].to_numpy()
        e = lag_bool((er > 0.55) & (mom > 0.01))
        pos = trail_pos_np(close, e, trail)
        go(f"er_mom_tr_{interval}_{erw}_{trail}", "momentum", "regime", f"ERmom trail{trail:.0%}", {"erw": erw, "mw": mw, "trail": trail}, pos)

    # J. Volume spike fade + hold
    for vw, hold in itertools.product([48, 96], [4, 8, 12]):
        vr = f[f"vol_ratio{vw}"].to_numpy()
        ret = np.zeros(len(close))
        ret[1:] = close[1:] / close[:-1] - 1
        rl = np.roll(ret, LAG)
        rl[:LAG] = 0
        e = lag_bool((vr > 2.0) & (rl < -0.025))
        pos = np.zeros(len(close))
        hold_left = 0
        for i in range(len(close)):
            if hold_left > 0:
                hold_left -= 1
                pos[i] = 1.0
            elif e[i]:
                pos[i] = 1.0
                hold_left = hold - 1
        go(f"vspike_{interval}_{vw}_{hold}", "microstructure", "volume", f"Vspike hold{hold}", {"vw": vw, "hold": hold}, pos)

    # K. Hour seasonality (1h/2h)
    if "hour" in f and interval in ("1h", "2h"):
        hour = f["hour"].to_numpy()
        for h_ent, hold in itertools.product([7, 8, 13, 14, 20, 21], [4, 8, 12]):
            pos = np.zeros(len(close))
            hold_left = 0
            for i in range(len(close)):
                if hold_left > 0:
                    hold_left -= 1
                    pos[i] = 1.0
                elif hour[i] == h_ent:
                    pos[i] = 1.0
                    hold_left = hold - 1
            go(f"season_{interval}_h{h_ent}_{hold}", "seasonality", "calendar", f"H{h_ent} hold{hold}", {"hour": h_ent, "hold": hold}, pos)

    print(f"[{interval}] cfgs={n} hits={len(hits)}", flush=True)
    return hits, ret_map


def max_corr(ids: list[str], ret_map: dict[str, pd.Series]) -> float:
    mat = pd.DataFrame({i: ret_map[i] for i in ids}).dropna(how="all")
    if mat.shape[1] < 2:
        return 0.0
    c = mat.corr().values
    n = c.shape[0]
    return float(np.nanmax(np.abs(c[np.triu_indices(n, k=1)])))


def pick_ensemble(pool: list[Hit], ret_map: dict[str, pd.Series]) -> dict | None:
    pool = sorted(pool, key=lambda h: (-h.sharpe, h.max_dd), reverse=True)
    best = None
    for k in range(4, 9):
        chosen: list[Hit] = []
        ids: list[str] = []
        fam, sty = set(), set()
        for h in pool:
            if h.id not in ret_map:
                continue
            if h.family in fam or h.style in sty:
                continue
            trial = ids + [h.id]
            if max_corr(trial, ret_map) > MAX_PAIR_CORR:
                continue
            chosen.append(h)
            ids.append(h.id)
            fam.add(h.family)
            sty.add(h.style)
            if len(chosen) >= k:
                break
        if len(chosen) < 4:
            continue
        eq = pd.DataFrame({h.id: ret_map[h.id] for h in chosen}).mean(axis=1).dropna()
        ann = min(ANN_MAP[h.interval] for h in chosen)
        sh = float(np.sqrt(ann) * eq.mean() / eq.std())
        cum = (1 + eq).cumprod()
        dd = float((cum / cum.cummax() - 1).min())
        is_r, oos_r = eq.loc[eq.index < OOS], eq.loc[eq.index >= OOS]

        def _sh(s: pd.Series) -> float:
            return float(np.sqrt(ann) * s.mean() / s.std()) if len(s) > 80 and s.std() > 0 else 0.0

        res = {
            "k": len(chosen), "sharpe": sh, "max_dd": dd,
            "sharpe_is": _sh(is_r), "sharpe_oos": _sh(oos_r),
            "max_corr": max_corr(ids, ret_map),
            "avg_trades_per_year": float(np.mean([h.trades_per_year for h in chosen])),
            "members": [asdict(h) for h in chosen],
            "returns": eq,
        }
        score = (sh if sh >= 2.0 and dd > -0.15 else sh - 5 * max(0, -dd - 0.15) - max(0, 2 - sh))
        best_score = (best["sharpe"] if best and best["sharpe"] >= 2 and best["max_dd"] > -0.15 else -999) if best else -999
        if best is None or score > best_score:
            best = res
    return best


def main():
    all_hits: list[Hit] = []
    all_rets: dict[str, pd.Series] = {}
    for iv in ("4h", "6h", "8h", "12h", "2h", "1h"):
        h, r = search(iv)
        all_hits.extend(h)
        all_rets.update(r)

    uniq = {x.id: x for x in all_hits}
    all_hits = sorted(uniq.values(), key=lambda h: -h.sharpe)
    best = pick_ensemble([h for h in all_hits if h.sharpe >= 0.5], all_rets)

    out = RUN / "artifacts"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "hf_search_hits.json", "w") as fp:
        json.dump([asdict(h) for h in all_hits[:120]], fp, indent=2)

    if best is None:
        print("No ensemble")
        return

    payload = {k: v for k, v in best.items() if k != "returns"}
    payload["meets_target"] = best["sharpe"] >= 2.0 and best["max_dd"] > -0.15
    with open(out / "hf_ensemble_result.json", "w") as fp:
        json.dump(payload, fp, indent=2)
    print(f"ENSEMBLE Sharpe={best['sharpe']:.2f} DD={best['max_dd']:.1%} corr={best['max_corr']:.2f} target={payload['meets_target']}")
    for m in best["members"]:
        print(f"  {m['id']}: S={m['sharpe']:.2f} DD={m['max_dd']:.1%} tpy={m['trades_per_year']:.0f} {m['family']}/{m['style']}")


if __name__ == "__main__":
    main()
