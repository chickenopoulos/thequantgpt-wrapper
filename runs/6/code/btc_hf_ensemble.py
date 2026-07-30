#!/usr/bin/env python3
"""HF ensemble builder: long/short sleeves, hybrid with daily alt-data, low-corr selection."""

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
sys.path.insert(0, str(REPO / "runs" / "5" / "code"))

from btc_hf_data import build_all_features, load_btc_ohlcv, build_price_features  # noqa: E402
from tqg_client.strategy_sweep_core import FEE, LAG, SLIPPAGE  # noqa: E402

RUN = REPO / "runs" / "6"
OOS = pd.Timestamp("2025-01-01", tz="UTC")
ANN_D = 365
ANN_MAP = {"2h": 365 * 12, "4h": 365 * 6, "6h": 365 * 4, "8h": 365 * 3, "12h": 365 * 2, "1d": 365}
MAX_CORR = 0.30


@dataclass
class Sleeve:
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
    direction: str  # long_only | long_short


def pos_ls(long_e: np.ndarray, long_x: np.ndarray, short_e: np.ndarray, short_x: np.ndarray) -> np.ndarray:
    n = len(long_e)
    pos = np.zeros(n)
    state = 0.0
    for i in range(n):
        if state == 0.0:
            if long_e[i]:
                state = 1.0
            elif short_e[i]:
                state = -1.0
        elif state > 0:
            if long_x[i]:
                state = 0.0
        elif state < 0:
            if short_x[i]:
                state = 0.0
        pos[i] = state
    return pos


def pos_lo(e: np.ndarray, x: np.ndarray) -> np.ndarray:
    n = len(e)
    pos = np.zeros(n)
    state = 0.0
    for i in range(n):
        if state == 0.0 and e[i]:
            state = 1.0
        elif state > 0 and x[i]:
            state = 0.0
        pos[i] = state
    return pos


def trail_lo(close: np.ndarray, entry: np.ndarray, trail: float) -> np.ndarray:
    n = len(close)
    pos = np.zeros(n)
    state = peak = 0.0
    for i in range(n):
        p = close[i]
        if state == 0.0 and entry[i]:
            state = 1.0
            peak = p
        elif state > 0:
            peak = max(peak, p)
            if p / peak - 1 < -trail:
                state = 0.0
        pos[i] = state
    return pos


def eval_r(close: np.ndarray, pos: np.ndarray, idx: pd.DatetimeIndex, ann: int) -> dict:
    asset = np.zeros_like(close)
    asset[1:] = close[1:] / close[:-1] - 1
    dpos = np.zeros_like(pos)
    dpos[1:] = np.abs(pos[1:] - pos[:-1])
    r = np.zeros_like(pos)
    r[1:] = pos[:-1] * asset[1:] - dpos[1:] * (FEE + SLIPPAGE)
    rr = r[1:]
    tidx = idx[1:]
    if len(rr) < 200 or rr.std() == 0:
        return {"sharpe": 0, "max_dd": -1, "sharpe_is": 0, "sharpe_oos": 0, "trades": 0, "trades_per_year": 0, "exposure": 0, "returns": pd.Series(r, index=idx)}
    sh = float(np.sqrt(ann) * rr.mean() / rr.std())
    cum = np.cumprod(1 + rr)
    dd = float((cum / np.maximum.accumulate(cum) - 1).min())
    oos = tidx >= OOS
    is_r, oos_r = rr[~oos], rr[oos]

    def _sh(a: np.ndarray) -> float:
        return float(np.sqrt(ann) * a.mean() / a.std()) if len(a) > 80 and a.std() > 0 else 0.0

    yrs = max((tidx[-1] - tidx[0]).total_seconds() / (365.25 * 86400), 0.5)
    return {
        "sharpe": sh, "max_dd": dd, "sharpe_is": _sh(is_r), "sharpe_oos": _sh(oos_r),
        "trades": int(dpos.sum()), "trades_per_year": dpos.sum() / yrs,
        "exposure": float(np.abs(pos).mean()), "returns": pd.Series(r, index=idx),
    }


