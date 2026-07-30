#!/usr/bin/env python3
"""Exhaustive BTC strategy search across ALL data providers.

Providers: Talos (OHLCV + 149 on-chain metrics), Coinglass (18+ daily series),
Binance futures OHLCV, Hyperliquid futures OHLCV.

Target: Sharpe >= 1.0, MaxDD < 25%, min 5 trades, pure binary signals.
"""

from __future__ import annotations

import itertools
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import vectorbt as vbt

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "runs" / "5" / "code"))

from btc_all_providers_data import load_all_features  # noqa: E402
from tqg_client.strategy_sweep_core import FEE, LAG, OOS, SLIPPAGE, efficiency_ratio  # noqa: E402

RUN = REPO / "runs" / "5"
ANN = 365
MIN_TRADES = 5


@dataclass
class Hit:
    provider: str
    family: str
    name: str
    params: dict
    sharpe: float
    max_dd: float
    sharpe_is: float
    sharpe_oos: float
    trades: int
    exposure: float


def trail_pos(close: pd.Series, entry: pd.Series, trail_pct: float) -> pd.Series:
    pos = pd.Series(0.0, index=close.index)
    state = peak = 0.0
    en = entry.fillna(False).astype(bool)
    for t in close.index:
        sig = en.loc[t]
        p = float(close.loc[t])
        if state == 0.0 and sig:
            state = 1.0
            peak = p
        elif state > 0:
            peak = max(peak, p)
            if (p / peak - 1) < -trail_pct or not sig:
                state = 0.0
        pos.loc[t] = state
    return pos


def pos_sig(entries: pd.Series, exits: pd.Series) -> pd.Series:
    idx = entries.index
    pos = pd.Series(0.0, index=idx)
    state = 0.0
    en = entries.fillna(False).astype(bool)
    ex = exits.fillna(False).astype(bool)
    for t in idx:
        if state == 0.0 and en.loc[t]:
            state = 1.0
        elif state > 0 and ex.loc[t]:
            state = 0.0
        pos.loc[t] = state
    return pos


def eval_pos(close: pd.Series, pos: pd.Series) -> dict:
    r = pos.shift(1).fillna(0) * close.pct_change().fillna(0) - pos.diff().abs().fillna(0) * (FEE + SLIPPAGE)
    rr = r.dropna()
    if len(rr) < 30 or rr.std() == 0:
        return {"sharpe": 0.0, "max_dd": 0.0, "sharpe_is": 0.0, "sharpe_oos": 0.0, "trades": 0, "exposure": 0.0}
    sh = float(np.sqrt(ANN) * rr.mean() / rr.std())
    cum = (1 + rr).cumprod()
    dd = float((cum / cum.cummax() - 1).min())
    is_r = rr.loc[rr.index < OOS]
    oos_r = rr.loc[rr.index >= OOS]

    def _sh(s: pd.Series) -> float:
        return float(np.sqrt(ANN) * s.mean() / s.std()) if len(s) > 10 and s.std() > 0 else 0.0

    return {
        "sharpe": sh,
        "max_dd": dd,
        "sharpe_is": _sh(is_r),
        "sharpe_oos": _sh(oos_r),
        "trades": int(pos.diff().abs().fillna(0).gt(0).sum()),
        "exposure": float(pos.abs().mean()),
    }


def consider(hits: list[Hit], provider: str, family: str, name: str, params: dict, m: dict) -> None:
    if m["sharpe"] >= 1.0 and m["max_dd"] > -0.25 and m["trades"] >= MIN_TRADES:
        hits.append(Hit(provider, family, name, params, m["sharpe"], m["max_dd"], m["sharpe_is"], m["sharpe_oos"], m["trades"], m["exposure"]))


