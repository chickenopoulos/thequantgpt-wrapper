"""Cross-run lab memory — derived index over runs/<id>/ folders."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import load_config, repo_root, resolve_path

log = logging.getLogger(__name__)

INDEX_SCHEMA_VERSION = 1
LAB_DIR_NAME = "_lab"
SKIP_DIR_NAMES = frozenset({LAB_DIR_NAME, ".git", "__pycache__"})

VERDICTS = frozenset(
    {
        "promising",
        "no_edge",
        "killed",
        "needs_robustness",
        "packaged",
    }
)

METRIC_KEYS = ("Sharpe", "CAGR", "MaxDD")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("failed to read JSON %s: %s", path, exc)
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def lab_index_dir(*, cfg: dict[str, Any] | None = None, runs_dir: Path | None = None) -> Path:
    """Resolve runs/_lab (or config override)."""
    cfg = cfg or load_config()
    if runs_dir is None:
        runs_dir = resolve_path(cfg, "runs_dir")
    override = cfg.get("lab_index_dir")
    if override:
        path = Path(str(override))
        if not path.is_absolute():
            path = (repo_root() / path).resolve()
        return path
    return (runs_dir / LAB_DIR_NAME).resolve()


def index_path(*, cfg: dict[str, Any] | None = None, runs_dir: Path | None = None) -> Path:
    return lab_index_dir(cfg=cfg, runs_dir=runs_dir) / "index.json"


def index_meta_path(*, cfg: dict[str, Any] | None = None, runs_dir: Path | None = None) -> Path:
    return lab_index_dir(cfg=cfg, runs_dir=runs_dir) / "index.meta.json"


def runs_base(*, cfg: dict[str, Any] | None = None, runs_dir: Path | None = None) -> Path:
    cfg = cfg or load_config()
    return runs_dir or resolve_path(cfg, "runs_dir")


def list_run_ids(*, cfg: dict[str, Any] | None = None, runs_dir: Path | None = None) -> list[str]:
    """Return run folder names that contain run.json (skip _lab and nested junk)."""
    base = runs_base(cfg=cfg, runs_dir=runs_dir)
    if not base.is_dir():
        return []
    ids: list[str] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir() or child.name in SKIP_DIR_NAMES:
            continue
        if child.name.startswith("."):
            continue
        if (child / "run.json").is_file():
            ids.append(child.name)
    return ids


def load_lab_meta(run_root: Path) -> dict[str, Any]:
    """Load optional runs/<id>/lab_meta.json sidecar."""
    return _read_json(run_root / "lab_meta.json") or {}


def save_lab_meta(run_root: Path, meta: dict[str, Any]) -> Path:
    path = run_root / "lab_meta.json"
    _write_json(path, meta)
    return path


def _compact_metrics(block: Any) -> dict[str, float] | None:
    if not isinstance(block, dict):
        return None
    out: dict[str, float] = {}
    for key in METRIC_KEYS:
        val = block.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            out[key] = float(val)
    return out or None


def _normalize_params(params: Any) -> dict[str, Any]:
    if not isinstance(params, dict):
        return {}
    # Drop non-fingerprint noise; keep scalar/list values only.
    cleaned: dict[str, Any] = {}
    for key in sorted(params.keys(), key=str):
        val = params[key]
        if isinstance(val, (str, int, float, bool)) or val is None:
            cleaned[str(key)] = val
        elif isinstance(val, list) and all(
            isinstance(x, (str, int, float, bool)) or x is None for x in val
        ):
            cleaned[str(key)] = val
    return cleaned


def params_fingerprint(
    *,
    workflow: str | None,
    strategy_type: str | None,
    symbol: str | None,
    interval: str | None,
    params: dict[str, Any] | None = None,
) -> str:
    """Stable string for near-duplicate detection."""
    parts = [
        str(workflow or ""),
        str(strategy_type or ""),
        str(symbol or ""),
        str(interval or ""),
    ]
    normalized = _normalize_params(params or {})
    for key, val in normalized.items():
        parts.append(f"{key}={json.dumps(val, sort_keys=True, separators=(',', ':'))}")
    return "|".join(parts)


def _report_excerpt(run_root: Path, *, limit: int = 500) -> str | None:
    report = run_root / "report.md"
    if not report.is_file():
        return None
    try:
        text = report.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    # Collapse whitespace for index compactness.
    collapsed = re.sub(r"\s+", " ", text)
    if len(collapsed) > limit:
        return collapsed[: limit - 1].rstrip() + "…"
    return collapsed


def _flow_summary(run_root: Path) -> tuple[int, str | None]:
    flow = _read_json(run_root / "flow.json") or {}
    turns = flow.get("turns") or []
    if not isinstance(turns, list):
        return 0, None
    last_prompt: str | None = None
    for turn in reversed(turns):
        if not isinstance(turn, dict):
            continue
        msg = turn.get("user_message")
        if isinstance(msg, str) and msg.strip():
            last_prompt = msg.strip()
            break
    return len(turns), last_prompt


def _file_mtime_iso(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _merge_memory_fields(
    run_data: dict[str, Any],
    lab_meta: dict[str, Any],
) -> dict[str, Any]:
    """Prefer run.json fields, then lab_meta sidecar."""

    def pick(key: str, default: Any = None) -> Any:
        if key in run_data and run_data[key] is not None:
            return run_data[key]
        if key in lab_meta and lab_meta[key] is not None:
            return lab_meta[key]
        return default

    verdict = pick("verdict")
    if isinstance(verdict, str) and verdict not in VERDICTS:
        # Keep unknown verdicts visible rather than dropping them.
        pass

    tags = pick("tags", [])
    if not isinstance(tags, list):
        tags = []
    tags = [str(t) for t in tags if t is not None]

    related = pick("related_runs", [])
    if not isinstance(related, list):
        related = []
    related = [str(r) for r in related if r]

    return {
        "verdict": verdict if isinstance(verdict, str) else None,
        "tags": tags,
        "related_runs": related,
        "hypothesis": pick("hypothesis") if isinstance(pick("hypothesis"), str) else None,
        "kill_reason": pick("kill_reason") if isinstance(pick("kill_reason"), str) else None,
    }


def extract_run_card(
    run_id: str,
    *,
    cfg: dict[str, Any] | None = None,
    runs_dir: Path | None = None,
) -> dict[str, Any]:
    """Build a summary card for one run from on-disk artifacts."""
    cfg = cfg or load_config()
    base = runs_base(cfg=cfg, runs_dir=runs_dir)
    run_root = base / run_id
    run_json_path = run_root / "run.json"
    run_data = _read_json(run_json_path)
    if run_data is None:
        raise FileNotFoundError(f"Missing or invalid run.json for run {run_id}: {run_json_path}")

    lab_meta = load_lab_meta(run_root)
    memory = _merge_memory_fields(run_data, lab_meta)

    spec = _read_json(run_root / "strategy_spec.json") or {}
    metrics_raw = _read_json(run_root / "artifacts" / "metrics.json") or {}

    defaults = run_data.get("defaults") if isinstance(run_data.get("defaults"), dict) else {}
    workflow = run_data.get("workflow") or spec.get("workflow")
    strategy_type = run_data.get("strategy_type") or spec.get("strategy_type")
    symbol = run_data.get("symbol") or spec.get("symbol")
    interval = (
        spec.get("interval")
        or defaults.get("interval")
        or (cfg.get("defaults") or {}).get("interval")
    )
    asset_class = spec.get("asset_class")
    oos_start = run_data.get("oos_start_ts") or spec.get("oos_start_ts")

    params = spec.get("params") if isinstance(spec.get("params"), dict) else {}
    if not params:
        snap = metrics_raw.get("strategy_snapshot")
        if isinstance(snap, dict) and isinstance(snap.get("params"), dict):
            params = snap["params"]

    turn_count, last_user_prompt = _flow_summary(run_root)
    updated_at = (
        run_data.get("last_execution_at")
        or run_data.get("last_validation_at")
        or _file_mtime_iso(run_json_path)
        or run_data.get("created_at")
        or _utc_now()
    )

    rel_root = f"runs/{run_id}"
    card: dict[str, Any] = {
        "run_id": str(run_data.get("run_id") or run_id),
        "title": str(run_data.get("title") or run_id),
        "created_at": run_data.get("created_at"),
        "updated_at": updated_at,
        "status": run_data.get("status"),
        "symbol": symbol,
        "asset_class": asset_class,
        "workflow": workflow,
        "strategy_type": strategy_type,
        "interval": interval,
        "oos_start_ts": oos_start,
        "validation_passed": bool(run_data.get("validation_passed", False)),
        "completed_steps": list(run_data.get("completed_steps") or []),
        "metrics": {
            "in_sample": _compact_metrics(metrics_raw.get("in_sample")),
            "out_of_sample": _compact_metrics(metrics_raw.get("out_of_sample")),
        },
        "params_fingerprint": params_fingerprint(
            workflow=str(workflow) if workflow else None,
            strategy_type=str(strategy_type) if strategy_type else None,
            symbol=str(symbol) if symbol else None,
            interval=str(interval) if interval else None,
            params=params,
        ),
        "verdict": memory["verdict"],
        "tags": memory["tags"],
        "related_runs": memory["related_runs"],
        "hypothesis": memory["hypothesis"],
        "kill_reason": memory["kill_reason"],
        "turn_count": turn_count,
        "last_user_prompt": last_user_prompt,
        "report_excerpt": _report_excerpt(run_root),
        "paths": {
            "root": rel_root,
            "report": f"{rel_root}/report.md",
            "metrics": f"{rel_root}/artifacts/metrics.json",
        },
    }
    return card


def empty_index() -> dict[str, Any]:
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "updated_at": _utc_now(),
        "runs": {},
    }


def load_index(
    *,
    cfg: dict[str, Any] | None = None,
    runs_dir: Path | None = None,
) -> dict[str, Any]:
    path = index_path(cfg=cfg, runs_dir=runs_dir)
    data = _read_json(path)
    if data is None:
        return empty_index()
    if "runs" not in data or not isinstance(data["runs"], dict):
        data["runs"] = {}
    data.setdefault("schema_version", INDEX_SCHEMA_VERSION)
    return data


def save_index(
    index: dict[str, Any],
    *,
    cfg: dict[str, Any] | None = None,
    runs_dir: Path | None = None,
    full_rebuild: bool = False,
) -> Path:
    cfg = cfg or load_config()
    index = dict(index)
    index["schema_version"] = INDEX_SCHEMA_VERSION
    index["updated_at"] = _utc_now()
    if not isinstance(index.get("runs"), dict):
        index["runs"] = {}

    path = index_path(cfg=cfg, runs_dir=runs_dir)
    _write_json(path, index)

    meta = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "updated_at": index["updated_at"],
        "run_count": len(index["runs"]),
        "last_full_rebuild": None,
    }
    meta_path = index_meta_path(cfg=cfg, runs_dir=runs_dir)
    existing_meta = _read_json(meta_path) or {}
    if full_rebuild:
        meta["last_full_rebuild"] = index["updated_at"]
    else:
        meta["last_full_rebuild"] = existing_meta.get("last_full_rebuild")
    _write_json(meta_path, meta)
    return path


def upsert_run(
    run_id: str,
    *,
    cfg: dict[str, Any] | None = None,
    runs_dir: Path | None = None,
) -> dict[str, Any]:
    """Extract card and write into index.json. Returns the card."""
    cfg = cfg or load_config()
    card = extract_run_card(run_id, cfg=cfg, runs_dir=runs_dir)
    index = load_index(cfg=cfg, runs_dir=runs_dir)
    index["runs"][card["run_id"]] = card
    save_index(index, cfg=cfg, runs_dir=runs_dir, full_rebuild=False)
    return card


def remove_run(
    run_id: str,
    *,
    cfg: dict[str, Any] | None = None,
    runs_dir: Path | None = None,
) -> bool:
    index = load_index(cfg=cfg, runs_dir=runs_dir)
    existed = run_id in index["runs"]
    if existed:
        del index["runs"][run_id]
        save_index(index, cfg=cfg, runs_dir=runs_dir, full_rebuild=False)
    return existed


def rebuild_index(
    *,
    cfg: dict[str, Any] | None = None,
    runs_dir: Path | None = None,
) -> dict[str, Any]:
    """Full scan of runs/ — repair / backfill."""
    cfg = cfg or load_config()
    index = empty_index()
    errors: list[dict[str, str]] = []
    for run_id in list_run_ids(cfg=cfg, runs_dir=runs_dir):
        try:
            card = extract_run_card(run_id, cfg=cfg, runs_dir=runs_dir)
            index["runs"][card["run_id"]] = card
        except Exception as exc:  # noqa: BLE001 — keep rebuild resilient
            errors.append({"run_id": run_id, "error": str(exc)})
            log.warning("lab index: skip %s: %s", run_id, exc)
    save_index(index, cfg=cfg, runs_dir=runs_dir, full_rebuild=True)
    if errors:
        index["_rebuild_errors"] = errors
    return index


def touch_run_index(run_id: str) -> None:
    """Best-effort upsert; never fail the parent script."""
    try:
        upsert_run(run_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("lab index update failed for %s: %s", run_id, exc)


def _metric_value(card: dict[str, Any], sample: str, key: str = "Sharpe") -> float | None:
    metrics = card.get("metrics") or {}
    block = metrics.get(sample)
    if not isinstance(block, dict):
        return None
    val = block.get(key)
    return float(val) if isinstance(val, (int, float)) else None


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def search_runs(
    *,
    symbol: str | None = None,
    asset_class: str | None = None,
    workflow: str | None = None,
    strategy_type: str | None = None,
    status: str | None = None,
    validation_passed: bool | None = None,
    verdict: str | None = None,
    tag: str | None = None,
    text: str | None = None,
    related_to: str | None = None,
    since: str | None = None,
    until: str | None = None,
    is_sharpe_gt: float | None = None,
    is_sharpe_lt: float | None = None,
    oos_sharpe_gt: float | None = None,
    oos_sharpe_lt: float | None = None,
    fingerprint_match: str | None = None,
    fingerprint_of: str | None = None,
    limit: int | None = None,
    cfg: dict[str, Any] | None = None,
    runs_dir: Path | None = None,
    index: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Filter indexed run cards. Case-insensitive for string fields."""
    cfg = cfg or load_config()
    index = index if index is not None else load_index(cfg=cfg, runs_dir=runs_dir)
    cards = list(index.get("runs", {}).values())

    fp_target: str | None = fingerprint_match
    if fingerprint_of:
        of_card = index.get("runs", {}).get(fingerprint_of)
        if of_card is None:
            # Try live extract if missing from index.
            try:
                of_card = extract_run_card(fingerprint_of, cfg=cfg, runs_dir=runs_dir)
            except FileNotFoundError:
                of_card = None
        if of_card:
            fp_target = of_card.get("params_fingerprint")

    since_dt = _parse_ts(since) if since else None
    until_dt = _parse_ts(until) if until else None
    text_l = text.lower() if text else None

    related_ids: set[str] | None = None
    if related_to:
        seed = index.get("runs", {}).get(related_to) or {}
        seed_related = {str(r) for r in (seed.get("related_runs") or [])}
        related_ids = {related_to} | seed_related
        for c in cards:
            if not isinstance(c, dict):
                continue
            if related_to in [str(r) for r in (c.get("related_runs") or [])]:
                related_ids.add(str(c.get("run_id")))

    def match(card: dict[str, Any]) -> bool:
        if symbol and str(card.get("symbol") or "").lower() != symbol.lower():
            return False
        if asset_class and str(card.get("asset_class") or "").lower() != asset_class.lower():
            return False
        if workflow and str(card.get("workflow") or "").lower() != workflow.lower():
            return False
        if strategy_type and str(card.get("strategy_type") or "").lower() != strategy_type.lower():
            return False
        if status and str(card.get("status") or "").lower() != status.lower():
            return False
        if validation_passed is not None and bool(card.get("validation_passed")) != validation_passed:
            return False
        if verdict and str(card.get("verdict") or "").lower() != verdict.lower():
            return False
        if tag:
            tags = [str(t).lower() for t in (card.get("tags") or [])]
            if tag.lower() not in tags:
                return False
        if related_ids is not None:
            rid = str(card.get("run_id") or "")
            own_related = [str(r) for r in (card.get("related_runs") or [])]
            if rid not in related_ids and related_to not in own_related:
                return False
        if fp_target and card.get("params_fingerprint") != fp_target:
            return False
        if fingerprint_of and card.get("run_id") == fingerprint_of:
            return False  # exclude self when matching fingerprint_of
        if since_dt:
            created = _parse_ts(card.get("created_at")) or _parse_ts(card.get("updated_at"))
            if created is None or created < since_dt:
                return False
        if until_dt:
            created = _parse_ts(card.get("created_at")) or _parse_ts(card.get("updated_at"))
            if created is None or created > until_dt:
                return False

        is_s = _metric_value(card, "in_sample")
        oos_s = _metric_value(card, "out_of_sample")
        if is_sharpe_gt is not None and (is_s is None or is_s <= is_sharpe_gt):
            return False
        if is_sharpe_lt is not None and (is_s is None or is_s >= is_sharpe_lt):
            return False
        if oos_sharpe_gt is not None and (oos_s is None or oos_s <= oos_sharpe_gt):
            return False
        if oos_sharpe_lt is not None and (oos_s is None or oos_s >= oos_sharpe_lt):
            return False

        if text_l:
            haystacks = [
                card.get("title"),
                card.get("hypothesis"),
                card.get("report_excerpt"),
                card.get("last_user_prompt"),
                card.get("kill_reason"),
                " ".join(str(t) for t in (card.get("tags") or [])),
                card.get("symbol"),
                card.get("workflow"),
            ]
            blob = " ".join(str(h) for h in haystacks if h).lower()
            if text_l not in blob:
                return False
        return True

    matched = [c for c in cards if isinstance(c, dict) and match(c)]
    matched.sort(key=lambda c: str(c.get("updated_at") or c.get("created_at") or ""), reverse=True)
    if limit is not None and limit >= 0:
        matched = matched[:limit]
    return matched


