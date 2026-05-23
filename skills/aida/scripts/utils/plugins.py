# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Plugin discovery and configuration utilities.

Scans installed plugins for configuration sections and generates
interactive questions for the setup wizard.
"""

from __future__ import annotations

import errno
import glob
import logging
import os
from pathlib import Path

from .errors import ConfigurationError
from .json_utils import safe_json_load
from .paths import get_home_dir

logger = logging.getLogger(__name__)

# Maximum file size for plugin JSON files (1 MB).
_MAX_FILE_SIZE = 1024 * 1024

VALID_PREFERENCE_TYPES = {"boolean", "choice", "string"}

PREFERENCE_TYPE_MAP = {
    "boolean": "boolean",
    "choice": "choice",
    "string": "text",
}


def _safe_read_file(
    file_path: Path,
    label: str,
    resolved_root: Path | None = None,
    max_size: int | None = None,
) -> str | None:
    """Read a file with TOCTOU-safe security checks.

    Uses ``O_NOFOLLOW`` to atomically reject symlinks during open,
    eliminating race conditions between symlink/size checks and
    file reads.  Optionally validates the resolved path stays
    within a cache root directory.

    Args:
        file_path: Path to the file.
        label: Human-readable label for log messages.
        resolved_root: If provided, validate that the file's
            resolved path is within this root.
        max_size: Maximum allowed file size in bytes.
            Defaults to ``_MAX_FILE_SIZE`` (1 MB).

    Returns:
        File content as string, or ``None`` on error.
    """
    if max_size is None:
        max_size = _MAX_FILE_SIZE

    # Path containment check (catches non-symlink traversal
    # via ``..`` components that the glob might match)
    if resolved_root is not None:
        try:
            file_path.resolve().relative_to(resolved_root)
        except ValueError:
            logger.warning(
                "%s path outside cache root: %s",
                label,
                file_path,
            )
            return None

    fd = -1
    try:
        fd = os.open(
            str(file_path), os.O_RDONLY | os.O_NOFOLLOW
        )
        st = os.fstat(fd)
        if st.st_size > max_size:
            logger.warning(
                "%s too large: %s", label, file_path
            )
            return None
        with os.fdopen(fd, "r", encoding="utf-8") as f:
            fd = -1  # fd now owned by file object
            return f.read()
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            logger.warning(
                "Skipping symlink %s: %s", label, file_path
            )
        elif exc.errno != errno.ENOENT:
            logger.warning(
                "Failed to read %s %s: %s",
                label,
                file_path,
                exc,
            )
        return None
    finally:
        if fd >= 0:
            os.close(fd)


def _read_aida_config(
    plugin_dir: Path, resolved_root: Path | None
) -> dict | None:
    """Read AIDA-specific configuration from aida-config.json.

    AIDA fields (``config`` and ``recommendedPermissions``) are
    stored separately from the standard Claude Code plugin manifest
    in ``.claude-plugin/aida-config.json``.

    Uses ``O_NOFOLLOW`` to atomically reject symlinks.

    Args:
        plugin_dir: Path to the ``.claude-plugin`` directory.
        resolved_root: Resolved cache root for path validation,
            or ``None`` if the cache root does not exist.

    Returns:
        Parsed dict from ``aida-config.json``, or ``None`` if
        the file is missing, invalid, or fails security checks.
    """
    config_path = plugin_dir / "aida-config.json"
    raw = _safe_read_file(
        config_path, "aida-config.json", resolved_root
    )
    if raw is None:
        return None

    try:
        data = safe_json_load(raw)
        if not isinstance(data, dict):
            logger.warning(
                "aida-config.json is not an object: %s",
                config_path,
            )
            return None
        return data
    except Exception:
        logger.warning(
            "Failed to read aida-config.json: %s",
            config_path,
            exc_info=True,
        )
        return None


def discover_installed_plugins() -> list[dict]:
    """Scan installed plugins and return their metadata.

    Looks for plugin.json files in the standard plugin cache
    directory (~/.claude/plugins/cache/*/*/.claude-plugin/plugin.json).

    AIDA-specific fields (``config`` and ``recommendedPermissions``)
    are read from a separate ``aida-config.json`` in the same
    directory. These fields are never read from ``plugin.json``.

    Returns:
        List of dicts with keys: name, version, config,
        recommendedPermissions, plugin_dir.
    """
    claude_dir = get_home_dir() / ".claude"
    cache_root = claude_dir / "plugins" / "cache"
    pattern = str(
        cache_root
        / "*"
        / "*"
        / ".claude-plugin"
        / "plugin.json"
    )
    resolved_root = cache_root.resolve() if cache_root.is_dir() else None
    plugins = []
    for manifest_path in sorted(glob.glob(pattern)):
        try:
            manifest_file = Path(manifest_path)
            plugin_dir_path = manifest_file.parent

            # Reject symlinked .claude-plugin directories
            if plugin_dir_path.is_symlink():
                logger.warning(
                    "Skipping symlink plugin directory: %s",
                    plugin_dir_path,
                )
                continue

            # Read manifest with TOCTOU-safe security checks
            raw = _safe_read_file(
                manifest_file,
                "plugin manifest",
                resolved_root,
            )
            if raw is None:
                continue

            data = safe_json_load(raw)
            if not isinstance(data, dict):
                logger.warning(
                    "Plugin manifest is not an object: %s",
                    manifest_path,
                )
                continue

            aida_config = _read_aida_config(
                plugin_dir_path, resolved_root
            )

            # Surface dependencies declared in aida-config.json
            # (#20). Treated as an optional plain dict; downstream
            # callers use `utils.dependencies.check_dependencies()`
            # to resolve specs against installed plugins.
            dependencies_raw = (
                aida_config.get("dependencies", {})
                if aida_config
                else {}
            )
            dependencies = (
                dependencies_raw
                if isinstance(dependencies_raw, dict)
                else {}
            )

            plugins.append(
                {
                    "name": data.get("name", "unknown"),
                    "version": data.get("version", "0.0.0"),
                    "config": (
                        aida_config.get("config", {})
                        if aida_config
                        else {}
                    ),
                    "dependencies": dependencies,
                    "recommendedPermissions": (
                        aida_config.get(
                            "recommendedPermissions", {}
                        )
                        if aida_config
                        else {}
                    ),
                    "plugin_dir": str(
                        plugin_dir_path.parent
                    ),
                }
            )
        except Exception:
            logger.warning(
                "Failed to load plugin manifest: %s",
                manifest_path,
                exc_info=True,
            )
    return plugins


def get_plugins_with_config(plugins: list[dict]) -> list[dict]:
    """Filter plugins that have a non-empty config section.

    Args:
        plugins: List of plugin dicts from discover_installed_plugins.

    Returns:
        Filtered list of plugins with config sections.
    """
    return [p for p in plugins if p.get("config")]


def validate_plugin_config(config: dict, plugin_name: str) -> None:
    """Validate a plugin's config section structure.

    Args:
        config: The config dict from aida-config.json.
        plugin_name: Plugin name for error messages.

    Raises:
        ConfigurationError: If config is invalid.
    """
    for field in ("label", "description", "preferences"):
        if field not in config:
            raise ConfigurationError(
                f"Plugin '{plugin_name}' config missing "
                f"required field: {field}"
            )

    if not isinstance(config["label"], str):
        raise ConfigurationError(
            f"Plugin '{plugin_name}' config 'label' "
            "must be a string"
        )
    if not isinstance(config["description"], str):
        raise ConfigurationError(
            f"Plugin '{plugin_name}' config 'description' "
            "must be a string"
        )
    if not isinstance(config["preferences"], list):
        raise ConfigurationError(
            f"Plugin '{plugin_name}' config 'preferences' "
            "must be a list"
        )

    for i, pref in enumerate(config["preferences"]):
        for req in ("key", "type", "label"):
            if req not in pref:
                raise ConfigurationError(
                    f"Plugin '{plugin_name}' preference [{i}] "
                    f"missing required field: {req}"
                )
            if not isinstance(pref[req], str):
                raise ConfigurationError(
                    f"Plugin '{plugin_name}' preference [{i}] "
                    f"'{req}' must be a string"
                )

        if pref["type"] not in VALID_PREFERENCE_TYPES:
            raise ConfigurationError(
                f"Plugin '{plugin_name}' preference [{i}] "
                f"has invalid type '{pref['type']}'. "
                f"Must be one of: "
                f"{', '.join(sorted(VALID_PREFERENCE_TYPES))}"
            )

        if pref["type"] == "choice" and "options" not in pref:
            raise ConfigurationError(
                f"Plugin '{plugin_name}' preference [{i}] "
                "is type 'choice' but missing 'options'"
            )
        if (
            pref["type"] == "choice"
            and not isinstance(pref.get("options"), list)
        ):
            raise ConfigurationError(
                f"Plugin '{plugin_name}' preference [{i}] "
                "'options' must be a list"
            )


def generate_plugin_checklist(plugins: list[dict]) -> dict | None:
    """Generate a multi-select question for plugin selection.

    Args:
        plugins: List of plugins with config sections.

    Returns:
        A question dict for multi-select, or None if empty.
    """
    if not plugins:
        return None

    options = []
    for plugin in plugins:
        config = plugin.get("config", {})
        try:
            validate_plugin_config(config, plugin["name"])
        except ConfigurationError:
            logger.warning(
                "Skipping plugin with invalid config: %s",
                plugin["name"],
                exc_info=True,
            )
            continue
        options.append(
            {
                "label": config["label"],
                "value": plugin["name"],
                "description": config["description"],
            }
        )

    if not options:
        return None

    return {
        "id": "selected_plugins",
        "question": "Which plugins would you like to configure?",
        "type": "multiselect",
        "options": options,
        "required": False,
    }


def generate_plugin_preference_questions(
    selected_plugin_names: list[str],
    plugins: list[dict],
) -> list[dict]:
    """Generate preference questions for selected plugins.

    Args:
        selected_plugin_names: Names of plugins user selected.
        plugins: Full list of plugins with config sections.

    Returns:
        Flat list of question dicts for plugin preferences.
    """
    questions = []
    plugin_map = {p["name"]: p for p in plugins}

    for name in selected_plugin_names:
        plugin = plugin_map.get(name)
        if not plugin:
            continue

        config = plugin.get("config", {})
        preferences = config.get("preferences", [])

        for pref in preferences:
            key = pref.get("key", "")
            # Use __ as delimiter between name and key to avoid
            # collisions with underscores in plugin names or keys
            question_id = f"plugin_{name}__{key.replace('.', '_')}"
            q_type = PREFERENCE_TYPE_MAP.get(pref.get("type", ""), "text")

            question: dict = {
                "id": question_id,
                "question": pref.get("label", key),
                "type": q_type,
                "_plugin_name": name,
            }

            if "default" in pref:
                question["default"] = pref["default"]

            if q_type == "choice" and "options" in pref:
                question["options"] = pref["options"]

            if "description" in pref:
                question["description"] = pref["description"]

            questions.append(question)

    return questions
