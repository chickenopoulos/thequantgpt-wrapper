#!/usr/bin/env python3
"""Ken French factor attribution for equity/ETF lab runs (not strategy code)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from tqg_client.factor_attribution import (  # noqa: E402
    MODELS,
    asset_class_allows,
    attribute,
)
from tqg_client.run_state import load_run_state, load_strategy_spec, run_root_from_state  # noqa: E402
from tqg_client.selection import load_is_returns  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="FF/Carhart attribution on IS returns")
    parser.add_argument("run_id")
    parser.add_argument("--model", default="all", help="capm, ff3, carhart4, ff5, ff5+mom, or all")
    parser.add_argument("--freq", default="monthly", choices=["monthly", "daily"])
    parser.add_argument("--force", action="store_true", help="Run even if asset_class is not equity")
    args = parser.parse_args()

    state = load_run_state(args.run_id)
    run_root = run_root_from_state(state)
    spec = load_strategy_spec(run_root) or {}
    ac = spec.get("asset_class")
    if not asset_class_allows(str(ac) if ac else None, args.force):
        print(
            json.dumps(
                {
                    "error": "not_equity",
                    "asset_class": ac,
                    "hint": "Attribution uses Ken French equity factors. Pass --force only if the return series is equity-like.",
                },
                indent=2,
            )
        )
        return 1
    rets = load_is_returns(run_root)
    if rets is None or len(rets.dropna()) < 24:
        print(json.dumps({"error": "missing_is_returns", "hint": "Need artifacts/returns_is.json"}, indent=2))
        return 1
    models = list(MODELS) if args.model == "all" else [args.model]
    cache = _REPO / "data" / "ken_french"
    out = {"run_id": args.run_id, "asset_class": ac, "models": []}
    for model in models:
        try:
            out["models"].append(attribute(rets, model=model, freq=args.freq, cache=cache))
        except Exception as exc:  # noqa: BLE001
            out["models"].append({"model": model, "error": str(exc)})
    dest = run_root / "artifacts" / "attribution.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