def search_talos_onchain(close: pd.Series, f: dict, hits: list[Hit]) -> int:
    n = 0
    ma200 = f["ma200"]
    trend = close.shift(LAG) > ma200

    presets = [
        ("CapMVRVZ", [(-1.5, -1.0, -0.5), (1.5, 2.0, 2.5)]),
        ("CapMVRVCur", [(0.8, 1.0, 1.2), (2.0, 2.5, 3.0)]),
        ("NUPL", [(0.15, 0.25, 0.35), (0.65, 0.75, 0.85)]),
        ("SOPR", [(0.95, 0.98, 1.0), (1.02, 1.05, 1.10)]),
        ("FlowNetExUSD", [(-1e9, -5e8, -1e8), (1e8, 5e8, 1e9)]),
        ("futures_cumulative_funding_rate_all_margin_rolling_30d", [(-0.05, -0.02, 0), (0.02, 0.05, 0.10)]),
        ("open_interest_reported_future_perpetual_usd", [(-0.05, -0.02, 0), (0.05, 0.10, 0.15)]),
        ("VtyDayRet30d", [(0.3, 0.5, 0.7), (1.0, 1.5, 2.0)]),
        ("AdrActCnt", [(-0.05, 0, 0.05), (0.05, 0.10, 0.15)]),
    ]
    for col, (ents, exs) in presets:
        key = f"talos_{col}"
        if key not in f:
            continue
        s = f[key]
        for ent in ents:
            for ex in exs:
                for gate in [False, True]:
                    e = (s < ent).fillna(False)
                    x = (s > ex).fillna(False)
                    if gate:
                        e = e & trend
                    pos = pos_sig(e, x)
                    m = eval_pos(close, pos)
                    n += 1
                    consider(hits, "talos", "onchain_threshold", f"{col}<{ent}/{ex}{'+MA' if gate else ''}", {"col": col, "ent": ent, "ex": ex, "gate": gate}, m)
                    for trail in [0.08, 0.10, 0.12]:
                        pos_t = trail_pos(close, e, trail)
                        m_t = eval_pos(close, pos_t)
                        n += 1
                        consider(hits, "talos", "onchain_trail", f"{col}<{ent}+trail{trail:.0%}", {"col": col, "ent": ent, "trail": trail, "gate": gate}, m_t)

    # SOPR capitulation 7d
    if "talos_SOPR" in f:
        s = f["talos_SOPR"]
        below = (s < 1).rolling(7).sum() >= 5
        for gate in [False, True]:
            e = below.shift(LAG).fillna(False)
            if gate:
                e = e & trend
            x = (s > 1.02).fillna(False)
            pos = pos_sig(e, x)
            m = eval_pos(close, pos)
            n += 1
            consider(hits, "talos", "sopr_capitulation", f"SOPR7d{'+MA' if gate else ''}", {"gate": gate}, m)

    # Realized price support
    if "talos_CapRealUSD" in f:
        r = f["talos_CapRealUSD"]
        for mult in [1.02, 1.05, 1.08]:
            e = (close.shift(LAG) < r * mult).fillna(False)
            x = (close.shift(LAG) > r * 1.15).fillna(False)
            pos = pos_sig(e, x)
            m = eval_pos(close, pos)
            n += 1
            consider(hits, "talos", "realized_price", f"price<real*{mult}", {"mult": mult}, m)

    return n


