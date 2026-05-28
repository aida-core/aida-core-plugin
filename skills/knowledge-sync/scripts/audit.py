#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Knowledge audit report (#144 Slice 2).

Reads `agents/<agent>/knowledge/decisions.json` and reports:
  - count by status (pending / in-use / rejected, locked subtotal)
  - oldest / newest decided_at among LLM verdicts (signal that a
    re-curate pass may be due)
  - URLs with last_synced older than a threshold (stale syncs)
  - URLs that are in-use but missing target_file / target_section
    (would fail to materialize during sync)

Doctor's job stays "is the local environment healthy?" Audit's job
is "is this agent's curated knowledge healthy?" — different scopes,
different commands.

Output is JSON on stdout; exit 0 always (audit reports state; it
doesn't fail).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).parent
SHARED = SCRIPT_DIR.parent.parent.parent / "scripts"
sys.path.insert(0, str(SHARED))

from shared.decisions_log import (  # noqa: E402
    Decision,
    read_decisions,
)

# Decisions older than this without re-review are flagged as stale.
DEFAULT_STALE_AFTER_DAYS = 90


def _parse_iso(stamp: Optional[str]) -> Optional[datetime]:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp)
    except ValueError:
        return None


def _age_days(stamp: Optional[str], now: datetime) -> Optional[float]:
    parsed = _parse_iso(stamp)
    if parsed is None:
        return None
    return (now - parsed).total_seconds() / 86_400


def _missing_target(d: Decision) -> bool:
    """In-use decision lacks the metadata sync needs to materialize."""
    if d.status != "in-use":
        return False
    target_file = d.target_file or (
        d.informs[0] if d.informs else None
    )
    return not target_file or not d.target_section


def run(
    project_root: Path,
    agent: str,
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
) -> Dict[str, Any]:
    knowledge_dir = project_root / "agents" / agent / "knowledge"
    try:
        decisions = read_decisions(knowledge_dir)
    except ValueError as exc:
        return {
            "success": False,
            "agent": agent,
            "message": str(exc),
        }

    now = datetime.now(timezone.utc)

    in_use = [d for d in decisions if d.status == "in-use"]
    rejected = [d for d in decisions if d.status == "rejected"]
    pending = [d for d in decisions if d.status == "pending"]
    locked_rejected = [d for d in rejected if d.locked]

    # Decisions LLM made — flag stale ones that may benefit from a
    # human review.
    llm_decisions = [d for d in decisions if d.decided_by == "llm"]
    stale_llm_decisions: List[Dict[str, Any]] = []
    for d in llm_decisions:
        if d.locked:
            continue
        age = _age_days(d.decided_at, now)
        if age is not None and age > stale_after_days:
            stale_llm_decisions.append(
                {
                    "url": d.url,
                    "decided_at": d.decided_at,
                    "age_days": round(age, 1),
                    "status": d.status,
                }
            )

    # In-use entries that haven't been synced recently (using
    # last_synced field, which sync populates).
    never_synced = [
        d.url for d in in_use if not d.last_synced
    ]

    # In-use entries missing the metadata sync needs.
    missing_target = [
        d.url for d in decisions if _missing_target(d)
    ]

    return {
        "success": True,
        "agent": agent,
        "totals": {
            "all": len(decisions),
            "in_use": len(in_use),
            "rejected": len(rejected),
            "rejected_locked": len(locked_rejected),
            "pending": len(pending),
        },
        "pending_urls": [d.url for d in pending],
        "stale_llm_decisions": stale_llm_decisions,
        "stale_after_days": stale_after_days,
        "never_synced": never_synced,
        "missing_target": missing_target,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="audit.py",
        description=(
            "Audit an agent's decision log — pending count, stale "
            "LLM verdicts, never-synced in-use entries, and in-use "
            "entries missing sync metadata."
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
        "--stale-after-days",
        type=int,
        default=DEFAULT_STALE_AFTER_DAYS,
        help=(
            "Flag LLM verdicts older than this many days as stale "
            f"(default: {DEFAULT_STALE_AFTER_DAYS})."
        ),
    )
    args = parser.parse_args()

    report = run(
        project_root=args.project_root.resolve(),
        agent=args.agent,
        stale_after_days=args.stale_after_days,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
