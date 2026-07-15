---
name: tqg-package-run
description: >-
  Validate and package a completed strategy run into reports/ for sharing.
  Use when the user asks to package, bundle, or export artifacts.
---

# Package run

## Preconditions

- Run folder exists under `runs/<run_id>/`
- Strategy code under `code/`
- `artifacts/metrics.json` present
- **`validation_passed: true`** in `run.json` (required by packaging script)

## Workflow

1. Read `runs/<run_id>/run.json` — confirm status and artifacts.
2. If `validation_passed` is false:
   ```bash
   python scripts/tqg_mcp_validate.py <run_id>
   ```
   Or re-run: `python scripts/tqg_run_backtest.py <run_id> --mcp-validate`
3. Package:
   ```bash
   python scripts/tqg_package_artifacts.py <run_id>
   ```
4. Confirm `reports/<run_id>/manifest.json` exists.
5. Optionally zip: `python scripts/tqg_package_artifacts.py <run_id> --zip`

## Override (emergency only)

If the user explicitly accepts packaging without MCP validation:
```bash
python scripts/tqg_package_artifacts.py <run_id> --skip-validation-check
```

## Reply

- `reports/<run_id>/` path
- Key files from `manifest.json`
- Brief metrics summary from packaged `artifacts/metrics.json`
