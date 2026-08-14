from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]


def repo_root() -> Path:
    return _REPO_ROOT


def load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE pairs from .env without overriding existing environment vars."""
    env_path = path or (_REPO_ROOT / ".env")
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(path: Path | None = None) -> dict[str, Any]:
    load_dotenv()
    cfg_path = path or (_REPO_ROOT / "config.yaml")
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"Missing {cfg_path}. Copy config.example.yaml to config.yaml and edit."
        )
    with cfg_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid config format in {cfg_path}")
    return data


def resolve_path(cfg: dict[str, Any], key: str) -> Path:
    rel = cfg.get(key, key)
    return (_REPO_ROOT / str(rel)).resolve()


def api_settings(cfg: dict[str, Any]) -> tuple[str, str]:
    api = cfg.get("tqg_api") or {}
    base_url = os.environ.get("TQG_API_BASE_URL", "").strip() or str(api.get("base_url", "")).rstrip("/")
    env_name = str(api.get("api_key_env", "TQG_API_KEY"))
    api_key = os.environ.get(env_name, "").strip()
    if not base_url:
        raise ValueError("config.yaml: tqg_api.base_url is required (or set TQG_API_BASE_URL)")
    if not api_key:
        raise ValueError(f"Set {env_name} in .env (or the environment) for MCP API access")
    return base_url, api_key
