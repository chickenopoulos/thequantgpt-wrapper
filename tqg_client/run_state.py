"""Run folder state — durable memory for a strategy research session."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_config, repo_root, resolve_path

RUN_STATUSES = frozenset(
    {
        "created",
        "baseline_complete",
        "psa_complete",
        "robustness_complete",
        "packaged",
        "failed",
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunState:
    run_id: str
    title: str
    created_at: str
    root: str
    status: str = "created"
    numeric_id: int | None = None
    source: str = "cursor_agent"
    symbol: str | None = None
    oos_start_ts: str | None = None
    workflow: str | None = None
    strategy_type: str | None = None
    last_scope: str | None = None
    strategy_spec_path: str = "strategy_spec.json"
    artifacts: dict[str, dict[str, str]] = field(default_factory=dict)
    completed_steps: list[str] = field(default_factory=list)
    defaults: dict[str, Any] = field(default_factory=dict)
    validation_passed: bool = False
    last_validation_at: str | None = None
    last_execution_at: str | None = None
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RunState:
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in raw.items() if k in allowed})

    def artifact_manifest(self) -> dict[str, dict[str, str]]:
        """Namespace injection shape used by strategy scripts."""
        return dict(self.artifacts)

    def register_artifact(self, key: str, path: str, fmt: str) -> None:
        self.artifacts[key] = {"path": path, "format": fmt}

    def mark_step(self, step: str) -> None:
        if step not in self.completed_steps:
            self.completed_steps.append(step)


def default_run_defaults(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    defaults = cfg.get("defaults") or {}
    return {
        "oos_start": str(defaults.get("oos_start", "2025-01-01")),
        "fee": float(defaults.get("fee", 0.00045)),
        "slippage": float(defaults.get("slippage", 0.0005)),
        "interval": str(defaults.get("interval", "1d")),
    }


def new_run_state(
    *,
    run_id: str,
    title: str,
    root: Path,
    numeric_id: int | None = None,
    source: str = "cursor_agent",
    cfg: dict[str, Any] | None = None,
) -> RunState:
    cfg = cfg or load_config()
    defaults = default_run_defaults(cfg)
    rel_root = str(root.relative_to(repo_root()))
    return RunState(
        run_id=run_id,
        numeric_id=numeric_id,
        title=title,
        source=source,
        created_at=_utc_now(),
        root=rel_root,
        status="created",
        oos_start_ts=defaults["oos_start"],
        strategy_spec_path="strategy_spec.json",
        defaults=defaults,
    )


def run_root_from_state(state: RunState) -> Path:
    return (repo_root() / state.root).resolve()


def load_run_state(run_id: str, *, runs_dir: Path | None = None) -> RunState:
    base = runs_dir or resolve_path(load_config(), "runs_dir")
    path = base / run_id / "run.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing run state: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid run.json in {path}")
    return RunState.from_dict(raw)


def save_run_state(state: RunState, *, runs_dir: Path | None = None) -> Path:
    root = run_root_from_state(state)
    path = root / "run.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def load_strategy_spec(run_root: Path) -> dict[str, Any] | None:
    spec_path = run_root / "strategy_spec.json"
    if not spec_path.exists():
        return None
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def merge_execution_feedback(state: RunState, feedback: dict[str, Any]) -> RunState:
    """Update run state after a successful or failed execution."""
    now = _utc_now()
    state.last_execution_at = now

    if feedback.get("success"):
        state.last_error = None
        state.validation_passed = bool(feedback.get("validation_passed", state.validation_passed))
        if feedback.get("validation_passed"):
            state.last_validation_at = now

        snapshot = feedback.get("strategy_snapshot")
        if isinstance(snapshot, dict):
            state.symbol = snapshot.get("symbol") or state.symbol
            state.oos_start_ts = snapshot.get("oos_start_ts") or state.oos_start_ts
            state.workflow = snapshot.get("workflow") or state.workflow
            state.strategy_type = snapshot.get("strategy_type") or state.strategy_type

        spec = feedback.get("strategy_spec")
        if isinstance(spec, dict):
            root = run_root_from_state(state)
            spec_path = root / state.strategy_spec_path
            spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
            state.symbol = spec.get("symbol") or state.symbol
            state.oos_start_ts = spec.get("oos_start_ts") or state.oos_start_ts
            state.workflow = spec.get("workflow") or state.workflow
            state.strategy_type = spec.get("strategy_type") or state.strategy_type

        for key, rel_path in (feedback.get("artifacts") or {}).items():
            if isinstance(rel_path, str):
                fmt = Path(rel_path).suffix.lstrip(".") or "unknown"
                state.register_artifact(key, rel_path, fmt)

        step = feedback.get("completed_step")
        if isinstance(step, str):
            state.mark_step(step)
            if step == "baseline":
                state.status = "baseline_complete"
            elif step == "psa":
                state.status = "psa_complete"
            elif step == "robustness":
                state.status = "robustness_complete"
        elif "metrics" in state.artifacts and state.status == "created":
            state.mark_step("baseline")
            state.status = "baseline_complete"
    else:
        state.status = "failed"
        state.last_error = str(feedback.get("error") or "execution failed")

    return state