def search_coinglass(close: pd.Series, f: dict, hits: list[Hit]) -> int:
    n = 0
    ma150 = f["ma150"]
    ma200 = f["ma200"]
    trend150 = close.shift(LAG) > ma150
    trend200 = close.shift(LAG) > ma200

    # Funding variants
    for fk in ["cg_futures_funding_rate_binance_1d", "cg_futures_funding_rate_oi_weight_binance_1d", "cg_futures_funding_rate_vol_weight_binance_1d"]:
        if fk not in f:
            continue
        fund = f[fk]
        for qlo in [0.05, 0.10, 0.15, 0.20]:
            for qhi in [0.80, 0.85, 0.90]:
                e = (fund < fund.rolling(90).quantile(qlo)).fillna(False) & trend200
                x = (fund > fund.rolling(90).quantile(qhi)).fillna(False)
                pos = pos_sig(e, x)
                m = eval_pos(close, pos)
                n += 1
                consider(hits, "coinglass", "funding_quantile", f"{fk.split('_')[-4]} q{qlo}/{qhi}", {"key": fk, "qlo": qlo, "qhi": qhi}, m)

    # Basis carry
    if "cg_futures_basis_binance_1d" in f:
        basis = f["cg_futures_basis_binance_1d"]
        for ent in np.arange(-0.005, 0.015, 0.0025):
            for ex in np.arange(0.005, 0.025, 0.005):
                e = (basis > ent).fillna(False) & trend200
                x = (basis < ex).fillna(False)
                pos = pos_sig(e, x)
                m = eval_pos(close, pos)
                n += 1
                consider(hits, "coinglass", "basis_carry", f"basis>{ent:.3f}", {"ent": float(ent), "ex": float(ex)}, m)

    # OI expansion
    if "cg_futures_open_interest_history_ohlc_binance_1d" in f:
        oi = f["cg_futures_open_interest_history_ohlc_binance_1d"]
        oi_chg = oi.pct_change(5)
        mom = f.get("mom21", close.pct_change(21).shift(LAG))
        for trail in [0.10, 0.12, 0.15]:
            e = (mom > 0) & (oi_chg > 0).fillna(False) & trend200
            pos = trail_pos(close, e, trail)
            m = eval_pos(close, pos)
            n += 1
            consider(hits, "coinglass", "oi_expansion", f"OI+mom trail{trail:.0%}", {"trail": trail}, m)

    # Liquidation fade
    for lk in ["cg_long_liq", "cg_short_liq"]:
        if lk not in f:
            continue
        liq = f[lk]
        for q in [0.90, 0.93, 0.95, 0.97]:
            for hold in [3, 5, 7, 10]:
                spike = (liq > liq.rolling(90).quantile(q)).shift(LAG).fillna(False)
                e = spike
                x = spike.shift(hold).fillna(False)
                pos = pos_sig(e, x)
                m = eval_pos(close, pos)
                n += 1
                consider(hits, "coinglass", "liq_fade", f"{lk} q={q} hold={hold}", {"key": lk, "q": q, "hold": hold}, m)

    # Taker buy ratio
    if "cg_taker_buy_ratio" in f:
        ratio = f["cg_taker_buy_ratio"]
        for ent in [0.52, 0.54, 0.55, 0.56]:
            for ex in [0.48, 0.50]:
                e = (ratio > ent).fillna(False) & trend200
                x = (ratio < ex).fillna(False)
                pos = pos_sig(e, x)
                m = eval_pos(close, pos)
                n += 1
                consider(hits, "coinglass", "taker_imbalance", f"taker>{ent}", {"ent": ent, "ex": ex}, m)

    # Orderbook imbalance (futures + spot)
    for ok, label in [("cg_ob_imbalance", "fut"), ("cg_spot_ob_imbalance", "spot")]:
        if ok not in f:
            continue
        imb = f[ok]
        for ent in [0.04, 0.06, 0.08, 0.10]:
            e = (imb > ent).fillna(False) & trend150
            x = (imb < 0).fillna(False)
            pos = pos_sig(e, x)
            m = eval_pos(close, pos)
            n += 1
            consider(hits, "coinglass", "orderbook", f"{label} imb>{ent}", {"key": ok, "ent": ent}, m)

    # Whale index gate + trend
    if "cg_indic_whale_index_binance_1d" in f:
        whale = f["cg_indic_whale_index_binance_1d"]
        for wthr in [0.3, 0.5, 0.7, 0.9]:
            for ma_w in [100, 150, 200]:
                ma = close.rolling(ma_w).mean().shift(LAG)
                e = (close.shift(LAG) > ma) & (whale < whale.rolling(90).quantile(wthr)).fillna(False)
                for trail in [0.08, 0.10, 0.12]:
                    pos = trail_pos(close, e.fillna(False), trail)
                    m = eval_pos(close, pos)
                    n += 1
                    consider(hits, "coinglass", "whale_gate", f"whale<{wthr}+MA{ma_w}", {"wthr": wthr, "ma": ma_w, "trail": trail}, m)

    # L/S ratio fade
    if "cg_futures_global_account_long_short_ratio_binance_1d" in f:
        ls = f["cg_futures_global_account_long_short_ratio_binance_1d"]
        for qhi in [0.90, 0.93, 0.95]:
            e = (ls < ls.rolling(90).quantile(1 - qhi)).fillna(False)  # extreme short crowd
            x = (ls > ls.rolling(90).quantile(0.5)).fillna(False)
            pos = pos_sig(e, x)
            m = eval_pos(close, pos)
            n += 1
            consider(hits, "coinglass", "ls_fade", f"LS fade q={qhi}", {"qhi": qhi}, m)

    # Net position momentum
    if "cg_futures_net_position_v2_binance_1d" in f:
        net = f["cg_futures_net_position_v2_binance_1d"]
        for w in [3, 5, 7]:
            e = (net.rolling(w).sum() > 0).shift(LAG).fillna(False) & trend200
            x = (net.rolling(w).sum() < 0).shift(LAG).fillna(False)
            pos = pos_sig(e, x)
            m = eval_pos(close, pos)
            n += 1
            consider(hits, "coinglass", "net_position", f"net_pos {w}d", {"w": w}, m)

    # ETF flows / premium
    if "cg_etf_flows_btc" in f:
        flow = f["cg_etf_flows_btc"]
        for sm in [3, 5, 7, 10]:
            fs = flow.rolling(sm).sum()
            e = (fs > 0).fillna(False) & trend200
            x = (fs < 0).fillna(False)
            pos = pos_sig(e, x)
            m = eval_pos(close, pos)
            n += 1
            consider(hits, "coinglass", "etf_flow", f"ETF flow {sm}d", {"sm": sm}, m)

    if "cg_etf_premium_discount_btc" in f:
        prem = f["cg_etf_premium_discount_btc"]
        for q in [0.05, 0.10, 0.15]:
            e = (prem < prem.rolling(90).quantile(q)).fillna(False)
            x = (prem > prem.rolling(90).quantile(0.5)).fillna(False)
            pos = pos_sig(e, x)
            m = eval_pos(close, pos)
            n += 1
            consider(hits, "coinglass", "etf_premium", f"ETF disc q={q}", {"q": q}, m)

    # Exchange balance drain
    if "cg_exchange_balance_btc" in f:
        bal = f["cg_exchange_balance_btc"]
        for w in [7, 14, 30]:
            d = bal.diff(w)
            e = (d < 0).fillna(False) & trend200
            x = (d > 0).fillna(False)
            pos = pos_sig(e, x)
            m = eval_pos(close, pos)
            n += 1
            consider(hits, "coinglass", "ex_balance", f"balance drain {w}d", {"w": w}, m)

    # Puell (already known best) + trail grid
    if "cg_puell_multiple" in f:
        puell = f["cg_puell_multiple"]
        for ma in range(140, 160):
            ma_s = close.rolling(ma).mean().shift(LAG)
            for pthr in np.arange(0.95, 1.05, 0.01):
                for trail in np.arange(0.06, 0.14, 0.01):
                    e = (close.shift(LAG) > ma_s) & (puell < pthr)
                    pos = trail_pos(close, e.fillna(False), float(trail))
                    m = eval_pos(close, pos)
                    n += 1
                    consider(hits, "coinglass", "sma_puell_trail", f"SMA{ma}+P{pthr:.2f}+T{trail:.0%}", {"ma": ma, "p": float(pthr), "trail": float(trail)}, m)

    return n


