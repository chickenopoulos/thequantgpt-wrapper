#!/usr/bin/env python3
"""Smoke-test local lab setup: Python, deps, config, data dir, MCP API."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.config import api_settings, load_config, resolve_path  # noqa: E402
from tqg_client.api import TqgApiClient  # noqa: E402


def _check_python() -> tuple[bool, str]:
    if sys.version_info < (3, 11):
        return False, f"Python {sys.version_info.major}.{sys.version_info.minor} (need >= 3.11)"
    return True, f"Python {sys.version_info.major}.{sys.version_info.minor}"


def _check_imports() -> list[str]:
    required = ("pandas", "numpy", "pyarrow", "vectorbt", "matplotlib", "httpx", "yaml")
    missing = []
    for name in required:
        try:
            importlib.import_module(name if name != "yaml" else "yaml")
        except ImportError:
            missing.append(name)
    return missing


def main() -> int:
    ok = True
    print("TheQuantGPT Cursor Lab — init smoke test\n")

    py_ok, py_msg = _check_python()
    print(f"[{'OK' if py_ok else 'FAIL'}] {py_msg}")
    ok = ok and py_ok

    missing = _check_imports()
    if missing:
        print(f"[FAIL] Missing packages: {', '.join(missing)}")
        print("       Run: pip install -r requirements.txt")
        ok = False
    else:
        print("[OK] Python dependencies")

    cfg_path = _REPO / "config.yaml"
    if not cfg_path.exists():
        print("[FAIL] config.yaml missing — copy config.example.yaml to config.yaml")
        return 1
    try:
        cfg = load_config(cfg_path)
        print("[OK] config.yaml")
    except Exception as exc:
        print(f"[FAIL] config.yaml: {exc}")
        return 1

    data_dir = resolve_path(cfg, "data_dir")
    runs_dir = resolve_path(cfg, "runs_dir")
    for label, path in (("data_dir", data_dir), ("runs_dir", runs_dir)):
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            print(f"[OK] {label} writable: {path}")
        except OSError as exc:
            print(f"[FAIL] {label} not writable: {exc}")
            ok = False

    parquet_files = list(data_dir.rglob("*.parquet"))
    if parquet_files:
        print(f"[OK] Found {len(parquet_files)} parquet file(s) under data/")
    else:
        print("[WARN] No parquet under data/ — upload OHLCV data before backtests")

    try:
        base_url, api_key = api_settings(cfg)
        client = TqgApiClient(base_url, api_key)
        health = client.health()
        print(f"[OK] MCP API health: {health.get('status', health)}")
    except Exception as exc:
        print(f"[FAIL] MCP API: {exc}")
        ok = False

    print()
    if ok:
        print("All critical checks passed. Ready for strategy runs.")
        return 0
    print("Fix failures above before running strategies.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
