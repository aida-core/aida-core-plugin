#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Knowledge sync entry point (#22).

Reads `agents/<agent>/knowledge/sources.yml`, walks each declared
source, fetches its content, and applies updates to the targeted
section of the target knowledge file.

Two modes:
  - `sync`: apply updates to disk
  - `status` / `--dry-run`: report what *would* change, write nothing

Output is JSON (machine-friendly for CI) on stdout; exit 0 on
success (no changes needed or all applied cleanly), 1 on partial
failure (some sources had problems).

Usage:
    python sync.py --agent claude-code-expert
    python sync.py --agent claude-code-expert --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).parent
SHARED = SCRIPT_DIR.parent.parent.parent / "scripts"
sys.path.insert(0, str(SHARED))

from shared.knowledge_sync import (  # noqa: E402
    KnowledgeSyncError,
    diff_summary,
    read_local_source,
    update_section,
)

import yaml  # noqa: E402


def _agent_root(project_root: Path, agent: str) -> Path:
    return project_root / "agents" / agent


def _load_sources(
    project_root: Path, agent: str
) -> List[Dict[str, Any]]:
    """Load and validate sources.yml. Returns [] if missing."""
    sources_path = (
        _agent_root(project_root, agent) / "knowledge" / "sources.yml"
    )
    if not sources_path.is_file():
        return []
    try:
        data = yaml.safe_load(sources_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise KnowledgeSyncError(
            f"sources.yml is not valid YAML: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise KnowledgeSyncError(
            "sources.yml must be a mapping with a top-level "
            "`sources:` key."
        )
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        raise KnowledgeSyncError(
            "`sources:` must be a list in sources.yml"
        )
    return sources


def _resolve_target(
    project_root: Path, agent: str, source: Dict[str, Any]
) -> Optional[Path]:
    """Return the absolute path to the target knowledge file."""
    target = source.get("target", {})
    if not isinstance(target, dict):
        return None
    rel = target.get("file")
    if not isinstance(rel, str):
        return None
    return _agent_root(project_root, agent) / rel


def _fetch_source_body(
    project_root: Path, source: Dict[str, Any]
) -> Optional[str]:
    """Fetch the upstream content for ``source``.

    Currently only handles ``type: local``. Returns None for other
    types or read failures — callers report ``source-missing`` for
    those.

    Normalizes the body by stripping the single trailing newline
    that POSIX file convention adds. Without this, every sync
    would report ``changed`` because the marker-block body has its
    trailing newline stripped by the parser (so the body never
    matches a file ending in \\n).
    """
    if source.get("type") != "local":
        return None
    path = source.get("path")
    if not isinstance(path, str):
        return None
    full = project_root / path
    text = read_local_source(str(full))
    if text is None:
        return None
    # Strip a single trailing newline so source-with-final-LF
    # compares equal to the LF-stripped marker body.
    return text[:-1] if text.endswith("\n") else text


def run(
    project_root: Path,
    agent: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Walk sources for ``agent`` and sync (or report) each.

    Returns a structured report; never raises for per-source
    failures — those go in the per-source `status` field.
    """
    try:
        sources = _load_sources(project_root, agent)
    except KnowledgeSyncError as exc:
        return {
            "success": False,
            "agent": agent,
            "message": str(exc),
            "results": [],
        }

    if not sources:
        return {
            "success": True,
            "agent": agent,
            "message": (
                f"No sources declared for agent {agent!r} "
                "(sources.yml missing or empty)."
            ),
            "results": [],
        }

    results: List[Dict[str, Any]] = []
    overall_ok = True

    for source in sources:
        name = source.get("name") or source.get("type") or "<unnamed>"
        result: Dict[str, Any] = {
            "name": name,
            "status": "unknown",
            "target": None,
        }

        target = _resolve_target(project_root, agent, source)
        if target is None:
            result["status"] = "invalid-target"
            result["message"] = (
                "Source has no valid `target.file` field."
            )
            overall_ok = False
            results.append(result)
            continue
        result["target"] = str(target)

        section_name = (source.get("target") or {}).get("section")
        if not isinstance(section_name, str) or not section_name:
            result["status"] = "invalid-target"
            result["message"] = (
                "Source target must declare a `section` name."
            )
            overall_ok = False
            results.append(result)
            continue

        body = _fetch_source_body(project_root, source)
        if body is None:
            result["status"] = "source-missing"
            result["message"] = (
                f"Couldn't read upstream source for {name!r}. "
                f"Source type: {source.get('type', '?')}, "
                f"path: {source.get('path', '?')}"
            )
            overall_ok = False
            results.append(result)
            continue

        if not target.is_file():
            result["status"] = "target-missing"
            result["message"] = (
                f"Target knowledge file does not exist: {target}"
            )
            overall_ok = False
            results.append(result)
            continue

        try:
            content = target.read_text(encoding="utf-8")
            summary = diff_summary(content, {section_name: body})
            section_status = summary[0]["status"]
        except KnowledgeSyncError as exc:
            result["status"] = "marker-error"
            result["message"] = str(exc)
            overall_ok = False
            results.append(result)
            continue

        if section_status == "missing":
            result["status"] = "missing-section"
            result["message"] = (
                f"Knowledge file {target.name} has no upstream "
                f"section named {section_name!r}. Add "
                f'`<!-- upstream:start name="{section_name}" -->`'
                " markers to opt that section into sync."
            )
            overall_ok = False
            results.append(result)
            continue

        if section_status == "unchanged":
            result["status"] = "unchanged"
            results.append(result)
            continue

        # status == "changed"
        if dry_run:
            result["status"] = "would-change"
            result["bytes_changed"] = (
                summary[0]["new_length"]
                - summary[0]["old_length"]
            )
            results.append(result)
            continue

        try:
            new_content, _ = update_section(
                content, section_name, body
            )
            target.write_text(new_content, encoding="utf-8")
        except (KnowledgeSyncError, OSError) as exc:
            result["status"] = "write-error"
            result["message"] = str(exc)
            overall_ok = False
            results.append(result)
            continue

        result["status"] = "changed"
        results.append(result)

    return {
        "success": overall_ok,
        "agent": agent,
        "dry_run": dry_run,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="sync.py",
        description=(
            "Sync an agent's knowledge files with declared "
            "upstream sources."
        ),
    )
    parser.add_argument(
        "--agent",
        required=True,
        help="Agent name (e.g., 'claude-code-expert')",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Don't write anything; report what would change."
        ),
    )
    args = parser.parse_args()

    report = run(
        project_root=args.project_root.resolve(),
        agent=args.agent,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