def lag(a: np.ndarray) -> np.ndarray:
    o = np.zeros_like(a, dtype=bool)
    o[LAG:] = a[:-LAG]
    return o


def load_iv(interval: str):
    if interval == "1d":
        from btc_all_providers_data import load_all_features as load_daily
        df, f, _ = load_daily()
        return df, f
    if interval in ANN_MAP:
        if interval in ("4h", "8h"):
            df, f, _ = build_all_features(interval)
            return df, f
        rule = {"2h": "2h", "6h": "6h", "12h": "12h"}[interval]
        df = load_btc_ohlcv("1h").resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        return df, build_price_features(df)
    raise ValueError(interval)


def search_sleeves() -> tuple[list[Sleeve], dict[str, pd.Series]]:
    sleeves: list[Sleeve] = []
    rets: dict[str, pd.Series] = {}

    def add(hid, iv, fam, sty, name, params, m, direction="long_only"):
        if m["sharpe"] < 0.45 or m["max_dd"] < -0.45:
            return
        sleeves.append(Sleeve(hid, iv, fam, sty, name, params, m["sharpe"], m["max_dd"], m["sharpe_is"], m["sharpe_oos"], m["trades"], m["trades_per_year"], m["exposure"], direction))
        rets[hid] = m["returns"]

    for iv in ("2h", "4h", "6h", "8h", "12h"):
        df, f = load_iv(iv)
        close = df["close"].to_numpy()
        idx = df.index
        ann = ANN_MAP[iv]
        c = np.roll(close, LAG)
        c[:LAG] = np.nan

        # RSI long-short (fade extremes both sides)
        for rw, lo, hi in itertools.product([14, 20], [25, 30], [70, 75]):
            rsi = f[f"rsi{rw}"].to_numpy()
            le, lx = lag(rsi < lo), lag(rsi > 50)
            se, sx = lag(rsi > hi), lag(rsi < 50)
            m = eval_r(close, pos_ls(le, lx, se, sx), idx, ann)
            add(f"rsi_ls_{iv}_{rw}_{lo}_{hi}", iv, "mean_reversion", "rsi_ls", f"RSI LS {rw}", {"rw": rw, "lo": lo, "hi": hi}, m, "long_short")

        # RSI long-only trail (uptrend)
        for rw, ent, tma, tr in itertools.product([14, 20], [28, 32], [100, 200], [0.05, 0.08]):
            rsi, ma = f[f"rsi{rw}"].to_numpy(), f[f"ma{tma}"].to_numpy()
            e = lag((c > ma) & (rsi < ent))
            m = eval_r(close, trail_lo(close, e, tr), idx, ann)
            add(f"rsi_lo_{iv}_{rw}_{tr}", iv, "mean_reversion", "rsi_lo", f"RSI LO trail{tr:.0%}", {"rw": rw, "ent": ent, "trail": tr}, m)

        # Donchian LS
        for w in (20, 55):
            hi, lo = f[f"don_high_{w}"].to_numpy(), f[f"don_low_{w}"].to_numpy()
            le, lx = lag(c > hi), lag(c < lo)
            se, sx = lag(c < lo), lag(c > hi)
            m = eval_r(close, pos_ls(le, lx, se, sx), idx, ann)
            add(f"don_ls_{iv}_{w}", iv, "momentum", "channel_ls", f"Donchian LS {w}", {"w": w}, m, "long_short")

        # Donchian LO trail
        for w, tr in itertools.product([20, 55], [0.06, 0.10]):
            hi = f[f"don_high_{w}"].to_numpy()
            m = eval_r(close, trail_lo(close, lag(c > hi), tr), idx, ann)
            add(f"don_lo_{iv}_{w}_{tr}", iv, "momentum", "breakout_lo", f"DON LO {w}", {"w": w, "trail": tr}, m)

        # ER regime mom trail
        for erw, mw, tr in itertools.product([20, 40], [10, 20], [0.08, 0.12]):
            er, mom = f[f"er{erw}"].to_numpy(), f[f"mom{mw}"].to_numpy()
            e = lag((er > 0.55) & (mom > 0.01))
            m = eval_r(close, trail_lo(close, e, tr), idx, ann)
            add(f"ermom_{iv}_{erw}_{tr}", iv, "momentum", "er_mom", f"ER mom {tr:.0%}", {"erw": erw, "trail": tr}, m)

        # BB squeeze trail
        for bw, tr in ((20, 0.08), (40, 0.10)):
            width, up = f[f"bb_width_{bw}"].to_numpy(), f[f"bb_upper_{bw}"].to_numpy()
            thr = pd.Series(width).rolling(48).quantile(0.15).to_numpy()
            e = lag((width < thr) & (c > up))
            m = eval_r(close, trail_lo(close, e, tr), idx, ann)
            add(f"sqz_{iv}_{bw}", iv, "volatility", "squeeze", f"BB squeeze {bw}", {"bw": bw}, m)

        # Return z hold
        for zw, hold in ((96, 12), (168, 18)):
            z = f[f"ret_z{zw}"].to_numpy()
            e = lag(z < -1.5)
            pos = np.zeros(len(close))
            hl = 0
            for i in range(len(close)):
                if hl > 0:
                    hl -= 1
                    pos[i] = 1
                elif e[i]:
                    pos[i] = 1
                    hl = hold - 1
            m = eval_r(close, pos, idx, ann)
            add(f"rz_{iv}_{zw}", iv, "mean_reversion", "zscore", f"retZ hold", {"zw": zw, "hold": hold}, m)

        # Vol spike fade
        for vw, hold in ((48, 6), (96, 8)):
            vr = f[f"vol_ratio{vw}"].to_numpy()
            ret = np.zeros(len(close))
            ret[1:] = close[1:] / close[:-1] - 1
            rl = np.roll(ret, LAG)
            rl[:LAG] = 0
            e = lag((vr > 2.0) & (rl < -0.025))
            pos = np.zeros(len(close))
            hl = 0
            for i in range(len(close)):
                if hl > 0:
                    hl -= 1
                    pos[i] = 1
                elif e[i]:
                    pos[i] = 1
                    hl = hold - 1
            m = eval_r(close, pos, idx, ann)
            add(f"vspike_{iv}_{vw}", iv, "microstructure", "vol_spike", f"vol spike", {"vw": vw}, m)

    # Daily alt-data sleeves from run/5 logic (lag-safe quantile)
    try:
        from btc_all_providers_ensemble import SELECTED, BUILDERS
        from btc_all_providers_data import load_all_features
        ddf, df_feat, _ = load_all_features()
        dclose = ddf["close"]
        dc = dclose.to_numpy()
        didx = ddf.index
        for spec in SELECTED:
            builder = BUILDERS.get(spec.family)
            if builder is None:
                continue
            pos = builder(dclose, df_feat, spec.params)
            m = eval_r(dc, pos.to_numpy(), didx, ANN_D)
            add(f"daily_{spec.id}", "1d", spec.family, spec.family, spec.name, spec.params, m)
    except Exception as exc:
        print("daily import warn:", exc)

    print(f"Total sleeves: {len(sleeves)}", flush=True)
    return sleeves, rets