def search_price_mr(close: pd.Series, f: dict, hits: list[Hit]) -> int:
    n = 0
    high, low = f["high"], f["low"]
    ibs = ((close - low) / (high - low).replace(0, np.nan)).shift(LAG)
    rsi = vbt.RSI.run(close, 14).rsi.shift(LAG)
    er = efficiency_ratio(close, 20).shift(LAG)

    for tma in [100, 125, 150, 200]:
        ma = close.rolling(tma).mean().shift(LAG)
        for ibs_thr in [0.15, 0.20, 0.25, 0.30, 0.35]:
            for rsi_thr in [25, 30, 35, 40]:
                e = (close.shift(LAG) > ma) & (ibs < ibs_thr) & (rsi < rsi_thr)
                x = (ibs > 0.5) | (close.shift(LAG) < ma)
                pos = pos_sig(e.fillna(False), x.fillna(False))
                m = eval_pos(close, pos)
                n += 1
                consider(hits, "price", "ibs_pullback", f"IBS MA{tma}", {"tma": tma, "ibs": ibs_thr, "rsi": rsi_thr}, m)

    for er_thr in [0.4, 0.5, 0.6]:
        for lo in [25, 30, 35]:
            e = (er > er_thr) & (rsi < lo)
            x = rsi > 50
            pos = pos_sig(e.fillna(False), x.fillna(False))
            m = eval_pos(close, pos)
            n += 1
            consider(hits, "price", "rsi_er", f"RSI<{lo} ER>{er_thr}", {"er": er_thr, "lo": lo}, m)

    # CMMA + gates from any on-chain filter
    if "cmma40" in f:
        cmma = f["cmma40"]
        for gk in ["cg_puell_multiple", "talos_NUPL", "talos_CapMVRVCur"]:
            if gk not in f:
                continue
            gate = f[gk]
            for pthr in [0.99, 1.0, 1.1, 0.75]:
                if "puell" in gk:
                    filt = gate < pthr
                elif "NUPL" in gk:
                    filt = gate < pthr
                else:
                    filt = gate < pthr
                for trail in [0.08, 0.10, 0.12, 0.15]:
                    e = (cmma > 0) & filt
                    pos = trail_pos(close, e.fillna(False), trail)
                    m = eval_pos(close, pos)
                    n += 1
                    consider(hits, "composite", "cmma_gate", f"CMMA+{gk.split('_')[-1]}", {"gate": gk, "p": pthr, "trail": trail}, m)

    return n


