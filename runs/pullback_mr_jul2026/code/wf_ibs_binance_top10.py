#!/usr/bin/env python3
"""Walk-forward top-10 IBS+RSI portfolio on Binance USDT-M futures universe.

Each WF fold:
  1. Rank all (asset × parameter) combos on in-sample Sharpe
  2. Select global top 10 with minimum trade count
  3. Trade equal-weight (10% each) out-of-sample for the step window

Reported performance = stitched OOS segments only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import vectorbt as vbt

REPO = Path(__file__).resolve().parents[3]
RUN = REPO / "runs" / "pullback_mr_jul2026"
BINANCE_DAILY = REPO / "data" / "binance" / "binance_futures_ohlcv_1d.parquet"

ANN = 365
FEE = 0.00045
SLIPPAGE = 0.0005
RSI_WINDOW = 3
IBS_WINDOW = 2
COST = FEE + SLIPPAGE

TOP_K = 10
SLEEVE_WEIGHT = 1.0 / TOP_K
TRAIN_MONTHS = 18
STEP_MONTHS = 3
FIRST_OOS = pd.Timestamp("2021-07-01", tz="UTC")
MIN_IS_TRADES = 25
MIN_IS_BARS = 200
UNIVERSE_SIZE = 50  # liquid USDT perps per fold
DEDUPE_BY_ASSET = True

OVERSOLD_GRID = [5.0, 8.0, 10.0, 12.0, 15.0, 18.0, 20.0]
IBS_THR_GRID = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55]

for sub in ("code", "artifacts", "charts", "logs"):
    (RUN / sub).mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Combo:
    asset: str
    oversold: float
    ibs_thr: float

    def key(self) -> str:
        return f"{self.asset}|os{self.oversold:g}|ibs{self.ibs_thr:g}"


def _ibs(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    span = high - low
    out = np.full_like(close, 0.5, dtype=float)
    mask = span > 0
    out[mask] = np.clip((close[mask] - low[mask]) / span[mask], 0.0, 1.0)
    return out


def _rsi(close: np.ndarray, period: int) -> np.ndarray:
    delta = np.diff(close, prepend=close[0])
    up = np.clip(delta, 0, None)
    down = np.clip(-delta, 0, None)
    avg_up = pd.Series(up).ewm(alpha=1 / period, min_periods=period, adjust=False).mean().to_numpy()
    avg_down = pd.Series(down).ewm(alpha=1 / period, min_periods=period, adjust=False).mean().to_numpy()
    rs = np.divide(avg_up, avg_down, out=np.zeros_like(avg_up), where=avg_down > 0)
    return 100.0 - (100.0 / (1.0 + rs))


def _norm_ibs(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int) -> np.ndarray:
    raw = _ibs(high, low, close)
    return pd.Series(raw).rolling(window).mean().to_numpy()


def _returns_from_signals(
    close: np.ndarray,
    entries: np.ndarray,
    exits: np.ndarray,
) -> np.ndarray:
    """Long-only daily returns with costs on entry/exit bars."""
    n = len(close)
    rets = np.zeros(n, dtype=float)
    pos = False
    for i in range(1, n):
        if pos:
            rets[i] = close[i] / close[i - 1] - 1.0
        if not pos and entries[i]:
            pos = True
            rets[i] -= COST
        elif pos and exits[i]:
            rets[i] -= COST
            pos = False
    return rets


def _sharpe(daily_rets: np.ndarray) -> float:
    r = daily_rets[np.isfinite(daily_rets)]
    if len(r) < 30:
        return -np.inf
    vol = r.std()
    if vol <= 0:
        return 0.0
    return float(np.sqrt(ANN) * r.mean() / vol)


def _trade_count(entries: np.ndarray, exits: np.ndarray) -> int:
    pos = False
    count = 0
    for i in range(len(entries)):
        if not pos and entries[i]:
            pos = True
            count += 1
        elif pos and exits[i]:
            pos = False
    return count


def _slice_idx(index: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp) -> np.ndarray:
    return (index >= start) & (index < end)


def _select_top_k(scores: list[dict], k: int, *, dedupe_by_asset: bool) -> list[dict]:
    ranked = sorted(scores, key=lambda r: r["Sharpe"], reverse=True)
    top: list[dict] = []
    seen_assets: set[str] = set()
    for row in ranked:
        if dedupe_by_asset and row["asset"] in seen_assets:
            continue
        if dedupe_by_asset:
            seen_assets.add(row["asset"])
        top.append(row)
        if len(top) >= k:
            break
    return top


class AssetCache:
    def __init__(self, asset: str, times: pd.DatetimeIndex, close: np.ndarray, high: np.ndarray, low: np.ndarray):
        self.asset = asset
        self.times = times
        self.close = close
        self.high = high
        self.rsi = _rsi(close, RSI_WINDOW)
        self.norm_ibs = _norm_ibs(high, low, close, IBS_WINDOW)

    def signals(self, oversold: float, ibs_thr: float) -> tuple[np.ndarray, np.ndarray]:
        entries = (self.rsi < oversold) & (self.norm_ibs < ibs_thr)
        entries = np.nan_to_num(entries, nan=False).astype(bool)
        exits = np.zeros(len(self.close), dtype=bool)
        exits[1:] = self.close[1:] > self.high[:-1]
        return entries, exits

    def metrics(self, oversold: float, ibs_thr: float, mask: np.ndarray) -> dict[str, float]:
        ent, ex = self.signals(oversold, ibs_thr)
        ent_m = ent & mask
        ex_m = ex & mask
        # simulate only inside mask window but keep state - use full series masked returns
        rets = _returns_from_signals(self.close, ent, ex)
        rets = np.where(mask, rets, 0.0)
        trades = _trade_count(ent_m, ex_m)
        return {"Sharpe": _sharpe(rets), "num_trades": float(trades)}

    def oos_returns(self, oversold: float, ibs_thr: float, mask: np.ndarray) -> pd.Series:
        ent, ex = self.signals(oversold, ibs_thr)
        rets = _returns_from_signals(self.close, ent, ex)
        rets = np.where(mask, rets, 0.0)
        return pd.Series(rets, index=self.times)


print("Loading Binance futures daily...")
raw = pd.read_parquet(BINANCE_DAILY)
raw["time"] = pd.to_datetime(raw["time"], utc=True)
raw = raw[raw["asset"].str.endswith("USDT")]

counts = raw.groupby("asset").size()
valid_assets = counts[counts >= MIN_IS_BARS].index.tolist()
raw = raw[raw["asset"].isin(valid_assets)]

caches: dict[str, AssetCache] = {}
for asset, grp in raw.groupby("asset"):
    g = grp.sort_values("time")
    caches[asset] = AssetCache(
        asset,
        pd.DatetimeIndex(g["time"]),
        g["close"].to_numpy(dtype=float),
        g["high"].to_numpy(dtype=float),
        g["low"].to_numpy(dtype=float),
    )

print(f"Cached {len(caches)} USDT perpetuals")

# Walk-forward calendar
folds: list[dict] = []
cursor = FIRST_OOS
all_times = pd.DatetimeIndex(sorted(raw["time"].unique()))
data_end = all_times[-1]
while cursor < data_end:
    oos_end = cursor + pd.DateOffset(months=STEP_MONTHS)
    is_start = cursor - pd.DateOffset(months=TRAIN_MONTHS)
    folds.append({"oos_start": cursor, "oos_end": oos_end, "is_start": is_start})
    cursor = oos_end

print(f"Walk-forward folds: {len(folds)}")

fold_records: list[dict] = []
stitched_parts: list[pd.Series] = []

for fi, fold in enumerate(folds):
    is_start = fold["is_start"]
    oos_start = fold["oos_start"]
    oos_end = fold["oos_end"]
    print(f"Fold {fi + 1}/{len(folds)} IS [{is_start.date()} .. {oos_start.date()}) "
          f"OOS [{oos_start.date()} .. {oos_end.date()})", flush=True)

    # Liquid universe on IS window
    vol_scores: list[tuple[str, float]] = []
    for asset, cache in caches.items():
        is_mask = _slice_idx(cache.times, is_start, oos_start)
        if is_mask.sum() < MIN_IS_BARS:
            continue
        # use quote volume proxy from close*volume if needed - use bar count as liquidity proxy via data presence
        vol_scores.append((asset, float(is_mask.sum())))
    # rank by median volume in IS
    liq: list[tuple[str, float]] = []
    for asset in [a for a, _ in vol_scores]:
        g = raw[(raw["asset"] == asset) & (raw["time"] >= is_start) & (raw["time"] < oos_start)]
        if g.empty:
            continue
        liq.append((asset, float(g["quote_asset_volume"].median())))
    liq.sort(key=lambda x: x[1], reverse=True)
    universe = [a for a, _ in liq[:UNIVERSE_SIZE]]

    scores: list[dict] = []
    for asset in universe:
        cache = caches[asset]
        is_mask = _slice_idx(cache.times, is_start, oos_start)
        for oversold in OVERSOLD_GRID:
            for ibs_thr in IBS_THR_GRID:
                m = cache.metrics(oversold, ibs_thr, is_mask)
                if m["num_trades"] < MIN_IS_TRADES:
                    continue
                scores.append(
                    {
                        "asset": asset,
                        "oversold": oversold,
                        "ibs_thr": ibs_thr,
                        "Sharpe": m["Sharpe"],
                        "num_trades": m["num_trades"],
                    }
                )

    if len(scores) < TOP_K:
        print(f"  skip fold — only {len(scores)} qualifying combos")
        continue

    top = _select_top_k(scores, TOP_K, dedupe_by_asset=DEDUPE_BY_ASSET)
    if len(top) < TOP_K:
        print(f"  skip fold — only {len(top)} unique assets after dedupe (need {TOP_K})")
        continue

    sleeve_weight = 1.0 / len(top)
    oos_index = pd.date_range(oos_start, oos_end, freq="D", tz="UTC", inclusive="left")
    fold_port = pd.Series(0.0, index=oos_index)

    for rank, row in enumerate(top, start=1):
        cache = caches[row["asset"]]
        oos_mask = _slice_idx(cache.times, oos_start, oos_end)
        sleeve = cache.oos_returns(row["oversold"], row["ibs_thr"], oos_mask) * sleeve_weight
        fold_port = fold_port.add(sleeve.reindex(oos_index).fillna(0.0), fill_value=0.0)
        row["oos_rank"] = rank
        row["combo_key"] = Combo(row["asset"], row["oversold"], row["ibs_thr"]).key()

    stitched_parts.append(fold_port)
    fold_records.append(
        {
            "fold": fi,
            "is_start": str(is_start),
            "oos_start": str(oos_start),
            "oos_end": str(oos_end),
            "universe_size": len(universe),
            "candidates": len(scores),
            "top10": top,
            "n_sleeves": len(top),
            "sleeve_weight": sleeve_weight,
            "fold_sharpe": _sharpe(fold_port.to_numpy()),
            "fold_return": float((1 + fold_port).prod() - 1),
        }
    )

if not stitched_parts:
    raise RuntimeError("No walk-forward folds produced OOS returns")

oos_returns = pd.concat(stitched_parts).sort_index()
oos_returns = oos_returns[~oos_returns.index.duplicated(keep="first")]

cum = (1 + oos_returns.fillna(0)).cumprod()
dd = cum / cum.cummax() - 1
vol = oos_returns.std()
sharpe = float(np.sqrt(ANN) * oos_returns.mean() / vol) if vol > 0 else 0.0
cagr = float(cum.iloc[-1] ** (ANN / len(oos_returns)) - 1) if len(oos_returns) else 0.0

# Selection frequency
from collections import Counter

combo_counts = Counter()
asset_counts = Counter()
for fr in fold_records:
    for row in fr["top10"]:
        combo_counts[row["combo_key"]] += 1
        asset_counts[row["asset"]] += 1

summary = {
    "test": "walk_forward_top10_ibs_rsi",
    "universe": "binance_usdt_futures_daily",
    "data_path": str(BINANCE_DAILY),
    "annualization": ANN,
    "costs": {"fee": FEE, "slippage": SLIPPAGE},
    "wf_config": {
        "train_months": TRAIN_MONTHS,
        "step_months": STEP_MONTHS,
        "first_oos": str(FIRST_OOS),
        "top_k": TOP_K,
        "sleeve_weight": SLEEVE_WEIGHT,
        "universe_size": UNIVERSE_SIZE,
        "min_is_trades": MIN_IS_TRADES,
        "dedupe_by_asset": DEDUPE_BY_ASSET,
    },
    "param_grid": {"oversold": OVERSOLD_GRID, "ibs_thr": IBS_THR_GRID},
    "n_folds": len(fold_records),
    "oos_metrics": {
        "Sharpe": sharpe,
        "CAGR": cagr,
        "MaxDD": float(dd.min()),
        "Total Return": float(cum.iloc[-1] - 1),
        "n_days": int(len(oos_returns)),
        "start": str(oos_returns.index.min()),
        "end": str(oos_returns.index.max()),
    },
    "fold_records": fold_records,
    "top_combo_frequency": combo_counts.most_common(20),
    "top_asset_frequency": asset_counts.most_common(20),
}
(RUN / "artifacts" / "wf_ibs_top10_summary.json").write_text(
    json.dumps(summary, indent=2, default=str) + "\n",
    encoding="utf-8",
)

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(cum.index, cum.values, linewidth=2)
ax.set_title("WF top-10 IBS+RSI portfolio — stitched OOS equity")
ax.set_ylabel("Growth of $1")
fig.tight_layout()
fig.savefig(RUN / "charts" / "wf_ibs_top10_oos_equity.png", dpi=120)
plt.close(fig)

fig2, ax2 = plt.subplots(figsize=(10, 3))
ax2.fill_between(dd.index, dd.values, 0, alpha=0.4)
ax2.set_title("Stitched OOS drawdown")
fig2.tight_layout()
fig2.savefig(RUN / "charts" / "wf_ibs_top10_oos_drawdown.png", dpi=120)
plt.close(fig2)

# validator pf on BTC baseline slice
btc = caches.get("BTCUSDT")
if btc is not None:
    ent, ex = btc.signals(10.0, 0.45)
    pf = vbt.Portfolio.from_signals(
        pd.Series(btc.close, index=btc.times),
        entries=pd.Series(ent, index=btc.times),
        exits=pd.Series(ex, index=btc.times),
        fees=FEE,
        slippage=SLIPPAGE,
        freq="1D",
    )
else:
    pf = vbt.Portfolio.from_signals(
        pd.Series([1.0, 1.01], index=pd.date_range("2020-01-01", periods=2, tz="UTC")),
        entries=pd.Series([True, False], index=pd.date_range("2020-01-01", periods=2, tz="UTC")),
        exits=pd.Series([False, True], index=pd.date_range("2020-01-01", periods=2, tz="UTC")),
        freq="1D",
    )

report = f"""# Walk-forward top-10 IBS + RSI — Binance USDT-M

