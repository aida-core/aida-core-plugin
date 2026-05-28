#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Manually mark a URL in-use without going through the LLM curator
(#144 Slice 2).

Useful for URLs you already know belong in an agent's corpus — you
can skip the discover → curate cycle and promote directly.

Behavior:
  - If the URL is new (no existing decision), creates an in-use
    entry from --url, --file, --section
  - If the URL exists as pending or rejected (and not locked), flips
    it to in-use with the given target metadata
  - Refuses to overwrite a locked entry — the user must run
    /aida knowledge review to flip a lock

decided_by is recorded as "human" and decided_at gets a fresh
timestamp.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

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


def run(
    project_root: Path,
    agent: str,
    url: str,
    target_file: str,
    target_section: str,
    reason: str = "",
) -> Dict[str, Any]:
    knowledge_dir = project_root / "agents" / agent / "knowledge"

    try:
        existing = read_decisions(knowledge_dir)
    except ValueError as exc:
        return {
            "success": False,
            "agent": agent,
            "message": str(exc),
        }

    current = find_by_url(existing, url)
    if current is not None and current.locked:
        return {
            "success": False,
            "agent": agent,
            "message": (
                f"Decision for {url!r} is locked ({current.status}). "
                "Run `/aida knowledge review` to flip the lock."
            ),
        }

    promoted = Decision(
        url=url,
        status="in-use",
        decided_at=now_iso(),
        decided_by="human",
        reason=reason or "Manually promoted via /aida knowledge promote.",
        target_file=target_file,
        target_section=target_section,
        # Preserve the discovery metadata if it existed
        discovered_at=current.discovered_at if current else None,
        source_root=current.source_root if current else None,
        informs=current.informs if current else [],
    )
    next_decisions = upsert_decision(existing, promoted)
    try:
        write_decisions(knowledge_dir, next_decisions)
    except OSError as exc:
        return {
            "success": False,
            "agent": agent,
            "message": f"Could not write decisions log: {exc}",
        }
    return {
        "success": True,
        "agent": agent,
        "url": url,
        "previous_status": current.status if current else None,
        "new_status": "in-use",
        "target_file": target_file,
        "target_section": target_section,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="promote.py",
        description=(
            "Manually mark a URL in-use, bypassing the LLM curator."
        ),
    )
    parser.add_argument(
        "--agent",
        required=True,
        help="Agent name (e.g., 'claude-code-expert')",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="The URL to promote.",
    )
    parser.add_argument(
        "--file",
        dest="target_file",
        required=True,
        help=(
            "The knowledge file this URL syncs into "
            "(e.g., 'skills.md')."
        ),
    )
    parser.add_argument(
        "--section",
        dest="target_section",
        required=True,
        help=(
            "The marker-block section name within the knowledge "
            "file (e.g., 'claude-skills-upstream')."
        ),
    )
    parser.add_argument(
        "--reason",
        default="",
        help=(
            "Optional reason recorded with the decision. Falls "
            "back to a generic 'manually promoted' note if empty."
        ),
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root (default: current directory)",
    )
    args = parser.parse_args()

    report = run(
        project_root=args.project_root.resolve(),
        agent=args.agent,
        url=args.url,
        target_file=args.target_file,
        target_section=args.target_section,
        reason=args.reason,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