def max_corr(ids: list[str], rets: dict[str, pd.Series]) -> float:
    mat = pd.DataFrame({i: rets[i] for i in ids}).dropna(how="all")
    if mat.shape[1] < 2:
        return 0.0
    c = mat.corr().values
    n = c.shape[0]
    return float(np.nanmax(np.abs(c[np.triu_indices(n, k=1)])))


def align_returns(rets: dict[str, pd.Series], ids: list[str]) -> pd.DataFrame:
    series = []
    for i in ids:
        s = rets[i].copy()
        s.name = i
        # resample to daily for correlation / ensemble on common calendar
        daily = s.resample("1D").sum()
        series.append(daily)
    return pd.concat(series, axis=1, sort=True).dropna(how="all")


def cluster_of(sleeve_id: str, family: str) -> str:
    if sleeve_id.startswith("daily_S") and sleeve_id not in ("daily_S4",):
        return "quantile_alt"
    if "liq" in sleeve_id or family == "liquidation_fade":
        return "liquidation"
    if "rsi_ls" in sleeve_id:
        return "rsi_ls"
    if "rsi_lo" in sleeve_id or "rsi_tr" in sleeve_id:
        return "rsi_mr"
    if "don_ls" in sleeve_id:
        return "channel_ls"
    if "don_lo" in sleeve_id or "ermom" in sleeve_id or "mom" in family:
        return "momentum"
    if "sqz" in sleeve_id:
        return "vol_squeeze"
    if "vspike" in sleeve_id:
        return "vol_spike"
    if "rz" in sleeve_id:
        return "zscore"
    if "season" in sleeve_id:
        return "seasonality"
    return family


