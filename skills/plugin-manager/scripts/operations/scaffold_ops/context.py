# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Context gathering operations for plugin scaffolding.

Functions for inferring git configuration, validating target
directories, and checking tool availability.
"""

import subprocess
from pathlib import Path
from typing import Optional


def is_existing_aida_plugin(target: Path) -> bool:
    """Return True if ``target`` already contains an AIDA plugin.

    A directory is an existing AIDA plugin when it contains
    ``.claude-plugin/plugin.json``. The scaffold wizard treats those
    differently from unrelated non-empty directories — instead of
    failing with "directory not empty", it offers to upgrade the
    plugin via the standards-migration flow (#110).
    """
    marker = target / ".claude-plugin" / "plugin.json"
    return marker.exists() and marker.is_file()


def infer_git_config() -> dict[str, str]:
    """Infer author name and email from git config.

    Returns:
        Dictionary with 'author_name' and 'author_email'
        keys. Values are empty strings if inference fails.
    """
    result: dict[str, str] = {
        "author_name": "",
        "author_email": "",
    }

    try:
        name = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if name.returncode == 0 and name.stdout.strip():
            result["author_name"] = name.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        email = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if (
            email.returncode == 0
            and email.stdout.strip()
        ):
            result["author_email"] = email.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return result


def validate_target_directory(
    path: str,
) -> tuple[bool, Optional[str]]:
    """Validate that the target directory is safe to use.

    The path is resolved (canonicalized) before validation,
    so directory traversal via '..' is inherently neutralized
    by resolve().

    Args:
        path: Target directory path

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not path:
        return (
            False,
            "Target directory path cannot be empty",
        )

    # Reject symlinks
    if Path(path).is_symlink():
        return (
            False,
            f"Target path is a symbolic link: {path}",
        )

    target = Path(path).resolve()

    # Check if directory already exists and is not empty
    if target.exists():
        if target.is_file():
            return (
                False,
                f"Target path is an existing file: "
                f"{target}",
            )
        if any(target.iterdir()):
            # An existing AIDA plugin gets handled separately
            # (the wizard offers to upgrade it); this validator
            # only signals "unrelated non-empty directory".
            if is_existing_aida_plugin(target):
                return (
                    False,
                    f"Target directory already contains an "
                    f"AIDA plugin: {target}",
                )
            return (
                False,
                f"Target directory is not empty: "
                f"{target}",
            )

    # Check if parent directory exists
    parent = target.parent
    if not parent.exists():
        return (
            False,
            f"Parent directory does not exist: {parent}",
        )

    return True, None


def check_gh_available() -> bool:
    """Check if the GitHub CLI (gh) is available.

    Returns:
        True if gh is installed and accessible
    """
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def resolve_default_target(plugin_name: str) -> str:
    """Resolve the default target directory for a new plugin.

    Creates a path at {cwd}/{plugin_name}.

    Args:
        plugin_name: Name of the plugin (kebab-case)

    Returns:
        Absolute path string for the target directory
    """
    return str(Path.cwd() / plugin_name)
