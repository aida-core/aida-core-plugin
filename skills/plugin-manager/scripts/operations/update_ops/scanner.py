# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Plugin scanner for the update operation.

Scans an existing plugin directory, compares each file against
the current scaffold templates, and produces a DiffReport.

This module is strictly read-only: it never modifies any files
on disk.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.utils import render_template

from ..constants import GENERATOR_VERSION
from ..shared import build_template_variables
from .models import (
    DiffReport,
    FileCategory,
    FileDiff,
    FileStatus,
    MergeStrategy,
)
from .parsers import extract_makefile_targets, parse_gitignore_entries
from .strategies import FileSpec, get_file_specs

logger = logging.getLogger(__name__)


def scan_plugin(
    plugin_path: Path,
    templates_dir: Path,
) -> DiffReport:
    """Scan a plugin directory and produce a DiffReport.

    Reads the plugin metadata, detects the language, renders
    each scaffold template, and compares expected vs actual
    file contents.

    Args:
        plugin_path: Absolute path to the plugin directory
        templates_dir: Path to the scaffold templates directory

    Returns:
        DiffReport comparing actual files to current standards

    Raises:
        ValueError: If plugin_path lacks a plugin.json manifest
    """
    plugin_json = (
        plugin_path / ".claude-plugin" / "plugin.json"
    )
    if not plugin_json.exists():
        raise ValueError(
            f"Not a valid plugin: {plugin_path} "
            "(missing .claude-plugin/plugin.json)"
        )

    metadata = _read_plugin_metadata(plugin_path)
    gen_version = _read_generator_version(plugin_path)
    language = _detect_language(plugin_path)

    context = _build_scan_context(
        plugin_path, metadata, language
    )
    license_text = _resolve_license_text(context)
    variables = build_template_variables(
        context, license_text
    )

    specs = get_file_specs(language)
    diffs: list[FileDiff] = []

    for spec in specs:
        try:
            diff = _compare_file(
                plugin_path, spec, variables, templates_dir
            )
            diffs.append(diff)
        except Exception:
            logger.warning(
                "Error comparing %s, marking as outdated",
                spec.path,
                exc_info=True,
            )
            diffs.append(
                FileDiff(
                    path=spec.path,
                    category=spec.category,
                    status=FileStatus.OUTDATED,
                    strategy=spec.default_strategy,
                    diff_summary=(
                        "Error during comparison"
                    ),
                )
            )

    return DiffReport(
        plugin_path=str(plugin_path),
        plugin_name=metadata.get("name", "unknown"),
        language=language,
        generator_version=gen_version,
        current_version=GENERATOR_VERSION,
        files=diffs,
    )


def _read_plugin_metadata(
    plugin_path: Path,
) -> dict[str, Any]:
    """Read and parse .claude-plugin/plugin.json.

    Args:
        plugin_path: Absolute path to the plugin directory

    Returns:
        Parsed plugin.json as a dictionary
    """
    plugin_json = (
        plugin_path / ".claude-plugin" / "plugin.json"
    )
    try:
        return json.loads(plugin_json.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "Failed to read plugin.json: %s", exc
        )
        return {}


def _read_generator_version(plugin_path: Path) -> str:
    """Read the generator_version from aida-config.json.

    Args:
        plugin_path: Absolute path to the plugin directory

    Returns:
        Version string, or "0.0.0" if unavailable
    """
    config_path = (
        plugin_path / ".claude-plugin" / "aida-config.json"
    )
    if not config_path.exists():
        return "0.0.0"

    try:
        data = json.loads(config_path.read_text())
        return data.get("generator_version", "0.0.0")
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "Failed to read aida-config.json: %s", exc
        )
        return "0.0.0"


