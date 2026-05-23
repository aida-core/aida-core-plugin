#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Validate AIDA configuration files for a project.

Non-interactive, CI-friendly. Checks:

  - `.claude/aida.yml` (project marker) exists and parses as valid YAML
  - `.claude/aida-project-context.yml` (+ optional .local overlay)
    exists, parses, and has the expected top-level shape
  - The merged project context has the keys the rest of AIDA expects
    (vcs, files, languages, etc.)

Exits 0 on success, 1 on any validation failure. Prints a structured
JSON report on stdout when --json is passed, otherwise a human report.

Usage:
    python validate.py [--project-root PATH] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Path setup so this can run standalone or via /aida config validate
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# Re-use the existing loader so validation never disagrees with what
# AIDA actually reads.
import _paths  # noqa: F401, E402 — adds shared/ to sys.path
from utils.project_context import (  # noqa: E402
    PROJECT_CONTEXT_FILE,
    PROJECT_CONTEXT_LOCAL_FILE,
    load_project_context,
)

import yaml  # noqa: E402


# Top-level keys we expect to find in a complete project-context YAML.
# These mirror what `configure.py` writes. The validator only cares
# that they're present and well-shaped; specific value enums get
# checked in the value-shape section.
EXPECTED_TOP_LEVEL_KEYS = {
    # `schema_version` (post-#39) is the project-context schema
    # version, distinct from the AIDA app version. Legacy configs
    # with `version` are migrated in-memory so this key is always
    # present after `load_project_context()`.
    "schema_version",
    "project_name",
    "vcs",
    "files",
    "languages",
    "tools",
    "inferred",
    "preferences",
}


def _check_global_install(home: Path) -> List[str]:
    """Return a list of issue strings for the global install marker.

    Empty list = pass.
    """
    issues: List[str] = []
    marker = home / ".claude" / "aida.yml"
    if not marker.is_file():
        issues.append(
            f"Global AIDA marker missing: {marker} "
            "(run /aida config and choose 'Set up AIDA globally')"
        )
    return issues


def _check_project_marker(project_root: Path) -> List[str]:
    """Validate `.claude/aida.yml` (the project-level marker)."""
    issues: List[str] = []
    marker = project_root / ".claude" / "aida.yml"
    if not marker.is_file():
        issues.append(
            f"Project marker missing: {marker} "
            "(run /aida config and choose 'Configure this project')"
        )
        return issues
    try:
        data = yaml.safe_load(marker.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        issues.append(f"Project marker fails YAML parse: {exc}")
        return issues
    if not isinstance(data, dict):
        issues.append(
            f"Project marker is not a mapping: got "
            f"{type(data).__name__}"
        )
        return issues
    if "version" not in data:
        issues.append("Project marker missing 'version' field")
    if "project" not in data or not isinstance(
        data.get("project"), dict
    ):
        issues.append(
            "Project marker missing 'project' mapping"
        )
    return issues


def _check_project_context(
    project_root: Path,
) -> List[str]:
    """Validate the project-context YAML pair.

    Loads via the same path AIDA's runtime uses (committed file +
    optional `.local` overlay) so the validator never disagrees with
    what consumers actually read.
    """
    issues: List[str] = []
    claude_dir = project_root / ".claude"
    committed = claude_dir / PROJECT_CONTEXT_FILE
    local = claude_dir / PROJECT_CONTEXT_LOCAL_FILE

    if not committed.is_file():
        issues.append(
            f"Project context missing: {committed}"
        )
        return issues

    # YAML parse — separate from the merged-load to surface parse
    # errors with file-specific context.
    for path in (committed, local):
        if not path.is_file():
            continue
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            issues.append(
                f"{path.name} fails YAML parse: {exc}"
            )

    if issues:
        return issues

    merged = load_project_context(project_root)
    if not isinstance(merged, dict):
        issues.append(
            "Merged project context is not a mapping: got "
            f"{type(merged).__name__}"
        )
        return issues

    missing = EXPECTED_TOP_LEVEL_KEYS - set(merged.keys())
    if missing:
        issues.append(
            "Merged project context missing expected keys: "
            + ", ".join(sorted(missing))
        )

    # Specific value shapes
    vcs = merged.get("vcs")
    if vcs is not None and not isinstance(vcs, dict):
        issues.append(
            f"vcs section must be a mapping, got "
            f"{type(vcs).__name__}"
        )
    files = merged.get("files")
    if files is not None and not isinstance(files, dict):
        issues.append(
            f"files section must be a mapping, got "
            f"{type(files).__name__}"
        )
    prefs = merged.get("preferences")
    if prefs is not None and not isinstance(prefs, dict):
        issues.append(
            f"preferences section must be a mapping, got "
            f"{type(prefs).__name__}"
        )

    return issues


def validate(
    project_root: Path, home: Path
) -> Dict[str, Any]:
    """Run all validation checks and return a structured report.

    Args:
        project_root: Project to validate
        home: User's home dir (for global marker check)

    Returns:
        Dict with `valid`, `errors`, and per-check details
    """
    global_issues = _check_global_install(home)
    marker_issues = _check_project_marker(project_root)
    context_issues = _check_project_context(project_root)

    all_errors = (
        global_issues + marker_issues + context_issues
    )
    return {
        "valid": not all_errors,
        "errors": all_errors,
        "checks": {
            "global_install": {
                "pass": not global_issues,
                "errors": global_issues,
            },
            "project_marker": {
                "pass": not marker_issues,
                "errors": marker_issues,
            },
            "project_context": {
                "pass": not context_issues,
                "errors": context_issues,
            },
        },
        "project_root": str(project_root),
    }


def _format_human(report: Dict[str, Any]) -> str:
    """Format a validation report as human-readable text."""
    lines = ["AIDA Configuration Validation"]
    lines.append("=" * 60)
    lines.append(f"Project: {report['project_root']}")
    lines.append("")
    for name, check in report["checks"].items():
        marker = "✓" if check["pass"] else "✗"
        lines.append(
            f"{marker} {name.replace('_', ' ').title()}"
        )
        for err in check["errors"]:
            lines.append(f"    {err}")
    lines.append("")
    if report["valid"]:
        lines.append("✓ Configuration is valid.")
    else:
        lines.append(
            f"✗ Configuration has {len(report['errors'])} "
            "issue(s). See above."
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="validate.py",
        description=(
            "Validate AIDA configuration files for a project."
        ),
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root (default: current directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the report as JSON (CI-friendly)",
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    home = Path.home()

    report = validate(project_root, home)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_format_human(report))

    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
