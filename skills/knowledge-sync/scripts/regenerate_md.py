#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Regenerate decisions.md from decisions.json (#144 Slice 2).

Repair command: if a user has hand-edited decisions.md (despite the
generated-file banner), this rebuilds it from the JSON state. The
JSON is the source of truth; markdown is derivative.

Implementation is trivial — just round-trip the JSON through
write_decisions, which regenerates the markdown atomically.
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
    read_decisions,
    write_decisions,
)


def run(
    project_root: Path,
    agent: str,
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
    try:
        write_decisions(knowledge_dir, decisions)
    except OSError as exc:
        return {
            "success": False,
            "agent": agent,
            "message": f"Could not write decisions log: {exc}",
        }
    return {
        "success": True,
        "agent": agent,
        "regenerated": str(
            knowledge_dir / "decisions.md"
        ),
        "decisions_count": len(decisions),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="regenerate_md.py",
        description=(
            "Repair: regenerate decisions.md from decisions.json."
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
    args = parser.parse_args()

    report = run(
        project_root=args.project_root.resolve(),
        agent=args.agent,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
