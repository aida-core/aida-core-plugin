# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Split/merge helpers for the project-context YAML files.

The project context lives in two files under `.claude/`:

- `aida-project-context.yml` — committed; project-level facts (vcs.type,
  languages, tools, preferences, etc.). Should be identical across every
  contributor's working copy.
- `aida-project-context.local.yml` — gitignored; user/environment overlay
  (project_root, vcs.remote_url, last_updated, config_complete).

Consumers should always read via `load_project_context()`, which merges
both files (local overrides project). Writers should always go through
`write_project_context()`, which splits a merged dict and writes both
files atomically.

Legacy single-file projects (everything in `aida-project-context.yml`)
read transparently through `load_project_context()`; the next call to
`write_project_context()` migrates them by emitting both files.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import yaml

from .errors import ConfigurationError, FileOperationError
from .files import read_file, write_yaml

logger = logging.getLogger(__name__)

PROJECT_CONTEXT_FILE = "aida-project-context.yml"
PROJECT_CONTEXT_LOCAL_FILE = "aida-project-context.local.yml"

# Schema version for the project-context YAML pair. **Separate from
# the AIDA app version (#39)** — apps and schemas evolve at
# independent rates. Bump major for breaking changes (removed/renamed
# fields), minor for additive fields, patch for clarifications.
#
# Migration policy:
#   - Reading older schema_version: apply migrations in order until
#     the file matches CURRENT. The migrated dict stays in memory;
#     the next write_project_context() persists the upgrade.
#   - Reading newer schema_version: log a warning and return the
#     dict as-is. Additive fields are safe to ignore; removed or
#     renamed fields will manifest as KeyError downstream, which is
#     better than a silent miscompile.
#   - Reading no schema_version (legacy files, including those that
#     used the old `version` field with the app version): treat as
#     1.0.0 and pass through unchanged. The shape hasn't actually
#     changed yet, so this is safe.
PROJECT_CONTEXT_SCHEMA_VERSION = "1.0.0"


# Migrations registry. Each entry maps a from_version to a callable
# that transforms a dict into the *next* schema version. The
# orchestrator (`migrate_to_current`) walks this in sequence until
# the dict matches PROJECT_CONTEXT_SCHEMA_VERSION.
#
# Convention: each migrator returns (migrated_dict, new_version).
# Empty today because we just defined version 1.0.0; this is the
# scaffolding for future schema changes.
_MIGRATIONS: Dict[
    str, Callable[[Dict[str, Any]], Tuple[Dict[str, Any], str]]
] = {}


def _read_schema_version(data: Dict[str, Any]) -> str:
    """Read the schema version from a context dict.

    Precedence (handles the messy real world):
      1. `schema_version` field (new, post-#39)
      2. `version` field (legacy — was actually the app version,
         but we treat it as 1.0.0 since the shape didn't change)
      3. No version field at all (pre-versioning) -> 1.0.0
    """
    if "schema_version" in data:
        return str(data["schema_version"])
    if "version" in data:
        # Legacy `version` field carried the app version, not the
        # schema version. The shape was identical to 1.0.0, so treat
        # the file as 1.0.0 and let `write_project_context` rewrite
        # with the correct field on the next save.
        return "1.0.0"
    return "1.0.0"


def _compare_versions(a: str, b: str) -> int:
    """Return -1/0/1 for a < b / a == b / a > b on semver-ish strings.

    Tolerates non-semver strings by falling back to lexical compare
    (we don't want to crash on a corrupt schema_version field).
    """
    def _parts(v: str) -> Tuple[int, ...]:
        try:
            return tuple(int(p) for p in v.split("."))
        except ValueError:
            return tuple()

    pa, pb = _parts(a), _parts(b)
    if not pa or not pb:
        return (a > b) - (a < b)
    if pa < pb:
        return -1
    if pa > pb:
        return 1
    return 0


