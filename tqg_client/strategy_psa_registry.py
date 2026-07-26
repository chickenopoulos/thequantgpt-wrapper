"""PSA spec registry for strategy catalog batch runs."""

from __future__ import annotations

from tqg_client.strategy_psa_core import PsaSpec
from tqg_client.strategy_psa_builders import (
    cg01,
    cg02,
    cg03,
    cg04,
    cg05,
    cg06,
    cg07,
    cg08,
    cg09,
    cg12,
    cg13,
    cg15,
    cg16,
    cg17,
    cg20,
    dv01,
    ef01,
    ef03,
    gf02,
    gf08,
    gf10,
    ia01,
    ia02,
    ia03,
    ia04,
    ia05,
    ia08,
    ia10,
    mr01,
    mr02,
    mr03,
    mr04,
    mr05,
    mr06,
    mr10,
    mr11,
    mr12,
    mr13,
    mr14,
    mr15,
    na01,
    na02,
    on02,
    on04,
    on06,
    on09,
    q08,
    q09,
    t01,
    t02,
    t03,
    t04,
    t05,
    t06,
    t08,
    t09,
    t10,
    t13,
    t14,
    taa01,
    taa05,
    taa06,
    taa07,
    v03,
    v07,
    v08,
)


def _skip(id: str, name: str, universe: str, ac: str, reason: str) -> PsaSpec:
    return PsaSpec(id, name, universe, ac, symbol="BTCUSDT", skip_reason=reason)


