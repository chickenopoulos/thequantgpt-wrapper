# EQI diagnostic ports (plan)

Worthy additions from the Experienced Quant Investor skill, implemented in this
stack. Not a clone of the 71-paper corpus.

| Item | Layer | Status |
|------|--------|--------|
| CSCV / PBO on `psa_returns_matrix.csv` | wrapper `tqg_client/pbo.py`, `scripts/tqg_pbo.py`; MCP catalog | done |
| Lo Sharpe SE, 95% CI, MinBTL/MinTRL, AR(1) | wrapper `sharpe_diagnostics` on `selection.json` | done |
| Break-even round-trip bps | same diagnostics when turnover is known | done |
| Leakage smells (negative shift, bfill, shuffled split) | core `lookahead_smells` + wrapper `local_validate` | done |
| Audit input tiers + stop rule | `AGENTS.md`, selection + robustness rules | done |
| Ken French attribution (equity only) | `scripts/tqg_factor_attribution.py` | done |
| MCP PBO spec + guidance | `thequantgpt-mcp` | done |

Skipped: paper anchors/debates, purged k-fold ML splitter, cloud-side Ken French fetch.