def search_cross_venue(close: pd.Series, f: dict, hits: list[Hit]) -> int:
    n = 0
    for sk in ["venue_spread_bn_talos", "venue_spread_hl_talos", "venue_spread_hl_bn"]:
        if sk not in f:
            continue
        spread = f[sk]
        for q in [0.05, 0.10, 0.15]:
            e = (spread < spread.rolling(60).quantile(q)).fillna(False)
            x = (spread > spread.rolling(60).quantile(0.5)).fillna(False)
            pos = pos_sig(e, x)
            m = eval_pos(close, pos)
            n += 1
            consider(hits, "cross_venue", "spread_mr", f"{sk} q={q}", {"key": sk, "q": q}, m)

        # Trend on alternate venue
        alt_key = {"venue_spread_bn_talos": "binance_close", "venue_spread_hl_talos": "hyperliquid_close"}.get(sk)
        if alt_key and alt_key in f:
            alt = f[alt_key]
            for ma in [50, 100, 150]:
                ma_a = alt.rolling(ma).mean().shift(LAG)
                e = (alt.shift(LAG) > ma_a).fillna(False)
                for trail in [0.08, 0.10, 0.12]:
                    pos = trail_pos(close, e, trail)
                    m = eval_pos(close, pos)
                    n += 1
                    consider(hits, "cross_venue", "alt_trend", f"{alt_key} MA{ma}", {"key": alt_key, "ma": ma, "trail": trail}, m)
    return n


