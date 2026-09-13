"""Wallet / account Sharpe from equity snapshots + capital flows.

This is a measurement layer, not an OHLCV rule. The honest unit of return for an
exchange account is the **time-weighted return** (TWR):

    r_t = V_t / (V_{t-1} + CF_t) - 1

where ``CF_t`` is net external capital credited at the start of the bar
(deposits, withdrawals, internal transfers, vault flows, spot↔perp class
transfers). Naive ``equity.pct_change()`` treats a deposit as trading skill.

Hyperliquid is the reference venue: public addresses, a leaderboard, and an
info API for portfolio NAV, ledger updates, fills, and funding. Coin-level
Sharpe is a *contribution* (coin PnL / prior account equity), not isolated
margin, unless the account actually uses isolated margin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from .selection import probabilistic_sharpe, sharpe_from_returns

HL_COIN_ALIASES = {
    "BTC": "BTC",
    "BTCUSDT": "BTC",
    "BTC-USD": "BTC",
    "ETH": "ETH",
    "ETHUSDT": "ETH",
    "SOL": "SOL",
    "SOLUSDT": "SOL",
}

# Ledger deltas that move *external* capital. Liquidations and funding are PnL.
_PERP_FLOW_TYPES = frozenset(
    {
        "deposit",
        "withdraw",
        "internalTransfer",
        "subAccountTransfer",
        "accountClassTransfer",
        "vaultDeposit",
        "vaultWithdraw",
        "vaultDistribution",
        "vaultLeaderCommission",
    }
)


def normalize_coin(symbol: str) -> str:
    raw = str(symbol or "").strip()
    if not raw:
        return ""
    if raw in HL_COIN_ALIASES:
        return HL_COIN_ALIASES[raw]
    upper = raw.upper()
    return HL_COIN_ALIASES.get(upper, raw.split(":")[-1].lstrip("@") or raw)


def _as_utc_index(values: Iterable) -> pd.DatetimeIndex:
    idx = pd.to_datetime(list(values), utc=True)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")
    return pd.DatetimeIndex(idx)


def ms_to_utc(ms: Any) -> pd.Timestamp:
    return pd.to_datetime(int(ms), unit="ms", utc=True)


def twr_returns(
    equity: pd.Series,
    cashflow: pd.Series | None = None,
    *,
    timing: str = "open",
    min_equity: float = 1e-8,
    min_active_equity: float = 0.0,
) -> pd.Series:
    """Bar TWR from mark-to-market equity and signed external cashflow.

    ``timing="open"`` (default): cashflow is available at the start of the bar
    and *does* earn this bar's trading PnL. ``timing="close"`` assumes the
    flow prints at the bar close and does not earn this bar.

    ``min_active_equity`` masks dust / empty snapshots (common on Hyperliquid
    ``perpAllTime`` tapes) so a later deposit is not a +∞ return.
    """
    eq = pd.Series(equity, dtype=float).sort_index()
    if not isinstance(eq.index, pd.DatetimeIndex):
        eq.index = _as_utc_index(eq.index)
    elif eq.index.tz is None:
        eq.index = eq.index.tz_localize("UTC")
    if float(min_active_equity) > 0:
        eq = eq.where(eq.abs() >= float(min_active_equity))
    cf = (
        pd.Series(cashflow, dtype=float).reindex(eq.index).fillna(0.0)
        if cashflow is not None
        else pd.Series(0.0, index=eq.index)
    )
    prev = eq.shift(1)
    if timing == "close":
        denom = prev
        numer = eq - cf
    elif timing == "open":
        denom = prev + cf
        numer = eq
    else:
        raise ValueError(f"timing must be 'open' or 'close', got {timing!r}")
    ret = numer / denom - 1.0
    ok = denom.abs() > float(min_equity)
    ret = ret.where(ok)
    ret.iloc[0] = np.nan
    return ret.rename("twr")


def naive_equity_returns(equity: pd.Series) -> pd.Series:
    eq = pd.Series(equity, dtype=float).sort_index()
    return eq.pct_change().rename("naive")


def resample_equity_cashflow(
    equity: pd.Series,
    cashflow: pd.Series | None = None,
    *,
    freq: str = "1D",
) -> tuple[pd.Series, pd.Series]:
    """Last equity in the bin, summed cashflow in the bin."""
    eq = pd.Series(equity, dtype=float).sort_index()
    if eq.empty:
        empty = pd.Series(dtype=float, name="equity")
        return empty, pd.Series(dtype=float, name="cashflow")
    eq_r = eq.resample(freq).last().dropna()
    if cashflow is None or len(pd.Series(cashflow).dropna()) == 0:
        cf_r = pd.Series(0.0, index=eq_r.index, name="cashflow")
        return eq_r.rename("equity"), cf_r
    cf = pd.Series(cashflow, dtype=float).sort_index().fillna(0.0)
    cf_r = cf.resample(freq).sum().reindex(eq_r.index).fillna(0.0)
    return eq_r.rename("equity"), cf_r.rename("cashflow")


def signed_perp_cashflow(user: str, delta: Mapping[str, Any]) -> float:
    """Signed USDC flow into the Hyperliquid *perp* account.

    Positive = capital in. Liquidations, funding, and spot-only sends are 0
    (they are PnL or they do not touch perp equity until a class transfer).
    """
    if not isinstance(delta, Mapping):
        return 0.0
    kind = str(delta.get("type") or "")
    if kind not in _PERP_FLOW_TYPES:
        return 0.0
    addr = str(user or "").lower()

    def _f(key: str, default: float = 0.0) -> float:
        raw = delta.get(key)
        if raw is None or raw == "":
            return default
        return float(raw)

    if kind == "deposit":
        return _f("usdc")
    if kind == "withdraw":
        return -_f("usdc") - _f("fee")
    if kind in {"internalTransfer", "subAccountTransfer"}:
        amt = _f("usdc")
        dest = str(delta.get("destination") or "").lower()
        src = str(delta.get("user") or "").lower()
        if dest == addr and src != addr:
            return amt
        if src == addr and dest != addr:
            return -amt - _f("fee")
        return 0.0
    if kind == "accountClassTransfer":
        amt = _f("usdc")
        return amt if bool(delta.get("toPerp")) else -amt
    if kind == "vaultDeposit":
        return -_f("usdc")
    if kind == "vaultWithdraw":
        net = delta.get("netWithdrawnUsd")
        if net is None or net == "":
            return _f("requestedUsd") - _f("commission") - _f("closingCost")
        return float(net)
    if kind in {"vaultDistribution", "vaultLeaderCommission"}:
        return _f("usdc")
    return 0.0


def ledger_to_cashflow(
    events: Iterable[Mapping[str, Any]],
    user: str,
) -> pd.Series:
    """Collapse Hyperliquid ``userNonFundingLedgerUpdates`` into a flow series."""
    times: list[pd.Timestamp] = []
    flows: list[float] = []
    for ev in events:
        if not isinstance(ev, Mapping):
            continue
        delta = ev.get("delta") if isinstance(ev.get("delta"), Mapping) else ev
        flow = signed_perp_cashflow(user, delta)  # type: ignore[arg-type]
        if flow == 0.0:
            continue
        t = ev.get("time")
        if t is None:
            continue
        times.append(ms_to_utc(t) if np.issubdtype(type(t), np.number) or isinstance(t, (int, float, str)) else pd.Timestamp(t, tz="UTC"))
        flows.append(float(flow))
    if not times:
        return pd.Series(dtype=float, name="cashflow")
    s = pd.Series(flows, index=_as_utc_index(times), name="cashflow")
    return s.groupby(level=0).sum().sort_index()


def history_pairs_to_series(pairs: Iterable[Any], *, name: str = "value") -> pd.Series:
    """Hyperliquid ``[[ms, "123.4"], ...]`` → UTC series."""
    times: list[pd.Timestamp] = []
    vals: list[float] = []
    for row in pairs or []:
        if not row or len(row) < 2:
            continue
        times.append(ms_to_utc(row[0]))
        vals.append(float(row[1]))
    if not times:
        return pd.Series(dtype=float, name=name)
    s = pd.Series(vals, index=_as_utc_index(times), name=name)
    return s.groupby(level=0).last().sort_index()


def portfolio_window(payload: Any, window: str = "perpAllTime") -> dict[str, Any]:
    """Pick one window from a ``type=portfolio`` response."""
    if isinstance(payload, dict):
        inner = payload.get(window) or payload.get("data") or payload
        if isinstance(inner, dict) and "accountValueHistory" in inner:
            return inner
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, (list, tuple)) and len(item) >= 2 and item[0] == window:
                return item[1] if isinstance(item[1], dict) else {}
            if isinstance(item, dict) and item.get("window") == window:
                return item
    return {}


def fills_coin_pnl(
    fills: Iterable[Mapping[str, Any]],
    coin: str,
) -> pd.Series:
    """Daily realized fill PnL (closedPnl − USDC fee) for one coin."""
    target = normalize_coin(coin)
    times: list[pd.Timestamp] = []
    pnls: list[float] = []
    for fill in fills:
        if not isinstance(fill, Mapping):
            continue
        if normalize_coin(str(fill.get("coin") or "")) != target:
            continue
        t = fill.get("time")
        if t is None:
            continue
        closed = float(fill.get("closedPnl") or 0.0)
        fee = float(fill.get("fee") or 0.0)
        token = str(fill.get("feeToken") or "USDC").upper()
        fee_usdc = fee if token in {"USDC", "USD"} else 0.0
        times.append(ms_to_utc(t))
        pnls.append(closed - fee_usdc)
    if not times:
        return pd.Series(dtype=float, name="coin_pnl")
    s = pd.Series(pnls, index=_as_utc_index(times), name="coin_pnl")
    return s.groupby(s.index.floor("D")).sum().sort_index()


def funding_coin_pnl(
    events: Iterable[Mapping[str, Any]],
    coin: str,
) -> pd.Series:
    target = normalize_coin(coin)
    times: list[pd.Timestamp] = []
    pnls: list[float] = []
    for ev in events:
        if not isinstance(ev, Mapping):
            continue
        delta = ev.get("delta") if isinstance(ev.get("delta"), Mapping) else ev
        if not isinstance(delta, Mapping):
            continue
        if str(delta.get("type") or "") != "funding":
            continue
        if normalize_coin(str(delta.get("coin") or "")) != target:
            continue
        t = ev.get("time")
        if t is None:
            continue
        times.append(ms_to_utc(t))
        pnls.append(float(delta.get("usdc") or 0.0))
    if not times:
        return pd.Series(dtype=float, name="funding")
    s = pd.Series(pnls, index=_as_utc_index(times), name="funding")
    return s.groupby(s.index.floor("D")).sum().sort_index()


def contribution_returns(pnl: pd.Series, equity: pd.Series) -> pd.Series:
    """Coin (or sleeve) PnL as a return on prior *account* equity."""
    eq = pd.Series(equity, dtype=float).sort_index()
    p = pd.Series(pnl, dtype=float).sort_index()
    idx = eq.index.union(p.index).sort_values()
    eq = eq.reindex(idx).ffill()
    p = p.reindex(idx).fillna(0.0)
    prev = eq.shift(1)
    ret = p / prev
    return ret.where(prev.abs() > 1e-8).rename("contribution")


def segment_metrics(returns: pd.Series, *, annualization: float) -> dict[str, float]:
    r = pd.Series(returns, dtype=float).dropna()
    n = int(len(r))
    if n < 2:
        return {
            "Sharpe": 0.0,
            "CAGR": 0.0,
            "MaxDD": 0.0,
            "TotalReturn": 0.0,
            "Vol": 0.0,
            "bars": float(n),
            "psr_gt0": float("nan"),
        }
    cum = (1.0 + r).cumprod()
    dd = cum / cum.cummax() - 1.0
    vol = float(r.std(ddof=1))
    sharpe = sharpe_from_returns(r, annualization)
    cagr = float(cum.iloc[-1] ** (float(annualization) / n) - 1.0) if n > 0 else 0.0
    sr_period = float(r.mean() / vol) if vol > 0 else 0.0
    psr = probabilistic_sharpe(
        sr_period,
        0.0,
        n,
        skew=float(r.skew()) if n > 2 else 0.0,
        kurtosis=float(r.kurtosis() + 3.0) if n > 3 else 3.0,
    )
    return {
        "Sharpe": float(sharpe),
        "CAGR": float(cagr),
        "MaxDD": float(dd.min()) if len(dd) else 0.0,
        "TotalReturn": float(cum.iloc[-1] - 1.0),
        "Vol": float(vol * np.sqrt(float(annualization))) if vol > 0 else 0.0,
        "bars": float(n),
        "psr_gt0": float(psr) if np.isfinite(psr) else float("nan"),
    }


def split_is_oos(
    returns: pd.Series,
    oos_start: str | pd.Timestamp,
) -> tuple[pd.Series, pd.Series]:
    r = pd.Series(returns, dtype=float).sort_index()
    cut = pd.Timestamp(oos_start)
    if cut.tzinfo is None:
        cut = cut.tz_localize("UTC")
    else:
        cut = cut.tz_convert("UTC")
    if r.index.tz is None:
        r.index = r.index.tz_localize("UTC")
    return r[r.index < cut], r[r.index >= cut]


@dataclass
class WalletRecord:
    wallet: str
    equity: pd.Series
    cashflow: pd.Series
    coin_pnl: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    meta: dict[str, Any] = field(default_factory=dict)

    def twr(
        self,
        *,
        freq: str = "1D",
        timing: str = "open",
        min_active_equity: float = 0.0,
    ) -> pd.Series:
        eq, cf = resample_equity_cashflow(self.equity, self.cashflow, freq=freq)
        return twr_returns(eq, cf, timing=timing, min_active_equity=min_active_equity)

    def naive(self, *, freq: str = "1D", min_active_equity: float = 0.0) -> pd.Series:
        eq, _ = resample_equity_cashflow(self.equity, self.cashflow, freq=freq)
        if min_active_equity > 0:
            eq = eq.where(eq.abs() >= float(min_active_equity))
        return naive_equity_returns(eq)

    def coin_contribution(self, *, freq: str = "1D", min_active_equity: float = 0.0) -> pd.Series:
        eq, _ = resample_equity_cashflow(self.equity, self.cashflow, freq=freq)
        if min_active_equity > 0:
            eq = eq.where(eq.abs() >= float(min_active_equity))
        pnl = pd.Series(self.coin_pnl, dtype=float)
        if pnl.empty:
            return pd.Series(0.0, index=eq.index, name="contribution")
        if not isinstance(pnl.index, pd.DatetimeIndex):
            pnl.index = _as_utc_index(pnl.index)
        pnl_r = pnl.resample(freq).sum().reindex(eq.index).fillna(0.0)
        return contribution_returns(pnl_r, eq)


def rank_wallets(
    records: Mapping[str, WalletRecord] | Iterable[WalletRecord],
    *,
    oos_start: str,
    annualization: float,
    freq: str = "1D",
    min_is_bars: int = 30,
    min_mean_equity: float = 0.0,
    min_active_equity: float = 0.0,
    coin: str | None = None,
) -> pd.DataFrame:
    """Rank on **IS TWR Sharpe only**. OOS columns are reported, never used to rank."""
    if isinstance(records, Mapping):
        recs = list(records.values())
    else:
        recs = list(records)
    rows: list[dict[str, Any]] = []
    for rec in recs:
        twr = rec.twr(freq=freq, min_active_equity=min_active_equity)
        naive = rec.naive(freq=freq, min_active_equity=min_active_equity)
        is_t, oos_t = split_is_oos(twr, oos_start)
        is_n, oos_n = split_is_oos(naive, oos_start)
        eq, _ = resample_equity_cashflow(rec.equity, rec.cashflow, freq=freq)
        if min_active_equity > 0:
            eq = eq.where(eq.abs() >= float(min_active_equity))
        is_eq, _ = split_is_oos(eq, oos_start)
        mean_eq = float(is_eq.mean()) if len(is_eq) else 0.0
        m_is = segment_metrics(is_t, annualization=annualization)
        m_oos = segment_metrics(oos_t, annualization=annualization)
        m_is_naive = segment_metrics(is_n, annualization=annualization)
        m_oos_naive = segment_metrics(oos_n, annualization=annualization)
        coin_is = coin_oos = {}
        if coin:
            contrib = rec.coin_contribution(freq=freq, min_active_equity=min_active_equity)
            c_is, c_oos = split_is_oos(contrib, oos_start)
            coin_is = segment_metrics(c_is, annualization=annualization)
            coin_oos = segment_metrics(c_oos, annualization=annualization)
        eligible = int(m_is["bars"]) >= int(min_is_bars) and mean_eq >= float(min_mean_equity)
        rows.append(
            {
                "wallet": rec.wallet,
                "eligible": bool(eligible),
                "mean_equity_is": mean_eq,
                "sharpe_is_twr": m_is["Sharpe"],
                "sharpe_oos_twr": m_oos["Sharpe"],
                "sharpe_is_naive": m_is_naive["Sharpe"],
                "sharpe_oos_naive": m_oos_naive["Sharpe"],
                "psr_is_twr": m_is["psr_gt0"],
                "cagr_is_twr": m_is["CAGR"],
                "maxdd_is_twr": m_is["MaxDD"],
                "bars_is": m_is["bars"],
                "bars_oos": m_oos["bars"],
                "cagr_oos_twr": m_oos["CAGR"],
                "maxdd_oos_twr": m_oos["MaxDD"],
                "sharpe_is_coin": coin_is.get("Sharpe", float("nan")) if coin else float("nan"),
                "sharpe_oos_coin": coin_oos.get("Sharpe", float("nan")) if coin else float("nan"),
                **{f"meta_{k}": v for k, v in rec.meta.items() if _is_scalar(v)},
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    eligible = out["eligible"].astype(bool)
    ranks = out.loc[eligible, "sharpe_is_twr"].rank(ascending=False, method="min")
    out["rank_is_twr"] = np.nan
    out.loc[eligible, "rank_is_twr"] = ranks
    return out.sort_values(["eligible", "sharpe_is_twr"], ascending=[False, False]).reset_index(drop=True)


def copy_topk_returns(
    records: Mapping[str, WalletRecord] | Iterable[WalletRecord],
    ranking: pd.DataFrame,
    *,
    oos_start: str,
    top_k: int = 5,
    freq: str = "1D",
) -> tuple[pd.Series, list[str]]:
    """Equal-weight daily TWR of wallets chosen on **IS TWR Sharpe** only."""
    if isinstance(records, Mapping):
        rec_map = {rec.wallet: rec for rec in records.values()}
    else:
        rec_map = {rec.wallet: rec for rec in records}
    picked = (
        ranking.loc[ranking["eligible"].astype(bool)]
        .sort_values("sharpe_is_twr", ascending=False)
        .head(int(top_k))
    )
    names = [str(w) for w in picked["wallet"].tolist()]
    if not names:
        return pd.Series(dtype=float, name="copy_topk"), []
    frame = pd.concat(
        [rec_map[w].twr(freq=freq).rename(w) for w in names if w in rec_map],
        axis=1,
    )
    book = frame.mean(axis=1, skipna=True).rename("copy_topk")
    # Guard: ranking used only IS; this series still contains OOS paths of the frozen names.
    _ = oos_start
    return book, names


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) or value is None


def synthetic_wallet_panel(
    *,
    start: str = "2024-01-01",
    end: str = "2026-06-01",
    seed: int = 7,
    n_noise: int = 24,
) -> dict[str, WalletRecord]:
    """Controlled panel: skill, deposit-faker, BTC specialist, noise, short-lived."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, end, freq="1D", tz="UTC")
    n = len(idx)

    def _rec(name: str, rets: np.ndarray, flows: np.ndarray, coin: np.ndarray, equity0: float = 10_000.0) -> WalletRecord:
        eq = np.empty(n, dtype=float)
        eq[0] = equity0
        # open-timing identity: V_t = (V_{t-1} + CF_t) * (1 + r_t)
        for t in range(1, n):
            eq[t] = (eq[t - 1] + flows[t]) * (1.0 + rets[t])
        # Dollar coin PnL so contribution_returns recovers `coin`.
        coin_s = pd.Series(np.r_[0.0, eq[:-1] * coin[1:]], index=idx)
        return WalletRecord(
            wallet=name,
            equity=pd.Series(eq, index=idx, name="equity"),
            cashflow=pd.Series(flows, index=idx, name="cashflow"),
            coin_pnl=coin_s,
            meta={"kind": name.split("_")[0]},
        )

    skill = 0.0012 + rng.normal(0.0, 0.004, n)  # ~Sharpe 0.0012/0.004 * sqrt(365) ≈ 4.7 before noise
    skill[0] = 0.0
    faker_r = 0.00015 + rng.normal(0.0, 0.008, n)
    faker_r[0] = 0.0
    faker_cf = np.zeros(n)
    # Two large IS deposits that naive pct_change reads as monster returns.
    faker_cf[40] = 40_000.0
    faker_cf[80] = 80_000.0
    btc_only = 0.0009 + rng.normal(0.0, 0.005, n)
    other_bleed = -0.0007 + rng.normal(0.0, 0.006, n)
    btc_only[0] = 0.0
    other_bleed[0] = 0.0
    specialist_r = btc_only + other_bleed  # wallet looks mediocre
    specialist_coin = btc_only  # BTC sleeve is the skill

    recs: dict[str, WalletRecord] = {
        "skill_btc": _rec("skill_btc", skill, np.zeros(n), skill),
        "deposit_faker": _rec("deposit_faker", faker_r, faker_cf, faker_r, equity0=5_000.0),
        "btc_specialist": _rec("btc_specialist", specialist_r, np.zeros(n), specialist_coin),
    }
    for i in range(n_noise):
        r = rng.normal(0.0, 0.012, n)
        r[0] = 0.0
        recs[f"noise_{i:02d}"] = _rec(f"noise_{i:02d}", r, np.zeros(n), r)
    short_r = 0.01 + rng.normal(0.0, 0.003, n)
    short_r[0] = 0.0
    short = _rec("short_lived", short_r, np.zeros(n), short_r)
    # Only 12 days of life in-sample.
    mask = np.zeros(n, dtype=bool)
    mask[:12] = True
    short.equity = short.equity.where(pd.Series(mask, index=idx), np.nan).ffill()
    short.equity.iloc[12:] = np.nan
    recs["short_lived"] = short
    return recs
