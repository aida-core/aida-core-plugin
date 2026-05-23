# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""`/aida plugin agents` — cross-plugin agent registry (#20).

Non-interactive, CI-friendly. Walks installed plugins and the
project / user agent directories, returns a unified roster, and
flags name collisions across plugins.

Distinct from ``/aida agent list`` (agent-manager) which is per-skill
CRUD. This view crosses plugin boundaries — useful for spotting
"two installed plugins both ship a `code-reviewer` agent" before
those collisions cause runtime confusion.

Phase 1 (`get_questions`): no questions — single-read operation.
The inferred dict carries the roster + collision summary.

Phase 2 (`execute`): same data, plus a `success` flag that goes
False when any collision is detected so this is usable as a CI
gate ("verify our plugin doesn't clash with the installed set").
"""

from __future__ import annotations

import glob
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL
)


def _resolve_project_root(context: Dict[str, Any]) -> Path:
    """Pick the project root from context, defaulting to cwd.

    Used to scan `<project>/.claude/agents/`. Defaulting to cwd
    matches the pattern in `deps.py` so the operations feel
    consistent.
    """
    path_str = context.get("project_root") or str(Path.cwd())
    return Path(path_str).resolve()


def _parse_agent_frontmatter(
    md_path: Path,
) -> Optional[Dict[str, Any]]:
    """Parse YAML frontmatter from an agent markdown file.

    Returns the parsed mapping, or None if there's no frontmatter
    or it's malformed. Defensive on purpose — a broken agent file
    shouldn't crash the registry scan.
    """
    try:
        text = md_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None

    # Use a lightweight YAML import — keep the operation dep-free
    # apart from PyYAML (which is already in requirements).
    try:
        import yaml
    except ImportError:
        return None

    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None

    return data if isinstance(data, dict) else None


def _iter_agent_files(agents_dir: Path) -> List[Path]:
    """Return agent markdown files under ``agents_dir``.

    Convention: ``agents/<name>/<name>.md``. Top-level standalone
    ``.md`` files are also picked up so existing project /
    user-level agent layouts work.
    """
    if not agents_dir.is_dir():
        return []
    results: List[Path] = []
    for md in sorted(agents_dir.rglob("*.md")):
        # Skip knowledge files / supporting docs — agents are
        # named files whose stem matches a parent directory name,
        # or a top-level md inside agents/.
        if md.parent.name == "knowledge":
            continue
        if (
            md.parent.parent == agents_dir
            and md.stem != md.parent.name
        ):
            continue
        results.append(md)
    return results


def _build_agent_entry(
    md_path: Path,
    *,
    source: str,
    source_label: str,
) -> Optional[Dict[str, Any]]:
    """Build a flat agent registry entry from a markdown file.

    Returns None on malformed input. Pulls `name` / `description`
    / `version` / `tags` from frontmatter; falls back to the file
    stem for `name` if frontmatter is missing one.
    """
    fm = _parse_agent_frontmatter(md_path) or {}
    name = fm.get("name") or md_path.stem
    if not isinstance(name, str):
        return None
    return {
        "name": name,
        "description": fm.get("description", ""),
        "version": fm.get("version", ""),
        "tags": fm.get("tags", []) or [],
        "source": source,
        "source_label": source_label,
        "path": str(md_path),
    }


def _discover_all_agents(
    project_root: Path,
) -> List[Dict[str, Any]]:
    """Walk every agent source, returning **every** agent found.

    Distinct from `utils.discover_agents` (which dedupes by name —
    first-found wins). This variant preserves duplicates so the
    caller can detect cross-plugin collisions.
    """
    agents: List[Dict[str, Any]] = []

    # 1. Project agents
    for md in _iter_agent_files(
        project_root / ".claude" / "agents"
    ):
        entry = _build_agent_entry(
            md,
            source="project",
            source_label=f"project: {project_root.name}",
        )
        if entry is not None:
            agents.append(entry)

    # 2. User agents
    user_agents = Path.home() / ".claude" / "agents"
    for md in _iter_agent_files(user_agents):
        entry = _build_agent_entry(
            md, source="user", source_label="user"
        )
        if entry is not None:
            agents.append(entry)

    # 3. Plugin agents (every plugin in the cache)
    cache_root = (
        Path.home() / ".claude" / "plugins" / "cache"
    )
    if cache_root.is_dir():
        pattern = str(
            cache_root / "*" / "*" / ".claude-plugin" / "plugin.json"
        )
        for manifest_path in sorted(glob.glob(pattern)):
            manifest = Path(manifest_path)
            if manifest.parent.is_symlink():
                continue
            plugin_root = manifest.parent.parent
            try:
                manifest_data = json.loads(
                    manifest.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(manifest_data, dict):
                continue
            plugin_name = manifest_data.get("name", plugin_root.name)
            for md in _iter_agent_files(plugin_root / "agents"):
                entry = _build_agent_entry(
                    md,
                    source="plugin",
                    source_label=f"plugin: {plugin_name}",
                )
                if entry is not None:
                    agents.append(entry)

    return agents


def _detect_collisions(
    agents: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return per-name collision groups.

    A collision is two+ agents with the same `name` from different
    sources. Same-source duplicates (two project agents with the
    same name) shouldn't really happen but get folded in too —
    the user wants to see them either way.

    Returns a sorted list of {name, count, sources} dicts.
    """
    by_name: Dict[str, List[Dict[str, Any]]] = {}
    for agent in agents:
        by_name.setdefault(agent["name"], []).append(agent)

    collisions = []
    for name in sorted(by_name):
        entries = by_name[name]
        if len(entries) < 2:
            continue
        collisions.append(
            {
                "name": name,
                "count": len(entries),
                "sources": [e["source_label"] for e in entries],
            }
        )
    return collisions


def get_questions(
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Phase 1: no questions — registry up-front in inferred."""
    project_root = _resolve_project_root(context)
    agents = _discover_all_agents(project_root)
    collisions = _detect_collisions(agents)
    return {
        "questions": [],
        "inferred": {
            "project_root": str(project_root),
            "agent_count": len(agents),
            "collision_count": len(collisions),
            "agents": agents,
            "collisions": collisions,
        },
        "phase": "get_questions",
    }


def execute(
    context: Dict[str, Any],
    responses: Dict[str, Any] | None = None,  # noqa: ARG001
) -> Dict[str, Any]:
    """Phase 2: registry + pass/fail summary.

    Returns ``success: False`` when at least one collision is
    detected so this is usable as a CI gate (e.g., "verify our
    new plugin doesn't introduce an agent-name conflict with any
    of our other installed plugins").
    """
    project_root = _resolve_project_root(context)
    agents = _discover_all_agents(project_root)
    collisions = _detect_collisions(agents)
    success = not collisions

    by_source = {}
    for agent in agents:
        by_source[agent["source"]] = (
            by_source.get(agent["source"], 0) + 1
        )

    if not agents:
        message = "No agents discovered."
    elif success:
        message = (
            f"Discovered {len(agents)} agent(s); no collisions."
        )
    else:
        message = (
            f"Discovered {len(agents)} agent(s); "
            f"{len(collisions)} name collision(s) across sources."
        )

    return {
        "success": success,
        "operation": "agents",
        "message": message,
        "project_root": str(project_root),
        "summary": {
            "total": len(agents),
            "by_source": by_source,
            "collisions": len(collisions),
        },
        "agents": agents,
        "collisions": collisions,
    }