def search_systematic_talos(close: pd.Series, f: dict, hits: list[Hit]) -> int:
    """Quantile-based search on all high-coverage Talos metrics."""
    n = 0
    ma200 = f["ma200"]
    trend = close.shift(LAG) > ma200
    talos_keys = [k for k in f if k.startswith("talos_") and f[k].notna().mean() > 0.8]
    skip = {"talos_PriceUSD", "talos_ReferenceRateUSD"}

    for key in talos_keys:
        if key in skip:
            continue
        s = f[key]
        for q_ent in [0.05, 0.10, 0.15, 0.20]:
            for q_ex in [0.80, 0.85, 0.90]:
                ent_thr = s.rolling(252, min_periods=60).quantile(q_ent)
                ex_thr = s.rolling(252, min_periods=60).quantile(q_ex)
                for gate in [False, True]:
                    e = (s < ent_thr).fillna(False)
                    x = (s > ex_thr).fillna(False)
                    if gate:
                        e = e & trend
                    pos = pos_sig(e, x)
                    m = eval_pos(close, pos)
                    n += 1
                    if m["sharpe"] >= 0.95 and m["max_dd"] > -0.30:
                        consider(hits, "talos", "quantile", f"{key} q{q_ent}/{q_ex}", {"key": key, "q_ent": q_ent, "q_ex": q_ex, "gate": gate}, m)
    return n


def select_diverse(hits: list[Hit], k: int = 5) -> list[Hit]:
    hits = sorted(hits, key=lambda h: (-h.sharpe, h.max_dd), reverse=True)
    chosen: list[Hit] = []
    families: set[str] = set()
    providers: set[str] = set()
    for h in hits:
        fam_key = f"{h.provider}:{h.family}"
        if fam_key in families:
            continue
        chosen.append(h)
        families.add(fam_key)
        providers.add(h.provider)
        if len(chosen) >= k:
            break
    if len(chosen) < k:
        for h in hits:
            if h not in chosen:
                chosen.append(h)
            if len(chosen) >= k:
                break
    return chosen[:k]


def main() -> None:
    (RUN / "artifacts").mkdir(parents=True, exist_ok=True)
    print("Loading all provider features...")
    ohlcv, f, meta = load_all_features()
    close = f["close"]
    print(f"  {meta['n_features']} features | {meta['source']}")

    hits: list[Hit] = []
    counts = {}
    for name, fn in [
        ("talos_onchain", search_talos_onchain),
        ("coinglass", search_coinglass),
        ("price_mr", search_price_mr),
        ("cross_venue", search_cross_venue),
        ("systematic_talos", search_systematic_talos),
    ]:
        print(f"Searching {name}...")
        counts[name] = fn(close, f, hits)
        print(f"  configs={counts[name]} cumulative_hits={len(hits)}")

    hits.sort(key=lambda h: -h.sharpe)
    near = [h for h in hits if h.sharpe >= 0.95]  # will recompute near from all evals - use top non-qualifying

    print(f"\n=== RESULTS ===")
    print(f"Total qualifying hits (Sharpe>=1, DD<25%, trades>={MIN_TRADES}): {len(hits)}")
    for h in hits[:30]:
        print(f"  [{h.provider:12}] {h.family:16} {h.name[:45]:45} sh={h.sharpe:.3f} dd={h.max_dd:.1%} tr={h.trades}")

    diverse = select_diverse(hits, 5)
    print(f"\nDiverse 5 ({len(diverse)}):")
    for h in diverse:
        print(f"  [{h.provider}] {h.name} sh={h.sharpe:.3f} dd={h.max_dd:.1%}")

    out = {
        "meta": meta,
        "search_counts": counts,
        "min_trades": MIN_TRADES,
        "total_hits": len(hits),
        "top_50": [asdict(h) for h in hits[:50]],
        "diverse_5": [asdict(h) for h in diverse],
    }
    (RUN / "artifacts" / "all_providers_search_hits.json").write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nWrote {RUN / 'artifacts' / 'all_providers_search_hits.json'}")


if __name__ == "__main__":
    main()