def find_fingerprint_matches(
    *,
    symbol: str | None = None,
    fingerprint: str | None = None,
    run_id: str | None = None,
    limit: int = 20,
    cfg: dict[str, Any] | None = None,
    runs_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Find runs sharing a params fingerprint (optionally scoped by symbol)."""
    kwargs: dict[str, Any] = {"limit": limit, "cfg": cfg, "runs_dir": runs_dir}
    if run_id:
        kwargs["fingerprint_of"] = run_id
    elif fingerprint:
        kwargs["fingerprint_match"] = fingerprint
    else:
        return []
    if symbol:
        kwargs["symbol"] = symbol
    return search_runs(**kwargs)


def lab_context_for_mcp(
    *,
    symbol: str | None = None,
    limit: int = 8,
    cfg: dict[str, Any] | None = None,
    runs_dir: Path | None = None,
) -> dict[str, Any]:
    """Compact prior-run blob for MCP guidance calls."""
    cfg = cfg or load_config()
    index = load_index(cfg=cfg, runs_dir=runs_dir)
    meta = _read_json(index_meta_path(cfg=cfg, runs_dir=runs_dir)) or {}
    prior = search_runs(symbol=symbol, limit=limit, cfg=cfg, runs_dir=runs_dir, index=index)

    warnings: list[dict[str, Any]] = []
    for card in prior:
        if card.get("verdict") in {"no_edge", "killed"}:
            warnings.append(
                {
                    "run_id": card.get("run_id"),
                    "verdict": card.get("verdict"),
                    "params_fingerprint": card.get("params_fingerprint"),
                    "kill_reason": card.get("kill_reason"),
                    "oos_sharpe": _metric_value(card, "out_of_sample"),
                }
            )

    # Slim cards for token budget.
    slim: list[dict[str, Any]] = []
    for card in prior:
        slim.append(
            {
                "run_id": card.get("run_id"),
                "title": card.get("title"),
                "status": card.get("status"),
                "symbol": card.get("symbol"),
                "workflow": card.get("workflow"),
                "strategy_type": card.get("strategy_type"),
                "verdict": card.get("verdict"),
                "tags": card.get("tags"),
                "validation_passed": card.get("validation_passed"),
                "metrics": card.get("metrics"),
                "params_fingerprint": card.get("params_fingerprint"),
                "hypothesis": card.get("hypothesis"),
                "report_excerpt": (card.get("report_excerpt") or "")[:240] or None,
            }
        )

    return {
        "prior_runs": slim,
        "duplicate_warnings": warnings,
        "index_updated_at": index.get("updated_at") or meta.get("updated_at"),
        "run_count": len(index.get("runs") or {}),
    }


def format_cards_table(cards: Iterable[dict[str, Any]]) -> str:
    rows = list(cards)
    if not rows:
        return "(no matching runs)"
    lines = [
        f"{'run_id':<28} {'symbol':<12} {'status':<18} {'oos_sh':>7} {'verdict':<16} title",
        "-" * 100,
    ]
    for c in rows:
        oos = _metric_value(c, "out_of_sample")
        oos_s = f"{oos:.2f}" if oos is not None else "-"
        lines.append(
            f"{str(c.get('run_id') or ''):<28} "
            f"{str(c.get('symbol') or '-'):<12} "
            f"{str(c.get('status') or '-'):<18} "
            f"{oos_s:>7} "
            f"{str(c.get('verdict') or '-'):<16} "
            f"{str(c.get('title') or '')}"
        )
    return "\n".join(lines)
