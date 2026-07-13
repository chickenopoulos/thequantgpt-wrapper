#!/usr/bin/env python3
"""Package a completed run into reports/ for sharing."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_files(run_root: Path) -> list[Path]:
    patterns = (
        "run.json",
        "flow.json",
        "strategy_spec.json",
        "RUN.md",
        "report.md",
        "code/*.py",
        "artifacts/*",
        "charts/*",
        "logs/*",
    )
    files: list[Path] = []
    for pattern in patterns:
        files.extend(run_root.glob(pattern))
    return sorted({p for p in files if p.is_file()})


def _refresh_run_md(run_root: Path) -> None:
    meta = _load_json(run_root / "run.json")
    flow = _load_json(run_root / "flow.json")
    spec = _load_json(run_root / "strategy_spec.json")
    artifacts = sorted((run_root / "artifacts").glob("*"))
    charts = sorted((run_root / "charts").glob("*"))
    code_files = sorted((run_root / "code").glob("*.py"))

    lines = [
        f"# {meta.get('title', 'Strategy run')}",
        "",
        f"**Run ID:** {meta.get('run_id', run_root.name)}",
        f"**Created:** {meta.get('created_at', '')}",
        f"**Root:** `{meta.get('root', run_root.name)}`",
        "",
    ]
    if spec:
        lines.extend(["## Strategy definition", "", "```json", json.dumps(spec, indent=2), "```", ""])
    turns = flow.get("turns") or []
    if turns:
        lines.append("## Turn log")
        lines.append("")
        for turn in turns:
            lines.append(f"### Turn {turn.get('turn_index', '?') + 1}")
            lines.append("")
            if turn.get("user_message"):
                lines.append(f"**User:** {turn['user_message']}")
                lines.append("")
            if turn.get("assistant_summary"):
                lines.append(f"**Agent:** {turn['assistant_summary']}")
                lines.append("")
    if artifacts:
        lines.extend(["## Artifacts", ""])
        for p in artifacts:
            lines.append(f"- `{p.relative_to(run_root)}`")
        lines.append("")
    if charts:
        lines.extend(["## Charts", ""])
        for p in charts:
            lines.append(f"- `{p.relative_to(run_root)}`")
        lines.append("")
    if code_files:
        lines.extend(["## Code", ""])
        for p in code_files:
            lines.append(f"- `{p.relative_to(run_root)}`")
        lines.append("")

    (run_root / "RUN.md").write_text("\n".join(lines), encoding="utf-8")


def package_run(run_id: str, *, zip_bundle: bool = False) -> Path:
    run_root = _REPO / "runs" / run_id
    if not run_root.is_dir():
        raise FileNotFoundError(f"Run not found: {run_root}")

    _refresh_run_md(run_root)
    files = _collect_files(run_root)
    if not any(p.suffix == ".py" for p in files):
        raise ValueError("No strategy code under runs/<id>/code/")
    if not (run_root / "artifacts").glob("*"):
        raise ValueError("No artifacts under runs/<id>/artifacts/")

    dest = _REPO / "reports" / run_id
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    for src in files:
        rel = src.relative_to(run_root)
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)

    manifest = {
        "run_id": run_id,
        "packaged_at": datetime.now(timezone.utc).isoformat(),
        "files": [str(f.relative_to(dest)) for f in sorted(dest.rglob("*")) if f.is_file()],
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if zip_bundle:
        archive = shutil.make_archive(str(dest), "zip", root_dir=dest)
        return Path(archive)
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description="Package runs/<id>/ into reports/<id>/")
    parser.add_argument("run_id", help="Run folder name (numeric or slug)")
    parser.add_argument("--zip", action="store_true", help="Also create reports/<id>.zip")
    args = parser.parse_args()
    try:
        out = package_run(args.run_id, zip_bundle=args.zip)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
