# OHLCV data format (Cursor Lab)

Client data stays on your server. TheQuantGPT is **asset-class agnostic** — crypto, equities, FX, bonds, metals, commodities, and other OHLCV series are all in scope.

## Bundled with a fresh clone

Binance **daily** OHLCV (spot + USDT-M futures) ships in the repo:

```text
data/binance/binance_futures_ohlcv_1d.parquet
data/binance/binance_spot_ohlcv_1d.parquet
```

These are long/tidy files with an `asset` column (e.g. `BTCUSDT`). Hourly bars, other venues, and extra vendor dumps are **not** shipped — add them locally under `data/` as needed.

## Preferred: local files under `data/`

Place parquet or CSV files anywhere under `data/`. The loader searches recursively by symbol name.

### Example layouts

```text
data/
  binance/
    binance_futures_ohlcv_1d.parquet    # crypto (long/tidy format)
  equities/
    SPY_1d.parquet
  fx/
    EURUSD_1d.csv
  metals/
    GC_F_1d.parquet
```

### Required columns

| Column | Type | Notes |
|--------|------|--------|
| `time` | datetime (UTC) | Bar open or close time — be consistent |
| `asset` or `symbol` | string | e.g. `BTCUSDT`, `SPY`, `EURUSD=X`, `GC=F` |
| `open`, `high`, `low`, `close` | float | Prices |
| `volume` | float | Volume or notional (document units in `strategy_spec.json`) |

Optional: `interval` (`1d`, `1h`, …), `quote_asset_volume`, `number_of_trades`.

Single-symbol files (no `asset` column) are fine when the filename contains the ticker.

## Loading data (Python)

```python
from pathlib import Path
from tqg_client.market_data import load_market_data, default_annualization

# Local first, then yfinance for public OHLCV when no local match exists
ohlcv, source = load_market_data("SPY", data_dir=Path("data"), interval="1d")
ann = default_annualization("SPY", asset_class="equity")  # 252

btc, source = load_market_data("BTCUSDT", data_dir=Path("data"), interval="1d")
ann = default_annualization("BTCUSDT", asset_class="crypto")  # 365
```

Legacy helper for a known long-format crypto parquet:

```python
from tqg_client.market_data import load_symbol_from_parquet

btc = load_symbol_from_parquet("data/binance/binance_futures_ohlcv_1d.parquet", "BTCUSDT")
```

## Rules for agents

1. **Inspect `data/`** before assuming a data source or asset class.
2. **Prefer local files** when the user has uploaded data.
3. **yfinance** is acceptable for public OHLCV when local files are missing — do not upload client files externally.
4. **Filter** to a single instrument before single-name backtests.
5. **Timezone:** normalize to UTC; index strategies on bar time.
6. **Lag indicators** by at least 1 bar — no same-bar lookahead.
7. **Annualization:** match the asset calendar (`252` typical equities/bonds, `365` for 24/7 markets like crypto/FX).
8. **OOS default:** `2025-01-01` unless the user changes it.

## Where to get data

You source and upload data (exchange dumps, vendor feeds, yfinance cache, or your own ETL). TheQuantGPT does not host your market data.