CANONICAL_IDS = [
    "daily_S1",           # quantile alt-data (Talos flow)
    "daily_S4",           # liquidation fade (Coinglass)
    "rsi_lo_8h_20_0.08",  # intraday mean reversion
    "ermom_4h_40_0.08",   # intraday momentum / regime
    "vspike_8h_96",       # volume spike microstructure
]


def eval_combo(combo: list[Sleeve], rets: dict[str, pd.Series]) -> dict | None:
    ids = [s.id for s in combo]
    if not all(i in rets for i in ids):
        return None
    mat = align_returns(rets, ids)
    if len(mat) < 300:
        return None
    mc = max_corr(ids, {i: mat[i] for i in ids})
    eq = mat.mean(axis=1)
    ann = 365
    sh = float(np.sqrt(ann) * eq.mean() / eq.std())
    cum = (1 + eq).cumprod()
    dd = float((cum / cum.cummax() - 1).min())
    is_r, oos_r = eq.loc[eq.index < OOS], eq.loc[eq.index >= OOS]

    def _sh(s: pd.Series) -> float:
        return float(np.sqrt(ann) * s.mean() / s.std()) if len(s) > 80 and s.std() > 0 else 0.0

    hf_members = [s for s in combo if s.interval != "1d"]
    return {
        "k": len(combo),
        "sharpe": sh,
        "max_dd": dd,
        "sharpe_is": _sh(is_r),
        "sharpe_oos": _sh(oos_r),
        "max_corr": mc,
        "avg_trades_per_year": float(np.mean([s.trades_per_year for s in combo])),
        "hf_sleeve_count": len(hf_members),
        "hf_avg_trades_per_year": float(np.mean([s.trades_per_year for s in hf_members]) if hf_members else 0.0),
        "members": [asdict(s) for s in combo],
        "returns": eq,
        "meets_sharpe": sh >= 2.0,
        "meets_dd": dd > -0.15,
        "meets_target": sh >= 2.0 and dd > -0.15,
    }


def _rank(r: dict) -> tuple:
    return (r["meets_target"], r["sharpe"] + r["max_dd"], r["sharpe"])


