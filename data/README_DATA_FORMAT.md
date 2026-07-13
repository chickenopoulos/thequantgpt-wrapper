# Crypto OHLCV data format (Cursor Lab)

Client data stays on your server. This repo expects **Binance futures daily OHLCV** in long (tidy) parquet format.

## Canonical layout

```text
data/
  binance/
    binance_futures_ohlcv_1d.parquet
```

## Required columns

| Column | Type | Notes |
|--------|------|--------|
| `time` | datetime (UTC) | Bar open or close time — be consistent |
| `asset` or `symbol` | string | e.g. `BTCUSDT` |
| `open`, `high`, `low`, `close` | float | USD-margined perp prices |
| `volume` | float | Base asset volume |

Optional: `interval` (`1d`), `quote_asset_volume`, `number_of_trades`.

## Loading one symbol (Python)

```python
from pathlib import Path
from tqg_client.market_data import load_symbol_from_parquet, load_symbol_close

path = Path("data/binance/binance_futures_ohlcv_1d.parquet")
btc = load_symbol_from_parquet(path, "BTCUSDT", interval="1d")
close = load_symbol_close(path, "BTCUSDT")
```

## Rules for agents

1. **Do not invent** file paths or column names — inspect `data/` first.
2. **Filter** to a single `asset` before backtesting single-name strategies.
3. **Timezone:** normalize to UTC; index strategies on `time`.
4. **Lag indicators** by at least 1 bar — no same-bar lookahead.
5. **OOS default:** `2025-01-01` unless the user changes it.

## CSV alternative

If using CSV, use the same column names. One file per symbol is fine:

```text
data/binance/BTCUSDT_1d.csv
```

## Where to get data

You source and upload data (exchange dumps, vendor feeds, or your own ETL). TheQuantGPT does not host your market data.
