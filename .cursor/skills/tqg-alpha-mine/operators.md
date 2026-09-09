# Operator catalog

The evaluator allows only these names. Attribute access, imports, and subscripts are rejected. The finished signal is lagged 1 bar before scoring.

## Operands (panels)

| Name | Meaning |
|------|---------|
| `open` `high` `low` `close` `volume` | OHLCV |
| `ret` | `close.pct_change()` |
| `intra` | `close - open` |
| `rng` | `high - low` |
| `upper_wick` | `high - max(open, close)` |
| `lower_wick` | `min(open, close) - low` |
| `typical` | `(high+low+close)/3` |
| `dollar_volume` | `close * volume` |
| extra numeric columns | Any other long-panel column that is a Python identifier (lowercased) and does not collide with an operator. Use this for joined Coinglass/Talos fields such as `funding` or `adr_act`. |

## Operators

Time-series (per name): `ts_delay`/`ts_shift`, `ts_delta`, `ts_sum`, `ts_mean`, `ts_std`, `ts_zscore`, `ts_rank`, `ts_min`, `ts_max`, `ts_ema`, `ts_corr`.

Cross-sectional (per date): `cs_rank`, `cs_zscore`, `cs_demean`, `cs_winsorize`.

Element-wise: `log`, `abs`, `sign`, `neg`, `relu`, `div`, `cwise_max`, `cwise_min`, plus `+ - * /`.

Windows are integer literals, e.g. `ts_corr(close, volume, 20)`. `--mutate` replaces the **last** integer in the expression.

## Examples

```text
cs_zscore(intra)
-cs_rank(ts_delta(close, 1))
-cs_zscore(ts_corr(close, volume, 20))
cs_zscore(div(upper_wick, rng))
cs_demean(cs_zscore(intra))
```
