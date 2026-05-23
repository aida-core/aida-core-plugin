# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""`/aida plugin deps` — list a plugin's declared dependencies + status.

Non-interactive, CI-friendly. Reads `dependencies` from a plugin's
`aida-config.json`, resolves each against the installed plugin set
discovered by scanning `~/.claude/plugins/cache/`, and returns a
structured report.

Phase 1 (`get_questions`): no questions — this is a one-shot read.
The inferred dict carries the dep report so callers that only run
Phase 1 (e.g., orchestrators that want a quick status) get a useful
answer without doing Phase 2.

Phase 2 (`execute`): same dep report, plus a `success` flag based on
whether every declared dep is satisfied (CI gateable).
"""

from __future__ import annotations

import glob
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from shared.dependencies import check_dependencies

logger = logging.getLogger(__name__)


def _resolve_plugin_path(context: Dict[str, Any]) -> Path:
    """Pick the plugin path from context, defaulting to cwd."""
    path_str = context.get("plugin_path") or str(Path.cwd())
    return Path(path_str).resolve()


def _read_declared_dependencies(plugin_path: Path) -> Dict[str, str]:
    """Read the `dependencies` field from a plugin's aida-config.json.

    Returns {} if the file is missing, malformed, or doesn't declare
    a dependencies field. Dep checking is best-effort — a missing
    config shouldn't crash, it should say "no deps to check".
    """
    config_path = (
        plugin_path / ".claude-plugin" / "aida-config.json"
    )
    if not config_path.is_file():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Failed to read aida-config.json at %s: %s",
            config_path,
            exc,
        )
        return {}
    if not isinstance(data, dict):
        return {}
    deps = data.get("dependencies", {})
    if not isinstance(deps, dict):
        return {}
    # Normalize: only string-keyed string-valued entries.
    return {
        name: spec
        for name, spec in deps.items()
        if isinstance(name, str) and isinstance(spec, str)
    }


def _discover_installed() -> List[Dict[str, Any]]:
    """Scan `~/.claude/plugins/cache/` for installed plugins.

    Returns a list of `{name, version}` dicts — enough for
    dep resolution. Skipped: malformed manifests, symlinked
    plugin dirs (defense-in-depth; matches the aida-skill scanner).

    Intentionally minimal vs. `utils.discover_installed_plugins`,
    which does extra TOCTOU-safe checks needed for the permissions
    scan. For dep reporting we only need name + version.
    """
    cache_root = Path.home() / ".claude" / "plugins" / "cache"
    if not cache_root.is_dir():
        return []
    pattern = str(
        cache_root / "*" / "*" / ".claude-plugin" / "plugin.json"
    )
    found: List[Dict[str, Any]] = []
    for manifest_path in sorted(glob.glob(pattern)):
        manifest = Path(manifest_path)
        if manifest.parent.is_symlink():
            logger.warning(
                "Skipping symlinked plugin dir: %s", manifest.parent
            )
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning(
                "Skipping malformed plugin manifest: %s", manifest
            )
            continue
        if not isinstance(data, dict):
            continue
        found.append(
            {
                "name": str(data.get("name", "unknown")),
                "version": str(data.get("version", "0.0.0")),
            }
        )
    return found


def get_questions(
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Phase 1: no questions — return the dep report up-front."""
    plugin_path = _resolve_plugin_path(context)
    declared = _read_declared_dependencies(plugin_path)
    installed = _discover_installed()
    report = check_dependencies(declared, installed)
    return {
        "questions": [],
        "inferred": {
            "plugin_path": str(plugin_path),
            "declared_count": len(declared),
            "results": report,
        },
        "phase": "get_questions",
    }


def execute(
    context: Dict[str, Any],
    responses: Dict[str, Any] | None = None,  # noqa: ARG001
) -> Dict[str, Any]:
    """Phase 2: same report, plus a pass/fail summary.

    Returns ``success: False`` when any dep is `missing` or
    `wrong-version` so this command is usable as a CI gate
    ("verify all deps satisfied before publishing").
    """
    plugin_path = _resolve_plugin_path(context)
    declared = _read_declared_dependencies(plugin_path)
    installed = _discover_installed()
    report = check_dependencies(declared, installed)

    failures = [r for r in report if r["status"] != "satisfied"]
    success = not failures

    summary = {
        "satisfied": sum(
            1 for r in report if r["status"] == "satisfied"
        ),
        "missing": sum(
            1 for r in report if r["status"] == "missing"
        ),
        "wrong_version": sum(
            1 for r in report if r["status"] == "wrong-version"
        ),
        "total": len(report),
    }

    if not declared:
        message = (
            f"No dependencies declared in "
            f"{plugin_path}/.claude-plugin/aida-config.json"
        )
    elif success:
        message = (
            f"All {summary['total']} dependencies satisfied"
        )
    else:
        message = (
            f"{len(failures)} of {summary['total']} dependencies "
            f"unsatisfied "
            f"({summary['missing']} missing, "
            f"{summary['wrong_version']} wrong-version)"
        )

    return {
        "success": success,
        "operation": "deps",
        "message": message,
        "plugin_path": str(plugin_path),
        "summary": summary,
        "results": report,
    }