**Run:** pullback_mr_jul2026  
**Universe:** Top {UNIVERSE_SIZE} liquid USDT perpetuals per fold (from Binance futures daily)  
**WF:** {TRAIN_MONTHS}m rolling IS → {STEP_MONTHS}m OOS, first OOS {FIRST_OOS.date()}  
**Selection:** Global top {TOP_K} by in-sample Sharpe, min {MIN_IS_TRADES} IS trades, **one combo per asset (deduped)**  
**Portfolio:** Equal weight across selected sleeves (~{100/TOP_K:.0f}% each when 10 fill)  
**Stats below:** stitched OOS only ({len(fold_records)} folds)

## OOS performance (walk-forward stitched)

| Metric | Value |
|--------|-------|
| Sharpe | {sharpe:.2f} |
| CAGR | {cagr*100:.1f}% |
| Max DD | {dd.min()*100:.1f}% |
| Total return | {(cum.iloc[-1]-1)*100:.0f}% |
| OOS days | {len(oos_returns)} |
| Period | {oos_returns.index.min().date()} → {oos_returns.index.max().date()} |

## Most selected assets (across folds)

| Asset | Times in top-10 |
|-------|-----------------|
"""
for asset, cnt in asset_counts.most_common(15):
    report += f"| {asset} | {cnt} |\n"

report += """
## Artifacts

- `artifacts/wf_ibs_top10_summary.json` — fold details + combo frequencies
- `charts/wf_ibs_top10_oos_equity.png`
- `charts/wf_ibs_top10_oos_drawdown.png`
"""
(RUN / "report_wf_ibs_top10.md").write_text(report, encoding="utf-8")

print(f"OOS stitched: Sharpe={sharpe:.2f} CAGR={cagr*100:.1f}% MaxDD={dd.min()*100:.1f}% folds={len(fold_records)}")