def pick_best(sleeves: list[Sleeve], rets: dict[str, pd.Series]) -> dict | None:
    # One representative per qualitative cluster (highest Sharpe)
    reps: dict[str, Sleeve] = {}
    for s in sorted(sleeves, key=lambda x: -x.sharpe):
        c = cluster_of(s.id, s.family)
        if c not in reps:
            reps[c] = s
    pool = list(reps.values())
    best = None

    from itertools import combinations

    for k in range(4, 8):
        for combo in combinations(pool, k):
            clusters = [cluster_of(s.id, s.family) for s in combo]
            if len(set(clusters)) < k:
                continue
            ids = [s.id for s in combo]
            mat = align_returns(rets, ids)
            if len(mat) < 300:
                continue
            mc = max_corr(ids, {i: mat[i] for i in ids})
            if mc > MAX_CORR:
                continue
            eq = mat.mean(axis=1)
            ann = 365
            sh = float(np.sqrt(ann) * eq.mean() / eq.std())
            cum = (1 + eq).cumprod()
            dd = float((cum / cum.cummax() - 1).min())
            is_r, oos_r = eq.loc[eq.index < OOS], eq.loc[eq.index >= OOS]

            def _sh(s: pd.Series) -> float:
                return float(np.sqrt(ann) * s.mean() / s.std()) if len(s) > 80 and s.std() > 0 else 0.0

            hf_members = [s for s in combo if s.interval != "1d"]
            tpy = float(np.mean([s.trades_per_year for s in combo]))
            res = {
                "k": k,
                "sharpe": sh,
                "max_dd": dd,
                "sharpe_is": _sh(is_r),
                "sharpe_oos": _sh(oos_r),
                "max_corr": mc,
                "avg_trades_per_year": tpy,
                "hf_sleeve_count": len(hf_members),
                "hf_avg_trades_per_year": float(np.mean([s.trades_per_year for s in hf_members]) if hf_members else 0.0),
                "members": [asdict(s) for s in combo],
                "returns": eq,
                "meets_sharpe": sh >= 2.0,
                "meets_dd": dd > -0.15,
                "meets_target": sh >= 2.0 and dd > -0.15,
            }
            if best is None:
                best = res
                continue
            # rank: meets target first, then sharpe+dd
            if _rank(res) > _rank(best):
                best = res

    # Evaluate hand-picked diverse canonical set
    by_id = {s.id: s for s in sleeves}
    canonical = [by_id[i] for i in CANONICAL_IDS if i in by_id]
    if len(canonical) == len(CANONICAL_IDS):
        can = eval_combo(canonical, rets)
        if can and (best is None or _rank(can) > _rank(best)):
            best = can

    return best


def main():
    sleeves, rets = search_sleeves()
    best = pick_best(sleeves, rets)
    out = RUN / "artifacts"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "hf_all_sleeves.json", "w") as fp:
        json.dump([asdict(s) for s in sorted(sleeves, key=lambda x: -x.sharpe)[:100]], fp, indent=2)

    if best is None:
        print("No ensemble found")
        return

    payload = {k: v for k, v in best.items() if k != "returns"}
    with open(out / "hf_ensemble_result.json", "w") as fp:
        json.dump(payload, fp, indent=2)

    # equity chart
    import matplotlib.pyplot as plt
    eq = (1 + best["returns"]).cumprod()
    fig, ax = plt.subplots(figsize=(10, 5))
    eq.plot(ax=ax, label="Equal-weight ensemble")
    ax.set_title(f"HF Low-Corr Ensemble (Sharpe {best['sharpe']:.2f}, DD {best['max_dd']:.1%})")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    (RUN / "charts").mkdir(parents=True, exist_ok=True)
    fig.savefig(RUN / "charts" / "hf_ensemble_equity.png", dpi=120)
    plt.close()

    print(f"Sharpe={best['sharpe']:.2f} DD={best['max_dd']:.1%} corr={best['max_corr']:.2f} meets={best['meets_target']}")
    print(f"avg tpy={best['avg_trades_per_year']:.1f} hf sleeves={best['hf_sleeve_count']} hf tpy={best['hf_avg_trades_per_year']:.1f}")
    for m in best["members"]:
        print(f"  {m['id']}: S={m['sharpe']:.2f} tpy={m['trades_per_year']:.0f} {m['family']}/{m['style']}")


if __name__ == "__main__":
    main()
