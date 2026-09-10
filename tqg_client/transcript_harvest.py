"""Harvest Cursor agent transcripts into lesson candidates + a chat→run map."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .lab_index import load_index
from .lessons import claim_is_oos_contaminated, new_lesson

_NOISE_RE = re.compile(
    r"tool_use|function_call|\[REDACTED\]|Explore /root/thequantgpt-wrapper thoroughly|"
    r"<user_query>|agentic framework|switch to plan mode",
    re.I,
)
_CONCLUSION_RE = re.compile(
    r"\b(no_edge|no edge|killed|kill_reason|does not survive|survivors:\s*0|"
    r"negative result|missing data|do not (?:re-?run|repeat)|overfit|oos collapse|"
    r"validation_passed|family n)\b",
    re.I,
)
_SYMBOL_RE = re.compile(
    r"\b(QQQ|SPY|BTCUSDT|BTC|ETHUSDT|XLE|GLD|TLT|SSO|FXI)\b"
)


def default_transcript_root() -> Path:
    env = os.environ.get("TQG_TRANSCRIPT_ROOT", "").strip()
    if env:
        return Path(env)
    candidates = [
        Path("/root/.cursor/projects/root/agent-transcripts"),
        Path.home() / ".cursor/projects/root/agent-transcripts",
    ]
    for path in candidates:
        if path.is_dir():
            return path
    return candidates[0]


def _iter_text(obj: Any) -> list[str]:
    chunks: list[str] = []
    if isinstance(obj, str):
        chunks.append(obj)
    elif isinstance(obj, dict):
        if obj.get("type") == "text" and isinstance(obj.get("text"), str):
            chunks.append(obj["text"])
        else:
            for val in obj.values():
                chunks.extend(_iter_text(val))
    elif isinstance(obj, list):
        for item in obj:
            chunks.extend(_iter_text(item))
    return chunks


def _parent_jsonl_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.is_dir():
        return files
    for child in sorted(root.iterdir()):
        if child.is_dir():
            parent = child / f"{child.name}.jsonl"
            if parent.is_file():
                files.append(parent)
                continue
            # Fallback: any jsonl not under subagents/
            for jsonl in child.glob("*.jsonl"):
                if "subagents" not in jsonl.parts:
                    files.append(jsonl)
        elif child.suffix == ".jsonl":
            files.append(child)
    return files


def _subagent_jsonl_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(root.glob("*/subagents/*.jsonl"))


def _run_id_patterns(run_ids: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    patterns: list[tuple[str, re.Pattern[str]]] = []
    for rid in sorted(run_ids, key=len, reverse=True):
        if not rid:
            continue
        if re.fullmatch(r"\d+", rid):
            pat = re.compile(rf"(?:runs/{re.escape(rid)}(?!\d)|run(?:_id)?\s*[:=]?\s*{re.escape(rid)}\b)")
        else:
            pat = re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(rid)}(?![A-Za-z0-9_-])")
        patterns.append((rid, pat))
    return patterns


def _usable_snippet(text: str) -> bool:
    snippet = re.sub(r"\s+", " ", text).strip()
    if len(snippet) < 40 or len(snippet) > 480:
        return False
    if _NOISE_RE.search(snippet):
        return False
    if snippet.count("def ") >= 2 or "#!/usr/bin/env" in snippet:
        return False
    return True


def _conclusion_snippets(texts: list[tuple[str, str]], *, limit: int = 3) -> list[str]:
    out: list[str] = []
    for role, text in texts:
        if role != "assistant":
            continue
        if not _CONCLUSION_RE.search(text) or _NOISE_RE.search(text):
            continue
        for part in re.split(r"(?<=[.!?])\s+", text):
            part = re.sub(r"\s+", " ", part).strip()
            if not _CONCLUSION_RE.search(part):
                continue
            if not _usable_snippet(part):
                continue
            if part not in out:
                out.append(part[:400])
            if len(out) >= limit:
                return out
    return out


def _first_user_query(texts: list[tuple[str, str]], limit: int = 160) -> str:
    for role, text in texts:
        if role == "user":
            cleaned = re.sub(r"<[^>]+>", " ", text)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if cleaned:
                return cleaned[:limit]
    return ""


def parse_transcript(path: Path, *, max_chars: int = 400_000) -> dict[str, Any]:
    chat_id = path.stem
    texts: list[tuple[str, str]] = []
    n_lines = 0
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"chat_id": chat_id, "path": str(path), "texts": [], "n_messages": 0}
    if len(raw) > max_chars:
        raw = raw[:max_chars]
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        n_lines += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or row.get("type") or "")
        blob = " ".join(_iter_text(row.get("message") or row.get("content") or row))
        blob = blob.strip()
        if blob:
            texts.append((role, blob))
    return {
        "chat_id": chat_id,
        "path": str(path),
        "texts": texts,
        "n_messages": len(texts),
        "n_lines": n_lines,
        "title_guess": _first_user_query(texts),
    }


def harvest_transcripts(
    *,
    transcript_root: Path | None = None,
    include_subagents: bool = True,
    existing_run_ids: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = transcript_root or default_transcript_root()
    index = load_index()
    run_ids = existing_run_ids or [str(k) for k in (index.get("runs") or {}).keys()]
    patterns = _run_id_patterns(run_ids)
    files = _parent_jsonl_files(root)
    if include_subagents:
        files.extend(_subagent_jsonl_files(root))

    transcript_map: dict[str, Any] = {
        "transcript_root": str(root),
        "chats": {},
    }
    lessons: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for path in files:
        parsed = parse_transcript(path)
        blob = "\n".join(t for _, t in parsed["texts"])
        linked: list[str] = []
        for rid, pat in patterns:
            if pat.search(blob):
                linked.append(rid)
        symbols = sorted(set(_SYMBOL_RE.findall(blob)))
        chat_id = parsed["chat_id"]
        transcript_map["chats"][chat_id] = {
            "path": parsed["path"],
            "title_guess": parsed["title_guess"],
            "run_ids": linked,
            "symbols": symbols,
            "n_messages": parsed["n_messages"],
        }
        if re.search(
            r"\bagentic framework\b|\blesson corpus\b|tqg_research_loop\.py",
            blob,
            re.I,
        ):
            continue

        if _NOISE_RE.search(parsed.get("title_guess") or ""):
            continue
        conclusions = _conclusion_snippets(parsed["texts"], limit=3)

        if not conclusions:
            continue

        targets = linked[:4] or [None]
        for rid in targets:
            claim = conclusions[0]
            symbol = None
            card = (index.get("runs") or {}).get(rid) if rid else None
            if isinstance(card, dict):
                symbol = card.get("symbol")
            if not symbol and symbols:
                symbol = symbols[0]
            oos_flag = claim_is_oos_contaminated(claim) or any(
                claim_is_oos_contaminated(c) for c in conclusions
            )
            # Transcript claims that cite OOS may only block, never steer.
            hint = "do_not_repeat" if rid else "tag_unsettled"
            if oos_flag and not rid:
                hint = "halt_for_human"
            try:
                lesson = new_lesson(
                    kind="process" if not rid else "hypothesis",
                    failure_mode="unsettled" if not rid else "no_edge_oos",
                    claim=claim[:400],
                    action_hint=hint,
                    source="transcript",
                    symbol=symbol if isinstance(symbol, str) else None,
                    related_runs=[rid] if rid else [],
                    transcript_ids=[chat_id],
                    evidence=" | ".join(conclusions[:3]),
                    oos_contaminated=oos_flag,
                    confidence=0.45 if not rid else 0.55,
                )
            except ValueError:
                continue
            key = lesson["lesson_id"]
            if key in seen_keys:
                continue
            seen_keys.add(key)
            lessons.append(lesson)

    transcript_map["chat_count"] = len(transcript_map["chats"])
    transcript_map["linked_chats"] = sum(
        1 for c in transcript_map["chats"].values() if c.get("run_ids")
    )
    return lessons, transcript_map
