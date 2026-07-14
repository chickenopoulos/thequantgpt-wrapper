#!/usr/bin/env python3
"""Smoke-test local lab setup: Python, deps, config, data dir, optional backtest."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.config import api_settings, load_config, resolve_path  # noqa: E402
from tqg_client.api import TqgApiClient  # noqa: E402
from tqg_client.execution import run_strategy_script  # noqa: E402
from tqg_client.run_state import load_run_state, merge_execution_feedback, save_run_state  # noqa: E402


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


def _run_demo_backtest() -> tuple[bool, str]:
    demo_id = "demo_btc_mr"
    runs_dir = resolve_path(load_config(), "runs_dir")
    if not (runs_dir / demo_id / "code").exists():
        return False, f"Missing runs/{demo_id}/code/ — add demo strategy or skip --run-demo"
    try:
        state = load_run_state(demo_id)
        feedback = run_strategy_script(state)
        state = merge_execution_feedback(state, feedback)
        save_run_state(state)
        if not feedback.get("success"):
            return False, feedback.get("error", "demo backtest failed")
        return True, f"Demo backtest OK — status={state.status}"
    except Exception as exc:
        return False, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="TheQuantGPT Cursor Lab smoke test")
    parser.add_argument("--run-demo", action="store_true", help="Execute runs/demo_btc_mr backtest")
    parser.add_argument("--skip-mcp", action="store_true", help="Skip MCP API health check")
    args = parser.parse_args()

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

    if not args.skip_mcp:
        try:
            base_url, api_key = api_settings(cfg)
            client = TqgApiClient(base_url, api_key)
            health = client.health()
            print(f"[OK] MCP API health: {health.get('status', health)}")
        except Exception as exc:
            print(f"[WARN] MCP API: {exc}")
            print("       Phase 1 local layer can run with --skip-mcp")

    if args.run_demo:
        demo_ok, demo_msg = _run_demo_backtest()
        print(f"[{'OK' if demo_ok else 'FAIL'}] Demo backtest: {demo_msg}")
        ok = ok and demo_ok

    print()
    if ok:
        print("All critical checks passed. Ready for strategy runs.")
        return 0
    print("Fix failures above before running strategies.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