def all_psa_specs() -> list[PsaSpec]:
    specs: list[PsaSpec] = []

    def add(
        id: str,
        name: str,
        universe: str,
        ac: str,
        symbol: str,
        build,
        baseline: dict,
        grid: dict,
        *,
        interval: str = "1d",
        min_trades: int = 30,
        min_stable_cells: int = 3,
    ) -> None:
        specs.append(
            PsaSpec(
                id=id,
                name=name,
                universe=universe,
                asset_class=ac,
                symbol=symbol,
                interval=interval,
                baseline=baseline,
                grid=grid,
                build=build,
                min_trades=min_trades,
                min_stable_cells=min_stable_cells,
            )
        )

    # Trend
    add("T-01", "Dual MA crossover", "BTCUSDT", "crypto", "BTCUSDT", t01,
        {"fast_ma": 20, "slow_ma": 100}, {"fast_ma": [10, 15, 20, 25, 30, 40, 50, 60]})
    add("T-02", "CMMA trend", "BTCUSDT", "crypto", "BTCUSDT", t02,
        {"lookback": 40}, {"lookback": [20, 30, 40, 50, 60, 80, 100]})
    add("T-03", "Donchian breakout", "BTCUSDT", "crypto", "BTCUSDT", t03,
        {"lookback": 20}, {"lookback": [10, 15, 20, 25, 30, 40, 50]})
    add("T-04", "Donchian + ER gate", "BTCUSDT", "crypto", "BTCUSDT", t04,
        {"lookback": 20, "er_max": 0.3}, {"lookback": [10, 15, 20, 25, 30, 40]})
    add("T-05", "TSMOM", "BTCUSDT", "crypto", "BTCUSDT", t05,
        {"skip_days": 21}, {"skip_days": [10, 15, 21, 30, 40, 50]})
    add("T-06", "Percentile-rank momentum", "BTCUSDT", "crypto", "BTCUSDT", t06,
        {"rank_window": 252, "entry_rank": 0.8, "exit_rank": 0.4},
        {"rank_window": [126, 189, 252, 315]})
    add("T-08", "Vol-filtered trend", "BTCUSDT", "crypto", "BTCUSDT", t08,
        {"vol_window": 90}, {"vol_window": [60, 75, 90, 120, 150]})
    add("T-09", "52-week high breakout", "BTCUSDT", "crypto", "BTCUSDT", t09,
        {"entry_prox": 0.05, "exit_prox": 0.10},
        {"entry_prox": [0.03, 0.04, 0.05, 0.06, 0.07, 0.08]})
    add("T-10", "QQQ/BTC Donchian rotation", "QQQ+BTC", "crypto", "BTCUSDT", t10,
        {"lookback": 20}, {"lookback": [10, 15, 20, 25, 30, 40]})
    add("T-13", "Network momentum hub", "ETHUSDT", "crypto", "ETHUSDT", t13,
        {"lookback": 20}, {"lookback": [10, 15, 20, 25, 30, 40]})
    add("T-14", "FX trend MA", "EURUSD", "fx", "EURUSD", t14,
        {"fast_ma": 50, "slow_ma": 200}, {"fast_ma": [30, 40, 50, 60, 80, 100]}, min_trades=40)

    specs.extend([
        _skip("T-07", "Multi-horizon ensemble", "BTCUSDT", "crypto", "multi-horizon ensemble"),
        _skip("T-11", "Session volume momentum", "BTCUSDT 1h", "crypto", "session clock"),
        _skip("T-12", "Hour-of-day vol tilt", "BTCUSDT 1h", "crypto", "continuous exposure"),
        _skip("T-15", "Commodity dual momentum", "GLD vs USO", "commodity", "dual pick"),
    ])

    # Mean reversion
    add("MR-01", "Bollinger fade", "BTCUSDT", "crypto", "BTCUSDT", mr01,
        {"window": 20, "std_mult": 2.0}, {"window": [15, 20, 25, 30, 40]})
    add("MR-02", "RSI oversold bounce", "BTCUSDT", "crypto", "BTCUSDT", mr02,
        {"rsi_window": 14, "oversold": 30, "exit_rsi": 50}, {"rsi_window": [10, 12, 14, 18, 21]})
    add("MR-03", "RSI + ER gate", "BTCUSDT", "crypto", "BTCUSDT", mr03,
        {"rsi_window": 14, "er_window": 20, "er_min": 0.5, "oversold": 30, "exit_rsi": 50},
        {"rsi_window": [10, 12, 14, 18, 21]}, min_trades=10)
    add("MR-04", "Z-score vs MA", "BTCUSDT", "crypto", "BTCUSDT", mr04,
        {"window": 20, "z_entry": 2.0}, {"window": [15, 20, 25, 30, 40]})
    add("MR-05", "Intraday gap fade", "BTCUSDT 1h", "crypto", "BTCUSDT", mr05,
        {"gap_thr": -0.02}, {"gap_thr": [-0.03, -0.025, -0.02, -0.015, -0.01]}, interval="1h", min_trades=20)
    add("MR-06", "Short-term reversal", "BTCUSDT", "crypto", "BTCUSDT", mr06,
        {"window": 20, "std_mult": 2.0}, {"std_mult": [1.5, 2.0, 2.5, 3.0, 3.5]})
    add("MR-10", "Pairs ratio MR", "BTC/ETH", "crypto", "BTCUSDT", mr10,
        {"window": 60, "z_entry": 2.0}, {"window": [40, 60, 80, 100, 120]}, min_trades=8)
    add("MR-11", "RSI on detrended", "BTCUSDT", "crypto", "BTCUSDT", mr11,
        {"detrend_window": 20, "rsi_window": 2, "oversold": 20, "exit_rsi": 60},
        {"detrend_window": [15, 20, 25, 30, 40]})
    add("MR-12", "Overnight reversal", "BTCUSDT 1h", "crypto", "BTCUSDT", mr12,
        {"overnight_thr": -0.01}, {"overnight_thr": [-0.02, -0.015, -0.01, -0.008, -0.005]}, interval="1h", min_trades=15)
    add("MR-13", "24h ticker fade", "BTCUSDT 1h", "crypto", "BTCUSDT", mr13,
        {"fade_thr": -0.05, "exit_thr": -0.02}, {"fade_thr": [-0.08, -0.06, -0.05, -0.04, -0.03]}, interval="1h")
    add("MR-14", "Low-volume fade", "BTCUSDT", "crypto", "BTCUSDT", mr14,
        {"vol_window": 30, "ret_window": 20}, {"vol_window": [20, 25, 30, 40, 50]})
    add("MR-15", "QQQ RSI MR", "QQQ", "equity", "QQQ", mr15,
        {"rsi_window": 4, "oversold": 25, "exit_rsi": 55, "trend_ma": 200},
        {"rsi_window": [3, 4, 5, 6, 8]}, min_trades=50)

    for sid in ["MR-07", "MR-08", "MR-09"]:
        specs.append(_skip(sid, sid, "SPY", "equity", "calendar effect / skip"))

    # Vol
    add("V-03", "Vol regime switch", "BTCUSDT", "crypto", "BTCUSDT", v03,
        {"vol_window": 90, "mom_window": 231}, {"vol_window": [60, 75, 90, 120]})
    add("V-07", "GARCH vol gate", "BTCUSDT", "crypto", "BTCUSDT", v07,
        {"forecast_window": 5, "mom_window": 60}, {"forecast_window": [3, 5, 7, 10, 14]})
    add("V-08", "Entropy chop filter", "BTCUSDT", "crypto", "BTCUSDT", v08,
        {"entropy_window": 20, "entropy_thr": 0.9, "rsi_window": 14, "oversold": 35, "exit_rsi": 50},
        {"entropy_window": [15, 20, 25, 30]})

    for sid in ["V-01", "V-02", "V-04", "V-05", "V-06"]:
        specs.append(_skip(sid, sid, "BTCUSDT", "crypto", "continuous exposure"))

    # TAA
    add("TAA-01", "Faber 10M SMA", "SPY", "equity", "SPY", taa01,
        {"ma_window": 200}, {"ma_window": [150, 175, 200, 225, 250]}, min_trades=40)
    add("TAA-05", "Bond filter equities", "SPY+TLT", "equity", "SPY", taa05,
        {"bond_window": 60}, {"bond_window": [40, 50, 60, 80, 100]}, min_trades=40)
    add("TAA-06", "Gold/rates triangle", "GLD+TLT", "commodity", "GLD", taa06,
        {"bond_window": 60, "gold_window": 20}, {"bond_window": [40, 60, 80, 100]})
    add("TAA-07", "Crypto vs equity rotation", "BTC+SPY", "multi-asset", "BTCUSDT", taa07,
        {"spy_window": 20}, {"spy_window": [10, 15, 20, 30, 40]})

    for sid in ["TAA-02", "TAA-03", "TAA-04", "TAA-08"]:
        specs.append(_skip(sid, sid, "multi-asset", "equity", "skip PSA v1"))

    # Cross-sectional
    for i in range(1, 11):
        specs.append(_skip(f"XS-{i:02d}", f"XS-{i:02d}", "Binance perps", "cross-section", "CS PSA too expensive"))
    specs.append(_skip("CG-19", "Funding CS mom", "Binance perps", "cross-section", "CS PSA too expensive"))

    # Coinglass
    add("CG-01", "Funding carry", "BTCUSDT", "crypto", "BTCUSDT", cg01,
        {"fund_thr": -0.0001}, {"fund_thr": [-0.0002, -0.00015, -0.0001, -0.00005, -0.00003]})
    add("CG-02", "Funding extreme fade", "BTCUSDT", "crypto", "BTCUSDT", cg02,
        {"quantile_window": 90, "hi_quantile": 0.9}, {"quantile_window": [60, 75, 90, 120]}, min_trades=15)
    add("CG-03", "OI expansion breakout", "BTCUSDT", "crypto", "BTCUSDT", cg03,
        {"oi_diff": 5, "price_window": 5}, {"oi_diff": [3, 5, 7, 10, 14]})
    add("CG-04", "OI divergence fade", "BTCUSDT", "crypto", "BTCUSDT", cg04,
        {"oi_diff": 5, "price_window": 20}, {"price_window": [10, 15, 20, 25, 30]}, min_trades=15)
    add("CG-05", "Liquidation cascade fade", "BTCUSDT", "crypto", "BTCUSDT", cg05,
        {"spike_window": 90, "spike_q": 0.95, "exit_window": 30},
        {"spike_q": [0.90, 0.92, 0.95, 0.97]}, min_trades=20)
    add("CG-06", "Short squeeze setup", "BTCUSDT", "crypto", "BTCUSDT", cg06,
        {"fund_thr": 0.0, "price_window": 5}, {"price_window": [3, 5, 7, 10, 14]})
    add("CG-07", "Taker buy imbalance", "BTCUSDT", "crypto", "BTCUSDT", cg07,
        {"entry_ratio": 0.55, "exit_ratio": 0.5},
        {"entry_ratio": [0.52, 0.54, 0.55, 0.56, 0.58]}, min_trades=5)
    add("CG-08", "Orderbook imbalance", "BTCUSDT", "crypto", "BTCUSDT", cg08,
        {"entry_imb": 0.1, "exit_imb": 0.0}, {"entry_imb": [0.05, 0.08, 0.1, 0.12, 0.15]})
    add("CG-09", "Whale gate + trend", "BTCUSDT", "crypto", "BTCUSDT", cg09,
        {"mom_window": 20}, {"mom_window": [10, 15, 20, 25, 30, 40]})
    add("CG-12", "ETF flow momentum", "BTCUSDT", "crypto", "BTCUSDT", cg12,
        {"flow_window": 5}, {"flow_window": [3, 5, 7, 10, 14]}, min_trades=15)
    add("CG-13", "ETF flow divergence", "BTCUSDT", "crypto", "BTCUSDT", cg13,
        {"flow_window": 5, "price_window": 5}, {"flow_window": [3, 5, 7, 10]}, min_trades=15)
    add("CG-15", "Exchange balance drain", "BTCUSDT", "crypto", "BTCUSDT", cg15,
        {"diff_window": 30}, {"diff_window": [14, 21, 30, 45, 60]}, min_trades=10)
    add("CG-16", "Puell multiple bottom", "BTCUSDT", "crypto", "BTCUSDT", cg16,
        {"entry_thr": 0.5, "exit_thr": 1.0}, {"entry_thr": [0.4, 0.45, 0.5, 0.55, 0.6]}, min_trades=3, min_stable_cells=2)
    add("CG-17", "Basis carry", "BTCUSDT", "crypto", "BTCUSDT", cg17,
        {"median_window": 30}, {"median_window": [15, 20, 30, 45, 60]})
    add("CG-20", "Funding extreme MR", "BTCUSDT", "crypto", "BTCUSDT", cg20,
        {"quantile_window": 90}, {"quantile_window": [60, 75, 90, 120]})

    for sid, reason in [
        ("CG-10", "missing data"),
        ("CG-11", "missing data"),
        ("CG-14", "0 baseline trades"),
        ("CG-18", "0 baseline trades"),
    ]:
        specs.append(_skip(sid, sid, "BTCUSDT", "crypto", reason))

    # On-chain
    add("ON-02", "NUPL regime", "BTC", "crypto", "BTCUSDT", on02,
        {"entry_thr": 0.25, "exit_thr": 0.75}, {"entry_thr": [0.15, 0.20, 0.25, 0.30, 0.35]}, min_trades=3, min_stable_cells=2)
    add("ON-04", "MVRV < 1 value", "BTC", "crypto", "BTCUSDT", on04,
        {"entry_thr": 1.0, "exit_thr": 3.0}, {"entry_thr": [0.8, 0.9, 1.0, 1.1, 1.2]}, min_trades=3, min_stable_cells=2)
    add("ON-06", "SOPR capitulation", "BTC", "crypto", "BTCUSDT", on06,
        {"streak_window": 7, "streak_min": 5}, {"streak_min": [3, 4, 5, 6, 7]}, min_trades=10)
    add("ON-09", "Accumulation proxy", "BTC", "crypto", "BTCUSDT", on09,
        {"diff_window": 30}, {"diff_window": [14, 21, 30, 45, 60]})

    for sid, reason in [
        ("ON-01", "0 baseline trades"),
        ("ON-03", "rare event"),
        ("ON-05", "missing NVT"),
        ("ON-07", "rare cross"),
        ("ON-08", "missing SplyLTH"),
        ("ON-10", "not mapped"),
    ]:
        specs.append(_skip(sid, sid, "BTC", "crypto", reason))

    add("NA-01", "Active address momentum", "BTC", "crypto", "BTCUSDT", na01,
        {"roc_window": 30}, {"roc_window": [14, 21, 30, 45, 60]})
    add("NA-02", "Tx count breakout", "BTC", "crypto", "BTCUSDT", na02,
        {"ma_window": 90}, {"ma_window": [60, 75, 90, 120, 150]})

    specs.append(_skip("NA-03", "NA-03", "BTC", "crypto", "missing column"))
    specs.append(_skip("NA-04", "NA-04", "BTC", "crypto", "missing column"))
    specs.append(_skip("NA-05", "NA-05", "BTC", "crypto", "skip PSA v1"))

    add("EF-01", "Exchange net outflow", "BTC", "crypto", "BTCUSDT", ef01,
        {"diff_window": 7}, {"diff_window": [3, 5, 7, 10, 14]})
    add("EF-03", "ETF + exchange combo", "BTC", "crypto", "BTCUSDT", ef03,
        {"etf_window": 5, "bal_window": 7}, {"etf_window": [3, 5, 7, 10]}, min_trades=15)

    specs.append(_skip("EF-02", "EF-02", "BTC", "crypto", "miner flows"))
    specs.append(_skip("EF-04", "EF-04", "BTC", "crypto", "stablecoin flow"))

    add("DV-01", "Funding trend", "BTC", "crypto", "BTCUSDT", dv01,
        {"cum_window": 30}, {"cum_window": [14, 21, 30, 45, 60]}, min_trades=5)

    for sid in ["DV-02", "DV-03", "DV-04", "DV-05"]:
        specs.append(_skip(sid, sid, "BTC", "crypto", "missing talos/data"))

    specs.append(_skip("GF-01", "GF-01", "BTC", "crypto", "0 baseline trades"))
    add("GF-02", "Bear late-stage ETF", "BTC", "crypto", "BTCUSDT", gf02,
        {"smooth_window": 30}, {"smooth_window": [20, 25, 30, 40, 50]})
    for sid in ["GF-03", "GF-04", "GF-05", "GF-09"]:
        specs.append(_skip(sid, sid, "BTC", "crypto", "0 baseline trades"))
    specs.append(_skip("GF-06", "GF-06", "BTC+DXY", "multi-asset", "continuous exposure"))
    specs.append(_skip("GF-07", "GF-07", "BTC", "crypto", "options max pain"))
    add("GF-08", "Vol compression breakout", "BTC", "crypto", "BTCUSDT", gf08,
        {"vol_quantile": 0.1, "breakout_window": 20, "exit_window": 10},
        {"breakout_window": [10, 15, 20, 25, 30]}, min_trades=8)
    add("GF-10", "Week 28 scorecard", "BTC", "crypto", "BTCUSDT", gf10,
        {"score_thr": 2, "mv_thr": 1.5, "fund_abs": 0.0001},
        {"score_thr": [2, 3]}, min_trades=3, min_stable_cells=2)

    add("IA-01", "BTC leads ETH", "ETHUSDT", "crypto", "ETHUSDT", ia01,
        {"lag_days": 1}, {"lag_days": [1, 2, 3, 5]})
    add("IA-02", "SPY leads BTC", "BTCUSDT", "crypto", "BTCUSDT", ia02,
        {"spy_window": 5}, {"spy_window": [3, 5, 7, 10, 15]})
    add("IA-03", "Gold/BTC ratio MR", "PAXG/BTC", "crypto", "BTCUSDT", ia03,
        {"window": 60, "z_entry": 2.0}, {"window": [40, 60, 80, 100]}, min_trades=3, min_stable_cells=2)
    add("IA-04", "Copper/gold risk-on", "BTC", "crypto", "BTCUSDT", ia04,
        {"ratio_window": 20}, {"ratio_window": [10, 15, 20, 30, 40]})
    add("IA-05", "Oil shock risk-off", "BTCUSDT", "crypto", "BTCUSDT", ia05,
        {"shock_window": 5, "shock_thr": 0.08}, {"shock_thr": [0.06, 0.07, 0.08, 0.09, 0.10]}, min_trades=3, min_stable_cells=2)
    add("IA-08", "ETH/BTC rotation", "ETHUSDT", "crypto", "ETHUSDT", ia08,
        {"mom_window": 20}, {"mom_window": [10, 15, 20, 25, 30]})
    specs.append(_skip("IA-09", "IA-09", "BTCUSDT", "crypto", "continuous DXY filter"))
    add("IA-10", "Intermarket divergence", "ETH lag BTC", "crypto", "ETHUSDT", ia10,
        {"lead_thr": 0.02}, {"lead_thr": [0.015, 0.02, 0.025, 0.03, 0.04]})

    specs.append(_skip("IA-06", "IA-06", "NVDAUSDT", "crypto", "data error"))
    specs.append(_skip("IA-07", "IA-07", "perp basket", "crypto", "rotation basket"))

    for sid in ["Q-01", "Q-02", "Q-03", "Q-04", "Q-05", "Q-07", "Q-10"]:
        specs.append(_skip(sid, sid, "—", "—", "fundamentals/macro required"))
    specs.append(_skip("Q-06", "Q-06", "^VIX", "vol", "alias V-05 continuous"))
    add("Q-08", "Recursive LS proxy", "BTCUSDT", "crypto", "BTCUSDT", q08,
        {"window": 20}, {"window": [10, 15, 20, 25, 30, 40]})
    add("Q-09", "Regime overlay proxy", "BTCUSDT", "crypto", "BTCUSDT", q09,
        {"vol_window": 20, "mom_window": 60}, {"mom_window": [40, 50, 60, 80, 100]})

    return specs