def migrate_to_current(
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Migrate a loaded context dict to ``PROJECT_CONTEXT_SCHEMA_VERSION``.

    Returns a *new* dict (does not mutate input).

    Behavior:
      - At current version: returns the dict with schema_version
        stamped (in case it was a legacy file)
      - Older: walks `_MIGRATIONS` to bring the dict forward
      - Newer: logs a warning and returns as-is (best-effort
        forward compat; downstream code is on its own)
      - Unknown intermediate version (no migration registered):
        logs a warning and returns as-is rather than crashing
    """
    if not data:
        return {}

    current = PROJECT_CONTEXT_SCHEMA_VERSION
    found = _read_schema_version(data)
    cmp = _compare_versions(found, current)

    if cmp > 0:
        logger.warning(
            "Project context schema_version %s is newer than "
            "this AIDA install (%s). Reading anyway; missing "
            "fields will surface as errors downstream.",
            found,
            current,
        )
        return dict(data)

    # cmp <= 0: walk migrations forward.
    migrated = dict(data)
    visited: set[str] = set()
    while _compare_versions(found, current) < 0:
        if found in visited:
            logger.warning(
                "Migration loop detected at schema_version %s; "
                "stopping. Loaded data may be incomplete.",
                found,
            )
            break
        visited.add(found)

        migrator = _MIGRATIONS.get(found)
        if migrator is None:
            logger.warning(
                "No migration registered from schema_version %s "
                "to %s; using file as-is.",
                found,
                current,
            )
            break
        migrated, found = migrator(migrated)

    migrated["schema_version"] = current
    return migrated


# Top-level keys that belong in the gitignored .local overlay.
_LOCAL_TOP_LEVEL_KEYS = frozenset(
    {"project_root", "last_updated", "config_complete"}
)

# Nested keys that belong in .local. Keyed by parent → child name.
# Per issue #65, only `vcs.remote_url` is user-specific; the rest of vcs
# (type, has_vcs, uses_worktrees, is_github, is_gitlab) is project-level.
_LOCAL_NESTED_KEYS: Dict[str, frozenset] = {
    "vcs": frozenset({"remote_url"}),
}


def split_context(merged: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Split a merged context dict into (project, local) components.

    Project-level keys go to the committed file; user-specific keys
    (paths, remote URLs, timestamps) go to the gitignored .local file.

    Empty parent dicts that result from extracting all their children
    are dropped so `local` doesn't carry stub `vcs: {}` entries.
    """
    project: Dict[str, Any] = {}
    local: Dict[str, Any] = {}

    for key, value in merged.items():
        if key in _LOCAL_TOP_LEVEL_KEYS:
            local[key] = value
            continue

        nested_local_keys = _LOCAL_NESTED_KEYS.get(key)
        if nested_local_keys and isinstance(value, dict):
            project_subset = {
                k: v for k, v in value.items() if k not in nested_local_keys
            }
            local_subset = {
                k: v for k, v in value.items() if k in nested_local_keys
            }
            if project_subset:
                project[key] = project_subset
            if local_subset:
                local[key] = local_subset
            continue

        project[key] = value

    return project, local


def merge_context(
    project: Dict[str, Any], local: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge a project + local pair into a single dict.

    Local values override project values at the leaf level. Nested dicts
    are merged shallowly (one level deep, matching the split semantics).
    """
    merged: Dict[str, Any] = {}
    for key, value in project.items():
        merged[key] = dict(value) if isinstance(value, dict) else value

    for key, value in local.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key].update(value)
        else:
            merged[key] = value

    return merged


def _read_yaml_if_exists(path: Path) -> Optional[Dict[str, Any]]:
    """Load a YAML mapping from path, returning None if the file is absent.

    Raises ConfigurationError on parse failure or if the document is not
    a mapping.
    """
    if not path.exists():
        return None
    try:
        text = read_file(path)
    except FileOperationError:
        raise
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        raise ConfigurationError(
            f"Cannot parse {path.name}: {e}",
            f"Fix the YAML syntax in {path}, or delete the file and rerun"
            " /aida config to regenerate it.",
        ) from e
    if not isinstance(data, dict):
        raise ConfigurationError(
            f"{path.name} is not a YAML mapping (got {type(data).__name__})",
            f"Expected a top-level mapping in {path}.",
        )
    return data


def load_project_context(project_root: Path) -> Dict[str, Any]:
    """Load the merged project context from `.claude/`.

    Reads `aida-project-context.yml` and (if present) overlays
    `aida-project-context.local.yml`. Returns an empty dict if neither
    file exists.

    Legacy single-file projects (no `.local.yml`) still work — the
    committed file is returned as-is; the split happens on the next
    write.

    Applies any registered schema migrations (#39) so callers always
    see a dict at the current schema version. Migrations happen
    in-memory; the next `write_project_context()` persists them.
    """
    claude_dir = project_root / ".claude"
    project = _read_yaml_if_exists(claude_dir / PROJECT_CONTEXT_FILE) or {}
    local = _read_yaml_if_exists(claude_dir / PROJECT_CONTEXT_LOCAL_FILE) or {}
    merged = merge_context(project, local)
    if merged:
        merged = migrate_to_current(merged)
    return merged


def write_project_context(
    project_root: Path, merged: Dict[str, Any]
) -> Tuple[Path, Path]:
    """Split `merged` and write the project + local files atomically.

    Returns (project_path, local_path). Both files are written even if
    one of the components is empty — an empty `.local` file is fine and
    keeps the gitignore expectation stable.
    """
    claude_dir = project_root / ".claude"
    project_path = claude_dir / PROJECT_CONTEXT_FILE
    local_path = claude_dir / PROJECT_CONTEXT_LOCAL_FILE

    project, local = split_context(merged)
    write_yaml(project_path, project)
    write_yaml(local_path, local)
    return project_path, local_path


_GITIGNORE_BLOCK_HEADER = "# AIDA project context (user-specific overlay)"


def ensure_gitignore_entry(project_root: Path) -> bool:
    """Append the AIDA local-overlay block to `.gitignore` if missing.

    Returns True if the gitignore was modified, False if it was already
    up-to-date or `.gitignore` does not exist (we don't create one — that
    decision belongs to the project, not /aida config).

    The entry is anchored to the `.claude/` path so it doesn't conflict
    with similarly-named files elsewhere in the tree.
    """
    gitignore_path = project_root / ".gitignore"
    if not gitignore_path.exists():
        return False

    entry = f".claude/{PROJECT_CONTEXT_LOCAL_FILE}"
    try:
        current = read_file(gitignore_path)
    except FileOperationError:
        return False

    # Idempotency: skip if the entry is already present in any non-comment line.
    for line in current.splitlines():
        if line.strip() == entry:
            return False

    block = f"\n{_GITIGNORE_BLOCK_HEADER}\n{entry}\n"
    if not current.endswith("\n") and current:
        block = "\n" + block
    new_content = current + block

    from .files import write_file as _write_file

    _write_file(gitignore_path, new_content, create_parents=False)
    return True
