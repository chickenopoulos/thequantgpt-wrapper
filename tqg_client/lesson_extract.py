"""Build lesson candidates from the lab index, reports, and catalog CSV."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from .config import repo_root
from .lab_index import _metric_value, load_index, rebuild_index, runs_base
from .lessons import (
    PROMISING_REVIEWED,
    claim_is_oos_contaminated,
    new_lesson,
)
from .run_state import load_run_state, save_run_state

log = logging.getLogger(__name__)

KNOWN_FAMILIES: list[tuple[str, tuple[str, ...]]] = [
    (
        "qqq_mr",
        (
            "1",
            "qqq_rsi2_mr",
            "qqq_rsi14_weekly_confirm",
            "qqq_qs_rsi",
            "qqq_pullback_reversal",
        ),
    ),
    (
        "spy_orb",
        ("spy_orb_enhanced", "spy_orb_enhanced_v2"),
    ),
    (
        "formulaic_alpha",
        (
            "alpha_mine_smoke",
            "binance_usdtm_leftover_volume",
            "formulaic_alpha_mine",
            "crypto_formulaic_oos20251001",
        ),
    ),
    (
        "residual_program",
        (
            "residual_identity_scan",
            "cs_resid_mom_btc",
            "cs_funding_carry",
            "indicator_catalog_scan",
            "iqr_bands_cross_asset",
            "iqr_er_combo",
            "iqr_upper_follow",
            "kaufman_er_cross_asset",
            "crypto_vol_gate_bh",
            "formulaic_alpha_mine",
        ),
    ),
]


def _blob(card: dict[str, Any], extra: str = "") -> str:
    parts = [
        card.get("kill_reason"),
        card.get("hypothesis"),
        card.get("report_excerpt"),
        card.get("last_error"),
        card.get("title"),
        " ".join(str(t) for t in (card.get("tags") or [])),
        extra,
    ]
    return " ".join(str(p) for p in parts if p).lower()


def infer_failure_mode(card: dict[str, Any], *, catalog_status: str | None = None) -> str:
    status = (catalog_status or "").upper()
    if status == "SKIP":
        return "missing_data"
    if status == "NO_TRADES":
        return "no_trades"
    if status == "RUNNER_ONLY":
        return "runner_only_not_oos"
    blob = _blob(card)
    err = str(card.get("last_error") or "").lower()
    if "missing" in blob and any(w in blob for w in ("data", "column", "onchain", "option")):
        return "missing_data"
    if err and any(w in err for w in ("attribute", "shift", "keyerror", "traceback", "modulenotfound")):
        return "runner_error"
    if "no_trades" in blob or "no trades" in blob or "never fires" in blob:
        return "no_trades"
    if "sparse" in blob:
        return "sparse_signals"
    if any(w in blob for w in ("fee", "slip", "cost", "turnover", "rt cost")):
        return "cost_sensitivity"
    if any(w in blob for w in ("bonferroni", "multiple testing", "n=37", "family n")):
        return "multiple_testing"
    if "reconstruct" in blob or "reconstruction" in blob:
        return "reconstruction_miss"
    is_s = _metric_value(card, "in_sample")
    oos = _metric_value(card, "out_of_sample")
    if is_s is not None and oos is not None and is_s >= 0.4 and (oos <= 0 or (is_s - oos) > 1.0):
        return "is_oos_collapse"
    if card.get("verdict") in {"no_edge", "killed"}:
        return "no_edge_oos" if oos is not None else "unsettled"
    if card.get("status") == "failed":
        return "runner_error" if err else "missing_data"
    return "unsettled"


def _evidence_from_card(card: dict[str, Any]) -> str:
    bits: list[str] = []
    if card.get("kill_reason"):
        bits.append(str(card["kill_reason"]))
    is_s = _metric_value(card, "in_sample")
    oos = _metric_value(card, "out_of_sample")
    if is_s is not None or oos is not None:
        bits.append(
            f"IS Sharpe={is_s if is_s is not None else 'n/a'} "
            f"OOS Sharpe={oos if oos is not None else 'n/a'}"
        )
    if card.get("last_error"):
        bits.append(f"last_error={card['last_error']}")
    if card.get("report_excerpt"):
        bits.append(str(card["report_excerpt"])[:240])
    return " | ".join(bits)[:800]


def lessons_from_run_card(
    card: dict[str, Any],
    *,
    catalog_status: str | None = None,
    catalog_note: str | None = None,
) -> list[dict[str, Any]]:
    rid = str(card.get("run_id") or "")
    if not rid:
        return []
    symbol = card.get("symbol")
    if isinstance(symbol, str) and symbol.startswith("catalog_"):
        symbol = card.get("symbol")
    mode = infer_failure_mode(card, catalog_status=catalog_status)
    evidence = _evidence_from_card(card)
    if catalog_note:
        evidence = (evidence + " | catalog: " + catalog_note)[:800]
    verdict = card.get("verdict")
    status = card.get("status")
    tags = [str(t).lower() for t in (card.get("tags") or [])]
    out: list[dict[str, Any]] = []

    def _add(**kwargs: Any) -> None:
        kwargs.setdefault("symbol", symbol if isinstance(symbol, str) else None)
        kwargs.setdefault("asset_class", card.get("asset_class"))
        kwargs.setdefault("workflow", card.get("workflow"))
        kwargs.setdefault("strategy_type", card.get("strategy_type"))
        kwargs.setdefault("related_runs", [rid] + list(card.get("related_runs") or []))
        kwargs.setdefault("params_fingerprint", card.get("params_fingerprint"))
        kwargs.setdefault("evidence", evidence)
        out.append(new_lesson(**kwargs))

    title = str(card.get("title") or rid)

    if catalog_status == "SKIP":
        _add(
            kind="data",
            failure_mode="missing_data",
            claim=f"{rid} ({title}) skipped — required data/columns were not local.",
            action_hint="acquire_data",
            source="catalog",
            oos_contaminated=False,
            confidence=0.9,
        )
        return out
    if catalog_status == "NO_TRADES":
        _add(
            kind="hypothesis",
            failure_mode="no_trades",
            claim=f"{rid} ({title}) produced no OOS trades on this sample.",
            action_hint="do_not_repeat",
            source="catalog",
            oos_contaminated=True,
            confidence=0.85,
        )
        return out
    if catalog_status == "RUNNER_ONLY":
        _add(
            kind="process",
            failure_mode="runner_only_not_oos",
            claim=(
                f"{rid} ({title}) is RUNNER_ONLY — full-sample Sharpe is not a true OOS split. "
                "Do not treat it as validated edge."
            ),
            action_hint="do_not_repeat",
            source="catalog",
            oos_contaminated=True,
            confidence=0.95,
        )
        return out

    if verdict in {"no_edge", "killed"} or "negative_result" in tags:
        oos_flag = claim_is_oos_contaminated(str(card.get("kill_reason") or "") + " " + evidence)
        kill = str(card.get("kill_reason") or "").strip()
        claim = kill if kill else f"{rid} ({title}) settled as {verdict or 'no_edge'} — do not silently re-baseline."
        _add(
            kind="hypothesis" if mode != "runner_error" else "code",
            failure_mode=mode if mode != "unsettled" else "no_edge_oos",
            claim=claim[:400],
            action_hint="do_not_repeat",
            source="run",
            oos_contaminated=oos_flag or mode in {"no_edge_oos", "is_oos_collapse"},
            confidence=0.92,
        )

    if status == "failed" or card.get("last_error"):
        err = str(card.get("last_error") or "")
        data_mode = mode == "missing_data" or "missing" in err.lower()
        _add(
            kind="data" if data_mode else "code",
            failure_mode="missing_data" if data_mode else "runner_error",
            claim=f"{rid} failed: {(err or 'runner/status=failed')[:240]}",
            action_hint="acquire_data" if data_mode else "do_not_repeat",
            source="run",
            oos_contaminated=False,
            confidence=0.8,
        )

    if rid in PROMISING_REVIEWED:
        _add(
            kind="hypothesis",
            failure_mode="unsettled",
            claim=(
                f"{rid} ({title}) is human-reviewed promising on this exact sample. "
                "Halt for packaging review — do not search neighbor rules from its OOS Sharpe."
            ),
            action_hint="halt_for_human",
            source="run",
            oos_contaminated=True,
            confidence=0.8,
        )

    is_s = _metric_value(card, "in_sample")
    oos = _metric_value(card, "out_of_sample")
    if (
        is_s is not None
        and oos is not None
        and is_s >= 0.5
        and (oos <= 0 or (is_s - oos) > 1.0)
        and verdict not in {"no_edge", "killed"}
        and rid not in PROMISING_REVIEWED
        and catalog_status != "OK"
    ):
        _add(
            kind="anti_pattern",
            failure_mode="is_oos_collapse",
            claim=(
                f"{rid} ({title}) shows IS→OOS Sharpe collapse "
                f"({is_s:.2f} → {oos:.2f}); do not retune on OOS."
            ),
            action_hint="do_not_repeat",
            source="run",
            oos_contaminated=True,
            confidence=0.75,
        )

    n_stable = 0
    try:
        n_stable = int(float(card.get("psa_stable_cells") or 0))
    except (TypeError, ValueError):
        n_stable = 0
    if catalog_status == "OK" and n_stable >= 3:
        _add(
            kind="process",
            failure_mode="unsettled",
            claim=(
                f"{rid} ({title}) recorded a PSA-stable IS plateau "
                f"({n_stable} cells). That is process evidence, not an OOS clone license."
            ),
            action_hint="needs_robustness",
            source="catalog",
            oos_contaminated=False,
            confidence=0.6,
        )

    if catalog_status == "OK" and oos is not None and oos <= 0:
        _add(
            kind="hypothesis",
            failure_mode="no_edge_oos",
            claim=(
                f"{rid} ({title}) catalog OK split has non-positive OOS Sharpe "
                f"({oos:.2f}). Settled on this sample — do not silently re-run."
            ),
            action_hint="do_not_repeat",
            source="catalog",
            oos_contaminated=True,
            confidence=0.7,
        )

    return out


def load_catalog_rows(path: Path | None = None) -> list[dict[str, str]]:
    csv_path = path or (repo_root() / "reports" / "catalog_robust_results.csv")
    if not csv_path.is_file():
        return []
    with csv_path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def extract_all_lessons(
    *,
    include_catalog: bool = True,
    extra_lessons: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    index = load_index()
    cards = list((index.get("runs") or {}).values())
    catalog_by_run: dict[str, dict[str, str]] = {}
    if include_catalog:
        for row in load_catalog_rows():
            rid = (row.get("run_id") or "").strip()
            if rid:
                catalog_by_run[rid] = row

    # Attach last_error from run.json when the index card lacks it.
    base = runs_base()
    for card in cards:
        if not isinstance(card, dict):
            continue
        if card.get("last_error"):
            continue
        rid = str(card.get("run_id") or "")
        run_json = base / rid / "run.json"
        if not run_json.is_file():
            continue
        try:
            raw = json.loads(run_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(raw, dict) and raw.get("last_error"):
            card["last_error"] = str(raw["last_error"])[:300]

    lessons: list[dict[str, Any]] = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        rid = str(card.get("run_id") or "")
        cat = catalog_by_run.get(rid)
        cat_status = (cat.get("status") if cat else None) or None
        cat_note = (cat.get("note") if cat else None) or None
        if cat:
            card = dict(card)
            card["psa_status"] = cat.get("psa_status")
            card["psa_stable_cells"] = cat.get("psa_stable_cells")
        try:
            lessons.extend(
                lessons_from_run_card(card, catalog_status=cat_status, catalog_note=cat_note)
            )
        except ValueError as exc:
            log.warning("skip card %s: %s", rid, exc)
    if extra_lessons:
        lessons.extend(extra_lessons)
    return lessons


def apply_catalog_tags(*, write: bool = True) -> dict[str, Any]:
    """Tag catalog runs from CSV. Does not auto-set promising from OOS Sharpe."""
    rows = load_catalog_rows()
    updated = 0
    skipped = 0
    for row in rows:
        rid = (row.get("run_id") or "").strip()
        if not rid:
            continue
        try:
            state = load_run_state(rid)
        except FileNotFoundError:
            skipped += 1
            continue
        status = (row.get("status") or "").upper()
        tags = list(state.tags or [])
        for tag in ("catalog", f"catalog_status_{status.lower()}" if status else ""):
            if tag and tag not in tags:
                tags.append(tag)
        psa = (row.get("psa_status") or "").upper()
        if psa == "STABLE" or (row.get("psa_stable_cells") or "0") not in {"", "0", "0.0"}:
            try:
                n_stable = int(float(row.get("psa_stable_cells") or 0))
            except ValueError:
                n_stable = 0
            if n_stable >= 3 and "psa_stable_plateau" not in tags:
                tags.append("psa_stable_plateau")
        note = (row.get("note") or "").strip()
        if write:
            if not state.verdict:
                if status == "SKIP":
                    state.verdict = "killed"
                    state.kill_reason = note or "catalog SKIP — missing data or runner error"
                    if "missing_data" not in tags:
                        tags.append("missing_data")
                elif status == "NO_TRADES":
                    state.verdict = "no_edge"
                    state.kill_reason = note or "catalog NO_TRADES"
                    if "no_trades" not in tags:
                        tags.append("no_trades")
            if status == "RUNNER_ONLY" and "runner_only_not_oos" not in tags:
                tags.append("runner_only_not_oos")
            state.tags = tags
            save_run_state(state)
        updated += 1
    if write and updated:
        rebuild_index()
    return {"updated": updated, "skipped_missing": skipped}


def link_known_families(*, write: bool = True) -> dict[str, Any]:
    linked = 0
    missing: list[str] = []
    for _name, members in KNOWN_FAMILIES:
        existing: list[str] = []
        states = []
        for rid in members:
            try:
                states.append(load_run_state(rid))
                existing.append(rid)
            except FileNotFoundError:
                missing.append(rid)
        if len(existing) < 2:
            continue
        if write:
            for state in states:
                related = list(state.related_runs or [])
                for other in existing:
                    if other != state.run_id and other not in related:
                        related.append(other)
                state.related_runs = related
                save_run_state(state)
                linked += 1
    if write and linked:
        rebuild_index()
    return {"runs_updated": linked, "missing_members": missing}