def _detect_language(plugin_path: Path) -> str:
    """Detect the plugin language.

    Prefers ``.claude-plugin/aida-scaffold.json`` (#110) — that
    records the exact language chosen at scaffold time, including
    ``"none"`` for skills-only plugins. Falls back to filesystem
    inference for plugins scaffolded before the metadata existed:

    - ``pyproject.toml`` -> ``"python"``
    - ``package.json`` -> ``"typescript"``
    - ``scripts/`` directory -> ``"python"``
    - ``src/`` directory -> ``"typescript"``
    - default: ``"python"``

    Note: filesystem inference cannot detect ``"none"`` (skills-only)
    correctly — a markdown-only plugin would have been
    misidentified as Python. The metadata path is what fixes the
    #96 reporter's silent-Python-toolchain experience.

    Args:
        plugin_path: Absolute path to the plugin directory

    Returns:
        ``"python"``, ``"typescript"``, or ``"none"``
    """
    metadata_path = (
        plugin_path / ".claude-plugin" / "aida-scaffold.json"
    )
    if metadata_path.exists():
        try:
            data = json.loads(
                metadata_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict):
            recorded = data.get("language")
            if recorded in ("python", "typescript", "none"):
                return recorded

    if (plugin_path / "pyproject.toml").exists():
        return "python"
    if (plugin_path / "package.json").exists():
        return "typescript"
    if (plugin_path / "scripts").is_dir():
        return "python"
    if (plugin_path / "src").is_dir():
        return "typescript"
    return "python"


