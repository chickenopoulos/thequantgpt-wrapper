#!/usr/bin/env python3
"""Write project Cursor MCP config (.cursor/mcp.json) for this clone."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
MCP_JSON = _REPO / ".cursor" / "mcp.json"
ENV_FILE = _REPO / ".env"
ENV_EXAMPLE = _REPO / ".env.example"


def _venv_python() -> Path:
    if os.name == "nt":
        candidate = _REPO / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = _REPO / ".venv" / "bin" / "python"
    if candidate.is_file():
        return Path(os.path.abspath(candidate))
    exe = Path(os.path.abspath(sys.executable))
    try:
        exe.relative_to(_REPO.resolve())
        return exe
    except ValueError:
        pass
    raise FileNotFoundError(
        f"No venv python at {candidate}. Create it first:\n"
        "  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    )


def _ensure_env_file() -> None:
    if ENV_FILE.exists():
        text = ENV_FILE.read_text(encoding="utf-8")
        if "TQG_API_KEY=" in text and "paste-your-api-key-here" not in text:
            return
        env_key = os.environ.get("TQG_API_KEY", "").strip()
        if env_key and "paste-your-api-key-here" in text:
            ENV_FILE.write_text(f"TQG_API_KEY={env_key}\n", encoding="utf-8")
            return
        if "TQG_API_KEY=" in text:
            return
        ENV_FILE.write_text(text.rstrip() + "\nTQG_API_KEY=paste-your-api-key-here\n", encoding="utf-8")
        return

    env_key = os.environ.get("TQG_API_KEY", "").strip()
    if env_key:
        ENV_FILE.write_text(f"TQG_API_KEY={env_key}\n", encoding="utf-8")
        return
    if ENV_EXAMPLE.exists():
        ENV_FILE.write_text(ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        ENV_FILE.write_text("TQG_API_KEY=paste-your-api-key-here\n", encoding="utf-8")


def _env_key_ready() -> bool:
    if not ENV_FILE.exists():
        return False
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("TQG_API_KEY="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            return bool(value) and value != "paste-your-api-key-here"
    return False


def write_mcp_json(*, force: bool) -> Path:
    python = _venv_python()
    payload = {
        "mcpServers": {
            "thequantgpt": {
                "command": str(python),
                "args": [str((_REPO / "scripts" / "tqg_mcp_bridge.py").resolve())],
                "envFile": str(ENV_FILE.resolve()),
            }
        }
    }
    MCP_JSON.parent.mkdir(parents=True, exist_ok=True)
    if MCP_JSON.exists() and not force:
        existing = json.loads(MCP_JSON.read_text(encoding="utf-8"))
        if existing != payload:
            print(
                f"note: {MCP_JSON} already exists and differs from the generated config.\n"
                "      Leaving it in place. Re-run with --force to overwrite.",
                file=sys.stderr,
            )
        return MCP_JSON
    MCP_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return MCP_JSON


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write .cursor/mcp.json so Cursor can load TheQuantGPT MCP tools"
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing .cursor/mcp.json")
    args = parser.parse_args()

    try:
        python = _venv_python()
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    _ensure_env_file()
    path = write_mcp_json(force=args.force)

    print(f"Cursor MCP config: {path}")
    print(f"  command: {python}")
    print(f"  envFile: {ENV_FILE.resolve()}")
    if _env_key_ready():
        print("[OK] .env has TQG_API_KEY")
    else:
        print("[WARN] Edit .env and set TQG_API_KEY before enabling the server in Cursor")

    print(
        "\nIn Cursor:\n"
        "  1. Open this repo as the workspace (File → Open Folder)\n"
        "  2. Cursor Settings → MCP\n"
        "  3. Enable the project server named thequantgpt\n"
        "  4. Confirm tools appear: tqg_get_guidance, tqg_validate_strategy_code, tqg_get_robustness_spec\n"
        "  5. If it fails, reload the window and check .env + .venv"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
