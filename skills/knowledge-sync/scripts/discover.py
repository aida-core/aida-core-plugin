#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Knowledge discovery entry point (#144).

Walks each ``roots:`` entry declared in
``agents/<agent>/knowledge/sources.yml`` and writes any newly-found
URLs into ``decisions.json`` as ``status: pending`` entries — ready
for the curator skill to verdict.

Existing entries (any status) are left untouched: discovery only adds
new URLs to the log; it never re-decides for the curator.

Output is JSON on stdout; exit 0 on a clean run (no errors at the
top level), 1 on parse / config failures.

Usage:
    python discover.py --agent claude-code-expert
    python discover.py --agent claude-code-expert --concurrency 2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).parent
SHARED = SCRIPT_DIR.parent.parent.parent / "scripts"
sys.path.insert(0, str(SHARED))

from shared.decisions_log import (  # noqa: E402
    Decision,
    find_by_url,
    now_iso,
    read_decisions,
    upsert_decision,
    write_decisions,
)
from shared.spider import (  # noqa: E402
    DEFAULT_CONCURRENCY,
    SpiderResult,
    discover,
    parse_roots,
)

import yaml  # noqa: E402


def _knowledge_dir(project_root: Path, agent: str) -> Path:
    return project_root / "agents" / agent / "knowledge"


def _load_roots(
    project_root: Path, agent: str
) -> List[Any]:
    """Read the ``roots:`` block from sources.yml; returns [] when
    absent. Raises ValueError on structural problems."""
    sources_path = _knowledge_dir(project_root, agent) / "sources.yml"
    if not sources_path.is_file():
        return []
    data = yaml.safe_load(sources_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(
            f"sources.yml at {sources_path} must be a mapping."
        )
    return parse_roots(data.get("roots"))


def run(
    project_root: Path,
    agent: str,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> Dict[str, Any]:
    """Walk roots for ``agent`` and persist new pending decisions.

    Returns a structured report; never raises for per-root walk
    failures — those go into the report's ``errors`` list.
    """
    try:
        roots = _load_roots(project_root, agent)
    except (ValueError, yaml.YAMLError) as exc:
        return {
            "success": False,
            "agent": agent,
            "message": str(exc),
            "discovered": 0,
            "skipped_existing": 0,
            "errors": [],
        }

    if not roots:
        return {
            "success": True,
            "agent": agent,
            "message": (
                f"No `roots:` declared for agent {agent!r}; nothing "
                "to discover."
            ),
            "discovered": 0,
            "skipped_existing": 0,
            "errors": [],
        }

    knowledge_dir = _knowledge_dir(project_root, agent)
    try:
        existing = read_decisions(knowledge_dir)
    except ValueError as exc:
        return {
            "success": False,
            "agent": agent,
            "message": (
                f"Could not read existing decisions.json: {exc}"
            ),
            "discovered": 0,
            "skipped_existing": 0,
            "errors": [],
        }

    result: SpiderResult = discover(roots, concurrency=concurrency)

    discovered_new = 0
    skipped_existing = 0
    timestamp = now_iso()
    next_decisions = existing
    for url, source_root in result.discovered:
        if find_by_url(next_decisions, url) is not None:
            skipped_existing += 1
            continue
        decision = Decision(
            url=url,
            status="pending",
            discovered_at=timestamp,
            source_root=source_root,
        )
        next_decisions = upsert_decision(next_decisions, decision)
        discovered_new += 1

    if discovered_new > 0:
        try:
            write_decisions(knowledge_dir, next_decisions)
        except OSError as exc:
            return {
                "success": False,
                "agent": agent,
                "message": (
                    f"Could not write decisions log: {exc}"
                ),
                "discovered": 0,
                "skipped_existing": skipped_existing,
                "errors": result.errors,
            }

    return {
        "success": True,
        "agent": agent,
        "discovered": discovered_new,
        "skipped_existing": skipped_existing,
        "errors": result.errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="discover.py",
        description=(
            "Spider an agent's configured roots and add newly-found "
            "URLs to decisions.json as pending entries."
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
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=(
            "Number of roots to walk in parallel "
            f"(default: {DEFAULT_CONCURRENCY}). Within a root, "
            "requests serialize through the per-host rate limiter."
        ),
    )
    args = parser.parse_args()

    report = run(
        project_root=args.project_root.resolve(),
        agent=args.agent,
        concurrency=args.concurrency,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