def _build_scan_context(
    plugin_path: Path,
    metadata: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    """Build a context dict from existing plugin metadata.

    Extracts values from plugin.json and supplements with
    git config for fields not stored in the manifest (e.g.
    author_email).

    Args:
        plugin_path: Absolute path to the plugin directory
        metadata: Parsed plugin.json dictionary
        language: Detected language string

    Returns:
        Context dict suitable for build_template_variables()
    """
    # Import here to avoid circular dependency at module
    # level; scaffold_ops.context is a sibling subpackage.
    from ..scaffold_ops.context import infer_git_config

    git_config = infer_git_config()

    # plugin.json stores author as an object or a string
    author_field = metadata.get("author", "")
    if isinstance(author_field, dict):
        author_name = author_field.get("name", "")
        author_email = author_field.get("email", "")
    else:
        author_name = str(author_field)
        author_email = ""

    # Fall back to git config when metadata is incomplete
    if not author_name:
        author_name = git_config.get("author_name", "")
    if not author_email:
        author_email = git_config.get("author_email", "")

    keywords = metadata.get("keywords", [])

    return {
        "plugin_name": metadata.get("name", "unknown"),
        "description": metadata.get("description", ""),
        "version": metadata.get("version", "0.1.0"),
        "author_name": author_name,
        "author_email": author_email,
        "license_id": metadata.get("license", "MIT"),
        "language": language,
        "keywords": keywords,
        "repository_url": metadata.get("repository", ""),
    }


def _resolve_license_text(
    context: dict[str, Any],
) -> str:
    """Resolve the full license text for template rendering.

    Args:
        context: Scan context dictionary

    Returns:
        Rendered license body text
    """
    from ..scaffold_ops.licenses import get_license_text

    year = str(datetime.now(timezone.utc).year)
    author = context.get("author_name", "")
    license_id = context.get("license_id", "MIT")

    try:
        return get_license_text(license_id, year, author)
    except ValueError:
        logger.warning(
            "Unsupported license '%s', falling back to MIT",
            license_id,
        )
        return get_license_text("MIT", year, author)


def _compare_file(
    plugin_path: Path,
    spec: FileSpec,
    variables: dict[str, Any],
    templates_dir: Path,
) -> FileDiff:
    """Compare a single file against its template.

    Routes to specialised handlers for COMPOSITE files and
    returns early for CUSTOM / SKIP files.

    Args:
        plugin_path: Absolute path to the plugin directory
        spec: File specification from the strategy registry
        variables: Rendered template variables
        templates_dir: Path to scaffold templates directory

    Returns:
        FileDiff describing the comparison result
    """
    # Custom and metadata files with SKIP strategy are never
    # compared; they belong to the plugin author.
    if (
        spec.category
        in (FileCategory.CUSTOM, FileCategory.METADATA)
        or spec.default_strategy == MergeStrategy.SKIP
    ):
        return FileDiff(
            path=spec.path,
            category=spec.category,
            status=FileStatus.CUSTOM_SKIP,
            strategy=MergeStrategy.SKIP,
        )

    # Composite files need special merge-aware comparison
    if spec.category == FileCategory.COMPOSITE:
        if spec.path == ".gitignore":
            return _compare_gitignore(
                plugin_path, variables, templates_dir
            )
        if spec.path == "Makefile":
            return _compare_makefile(
                plugin_path, variables, templates_dir
            )
        # Unknown composite -- treat as manual review
        return FileDiff(
            path=spec.path,
            category=spec.category,
            status=FileStatus.OUTDATED,
            strategy=MergeStrategy.MANUAL_REVIEW,
            diff_summary="Unknown composite file",
        )

    # Dependency configs: presence-only check
    if spec.category == FileCategory.DEPENDENCY_CONFIG:
        actual_path = plugin_path / spec.path
        status = (
            FileStatus.UP_TO_DATE
            if actual_path.exists()
            else FileStatus.MISSING
        )
        return FileDiff(
            path=spec.path,
            category=spec.category,
            status=status,
            strategy=MergeStrategy.MANUAL_REVIEW,
            diff_summary=(
                ""
                if status == FileStatus.UP_TO_DATE
                else "File does not exist"
            ),
        )

    # Regular template-backed files
    return _compare_templated_file(
        plugin_path, spec, variables, templates_dir
    )


def _compare_templated_file(
    plugin_path: Path,
    spec: FileSpec,
    variables: dict[str, Any],
    templates_dir: Path,
) -> FileDiff:
    """Compare a regular template-backed file.

    Renders the template and compares byte-for-byte against
    the file on disk.

    Args:
        plugin_path: Absolute path to the plugin directory
        spec: File specification with a non-None template
        variables: Rendered template variables
        templates_dir: Path to scaffold templates directory

    Returns:
        FileDiff with status MISSING, OUTDATED,
        or UP_TO_DATE
    """
    actual_path = plugin_path / spec.path

    if spec.template is None:
        # No template to compare against; skip quietly
        return FileDiff(
            path=spec.path,
            category=spec.category,
            status=FileStatus.CUSTOM_SKIP,
            strategy=MergeStrategy.SKIP,
        )

    expected = render_template(
        templates_dir, spec.template, variables
    )

    if not actual_path.exists():
        return FileDiff(
            path=spec.path,
            category=spec.category,
            status=FileStatus.MISSING,
            strategy=spec.default_strategy,
            expected_content=expected,
            diff_summary="File does not exist",
        )

    actual = actual_path.read_text()

    if actual == expected:
        return FileDiff(
            path=spec.path,
            category=spec.category,
            status=FileStatus.UP_TO_DATE,
            strategy=spec.default_strategy,
            expected_content=expected,
            actual_content=actual,
        )

    return FileDiff(
        path=spec.path,
        category=spec.category,
        status=FileStatus.OUTDATED,
        strategy=spec.default_strategy,
        expected_content=expected,
        actual_content=actual,
        diff_summary="Content differs from template",
    )


def _render_composite_gitignore(
    variables: dict[str, Any],
    templates_dir: Path,
) -> str:
    """Render the expected .gitignore from template fragments.

    Concatenates the shared and language-specific gitignore
    templates, matching the logic in
    scaffold_ops.generators.assemble_gitignore.

    Args:
        variables: Template variables (language key used)
        templates_dir: Path to scaffold templates directory

    Returns:
        Expected .gitignore content as a single string
    """
    language = variables.get("language", "python")

    shared = render_template(
        templates_dir,
        "shared/gitignore-shared.jinja2",
        {},
    )

    if language == "python":
        lang_part = render_template(
            templates_dir,
            "python/gitignore-python.jinja2",
            {},
        )
    else:
        lang_part = render_template(
            templates_dir,
            "typescript/gitignore-node.jinja2",
            {},
        )

    return "\n".join([shared, lang_part])


def _compare_gitignore(
    plugin_path: Path,
    variables: dict[str, Any],
    templates_dir: Path,
) -> FileDiff:
    """Compare .gitignore against expected template output.

    Uses set-based comparison of active entries rather than
    exact string matching so that ordering differences and
    user additions do not trigger false positives.

    Args:
        plugin_path: Absolute path to the plugin directory
        variables: Rendered template variables
        templates_dir: Path to scaffold templates directory

    Returns:
        FileDiff for .gitignore
    """
    expected_content = _render_composite_gitignore(
        variables, templates_dir
    )
    actual_path = plugin_path / ".gitignore"

    if not actual_path.exists():
        return FileDiff(
            path=".gitignore",
            category=FileCategory.COMPOSITE,
            status=FileStatus.MISSING,
            strategy=MergeStrategy.MERGE,
            expected_content=expected_content,
            diff_summary="File does not exist",
        )

    actual_content = actual_path.read_text()
    expected_entries = parse_gitignore_entries(
        expected_content
    )
    actual_entries = parse_gitignore_entries(
        actual_content
    )

    missing = expected_entries - actual_entries

    if not missing:
        return FileDiff(
            path=".gitignore",
            category=FileCategory.COMPOSITE,
            status=FileStatus.UP_TO_DATE,
            strategy=MergeStrategy.MERGE,
            expected_content=expected_content,
            actual_content=actual_content,
        )

    sorted_missing = sorted(missing)
    summary = (
        f"Missing {len(sorted_missing)} entries: "
        + ", ".join(sorted_missing[:10])
    )
    if len(sorted_missing) > 10:
        summary += f" (and {len(sorted_missing) - 10} more)"

    return FileDiff(
        path=".gitignore",
        category=FileCategory.COMPOSITE,
        status=FileStatus.OUTDATED,
        strategy=MergeStrategy.MERGE,
        expected_content=expected_content,
        actual_content=actual_content,
        diff_summary=summary,
    )


def _render_composite_makefile(
    variables: dict[str, Any],
    templates_dir: Path,
) -> str:
    """Render the expected Makefile from template fragments.

    Concatenates the header and language-specific target
    templates, matching the logic in
    scaffold_ops.generators.assemble_makefile.

    Args:
        variables: Template variables
        templates_dir: Path to scaffold templates directory

    Returns:
        Expected Makefile content as a single string
    """
    language = variables.get("language", "python")

    header = render_template(
        templates_dir,
        "shared/makefile-header.jinja2",
        variables,
    )

    if language == "python":
        lang_targets = render_template(
            templates_dir,
            "python/makefile-python.jinja2",
            variables,
        )
    else:
        lang_targets = render_template(
            templates_dir,
            "typescript/makefile-typescript.jinja2",
            variables,
        )

    return "\n".join([header, lang_targets])


def _compare_makefile(
    plugin_path: Path,
    variables: dict[str, Any],
    templates_dir: Path,
) -> FileDiff:
    """Compare Makefile against expected template output.

    Uses target-name comparison rather than exact string
    matching so that custom additions or formatting changes
    do not trigger false positives.

    Args:
        plugin_path: Absolute path to the plugin directory
        variables: Rendered template variables
        templates_dir: Path to scaffold templates directory

    Returns:
        FileDiff for Makefile
    """
    expected_content = _render_composite_makefile(
        variables, templates_dir
    )
    actual_path = plugin_path / "Makefile"

    if not actual_path.exists():
        return FileDiff(
            path="Makefile",
            category=FileCategory.COMPOSITE,
            status=FileStatus.MISSING,
            strategy=MergeStrategy.MERGE,
            expected_content=expected_content,
            diff_summary="File does not exist",
        )

    actual_content = actual_path.read_text()
    expected_targets = extract_makefile_targets(
        expected_content
    )
    actual_targets = extract_makefile_targets(
        actual_content
    )

    missing = expected_targets - actual_targets

    if not missing:
        return FileDiff(
            path="Makefile",
            category=FileCategory.COMPOSITE,
            status=FileStatus.UP_TO_DATE,
            strategy=MergeStrategy.MERGE,
            expected_content=expected_content,
            actual_content=actual_content,
        )

    sorted_missing = sorted(missing)
    summary = (
        f"Missing {len(sorted_missing)} targets: "
        + ", ".join(sorted_missing[:10])
    )
    if len(sorted_missing) > 10:
        summary += (
            f" (and {len(sorted_missing) - 10} more)"
        )

    return FileDiff(
        path="Makefile",
        category=FileCategory.COMPOSITE,
        status=FileStatus.OUTDATED,
        strategy=MergeStrategy.MERGE,
        expected_content=expected_content,
        actual_content=actual_content,
        diff_summary=summary,
    )
