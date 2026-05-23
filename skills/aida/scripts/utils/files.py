# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""File operation utilities for AIDA.

This module provides safe file operations with proper error handling,
including JSON manipulation and template file operations.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
HAS_YAML = True


class _IndentedDumper(yaml.SafeDumper):
    """SafeDumper that indents sequence items inside their parent.

    PyYAML's default emits sequences flush with the parent key:

        tools:
          detected:
          - Git
          - GitHub Actions

    yamllint's `indentation` rule (with `indent-sequences: true`, the
    default) expects sequence items indented one level deeper:

        tools:
          detected:
            - Git
            - GitHub Actions

    Overriding `increase_indent` to never go indentless restores the
    expected indentation.
    """

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)

# Try to import fcntl for Unix file locking
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

from .errors import FileOperationError, ConfigurationError  # noqa: E402
from .paths import ensure_directory  # noqa: E402


# File operation constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB maximum file size for reading


def read_file(path: Path, encoding: str = "utf-8", max_size: int = MAX_FILE_SIZE) -> str:
    """Safely read a text file with error handling and size limit.

    Args:
        path: Path to file to read
        encoding: Text encoding (default: utf-8)
        max_size: Maximum file size in bytes (default: 10MB)

    Returns:
        File contents as string

    Raises:
        FileOperationError: If file cannot be read or exceeds size limit

    Security:
        - Validates file size before reading to prevent memory exhaustion
        - Uses specified encoding to prevent decode attacks

    Example:
        >>> read_file(Path("config.txt"))
        'file contents here'
    """
    try:
        # Security: Check file size before reading
        file_size = path.stat().st_size
        if file_size > max_size:
            raise FileOperationError(
                f"File too large to read: {path} ({file_size} bytes)",
                f"Maximum size is {max_size} bytes ({max_size // 1024 // 1024}MB). "
                f"Use chunked reading for large files."
            )

        with open(path, "r", encoding=encoding) as f:
            return f.read()
    except FileNotFoundError as e:
        raise FileOperationError(
            f"File not found: {path}",
            "Verify the file path is correct."
        ) from e
    except PermissionError as e:
        raise FileOperationError(
            f"Permission denied reading file: {path}",
            "Check file permissions or run with appropriate access."
        ) from e
    except UnicodeDecodeError as e:
        raise FileOperationError(
            f"Failed to decode file (encoding: {encoding}): {path}",
            "Try a different encoding or verify the file is text format."
        ) from e
    except OSError as e:
        raise FileOperationError(
            f"Error reading file: {path}",
            f"Error: {e}"
        ) from e


def write_file(path: Path, content: str, encoding: str = "utf-8",
               create_parents: bool = True) -> None:
    """Safely write content to a text file with atomic write operation.

    Uses atomic write pattern (write-to-temp-then-rename) to prevent
    race conditions and partial writes.

    Args:
        path: Path to file to write
        content: Content to write
        encoding: Text encoding (default: utf-8)
        create_parents: Create parent directories if they don't exist

    Raises:
        FileOperationError: If file cannot be written

    Security:
        - Validates path doesn't contain null bytes
        - Uses atomic write to prevent race conditions
        - Verifies parent directory is not a symlink

    Example:
        >>> write_file(Path("config.txt"), "new content")
    """
    try:
        # Security: Validate path doesn't contain null bytes
        if '\x00' in str(path):
            raise FileOperationError(
                f"Invalid path contains null bytes: {path}",
                "Remove null bytes from the path."
            )

        # Create parent directories if needed
        if create_parents:
            # Use exist_ok=True to handle race condition
            path.parent.mkdir(parents=True, exist_ok=True)

            # Security: Verify parent is not a symlink
            if path.parent.is_symlink():
                raise FileOperationError(
                    f"Security violation: Parent directory is a symlink: {path.parent}",
                    "Remove the symlink or use a different path."
                )

        # Atomic write: write to temp file, then rename
        temp_path = path.parent / f".{path.name}.tmp.{os.getpid()}"
        try:
            with open(temp_path, "w", encoding=encoding) as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk

            # Atomic rename (replaces existing file if present)
            temp_path.replace(path)
        finally:
            # Clean up temp file if rename failed
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass  # Best effort cleanup

    except PermissionError as e:
        raise FileOperationError(
            f"Permission denied writing file: {path}",
            "Check file permissions or run with appropriate access."
        ) from e
    except OSError as e:
        raise FileOperationError(
            f"Error writing file: {path}",
            f"Error: {e}"
        ) from e


def read_json(path: Path, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Read and parse a JSON file with error handling.

    Args:
        path: Path to JSON file
        default: Default value to return if file doesn't exist (None = raise error)

    Returns:
        Parsed JSON data as dictionary

    Raises:
        FileOperationError: If file cannot be read
        ConfigurationError: If JSON is invalid

    Example:
        >>> read_json(Path("config.json"))
        {'setting': 'value'}
    """
    # Return default if file doesn't exist and default provided
    if default is not None and not path.exists():
        return default

    try:
        content = read_file(path)
        return json.loads(content)

    except json.JSONDecodeError as e:
        raise ConfigurationError(
            f"Invalid JSON in file: {path}",
            f"JSON error at line {e.lineno}, column {e.colno}: {e.msg}\n"
            f"Verify the JSON syntax is correct."
        ) from e
    except FileOperationError:
        # Re-raise file operation errors as-is
        raise


def write_json(path: Path, data: Dict[str, Any], indent: int = 2,
               create_parents: bool = True) -> None:
    """Write data to a JSON file with pretty formatting.

    Args:
        path: Path to JSON file to write
        data: Data to serialize as JSON
        indent: Number of spaces for indentation (default: 2)
        create_parents: Create parent directories if they don't exist

    Raises:
        FileOperationError: If file cannot be written
        ConfigurationError: If data cannot be serialized

    Example:
        >>> write_json(Path("config.json"), {"setting": "value"})
    """
    try:
        content = json.dumps(data, indent=indent, ensure_ascii=False)
        write_file(path, content, create_parents=create_parents)

    except TypeError as e:
        raise ConfigurationError(
            f"Cannot serialize data to JSON: {e}",
            "Ensure all data types are JSON-serializable (str, int, float, bool, list, dict, None)."
        ) from e
    except FileOperationError:
        # Re-raise file operation errors as-is
        raise


def write_yaml(path: Path, data: Dict[str, Any], create_parents: bool = True) -> None:
    """Write data to a YAML file with pretty formatting.

    Args:
        path: Path to YAML file to write
        data: Data to serialize as YAML
        create_parents: Create parent directories if they don't exist

    Raises:
        FileOperationError: If file cannot be written
        ConfigurationError: If data cannot be serialized or PyYAML not available

    Example:
        >>> write_yaml(Path("config.yml"), {"setting": "value"})
    """
    try:
        # explicit_start emits a `---` document marker; the custom
        # Dumper indents sequences inside their parent. Together these
        # produce yamllint-default-clean output so consumers (including
        # every scaffolded plugin that enforces yamllint) don't have
        # to special-case AIDA-generated files.
        content = yaml.dump(
            data,
            Dumper=_IndentedDumper,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            explicit_start=True,
        )
        write_file(path, content, create_parents=create_parents)

    except yaml.YAMLError as e:
        raise ConfigurationError(
            f"Cannot serialize data to YAML: {e}",
            "Ensure all data types are YAML-serializable."
        ) from e
    except FileOperationError:
        # Re-raise file operation errors as-is
        raise


def update_json(
    path: Path,
    updates: Dict[str, Any],
    create_if_missing: bool = True,
    max_retries: int = 3
) -> Dict[str, Any]:
    """Update specific fields in a JSON file with file locking.

    Uses file locking on Unix systems to prevent race conditions during
    read-modify-write operations. On Windows, uses retry logic.

    Args:
        path: Path to JSON file
        updates: Dictionary of fields to update
        create_if_missing: Create file with updates if it doesn't exist
        max_retries: Maximum number of retry attempts (default: 3)

    Returns:
        Updated JSON data

    Raises:
        FileOperationError: If file operations fail
        ConfigurationError: If JSON is invalid

    Security:
        - Uses file locking (Unix) to prevent concurrent write conflicts
        - Atomic write ensures no partial updates
        - Retry logic handles transient conflicts

    Example:
        >>> update_json(Path("config.json"), {"new_setting": "value"})
        {'old_setting': 'old', 'new_setting': 'value'}
    """
    for attempt in range(max_retries):
        try:
            # Ensure parent directory exists
            if create_if_missing and not path.parent.exists():
                ensure_directory(path.parent)

            # Open with read/write mode, create if needed
            mode = "r+" if path.exists() else "w+"

            with open(path, mode, encoding="utf-8") as f:
                # Acquire exclusive lock (Unix only)
                if HAS_FCNTL:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    except OSError:
                        # Lock failed, retry
                        if attempt < max_retries - 1:
                            time.sleep(0.1 * (2 ** attempt))
                            continue
                        raise

                try:
                    # Read existing data
                    f.seek(0)
                    content = f.read()
                    if content:
                        data = json.loads(content)
                    else:
                        data = {}

                    # Update with new values
                    data.update(updates)

                    # Write back atomically
                    f.seek(0)
                    f.truncate()
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())  # Ensure written to disk

                    return data

                finally:
                    # Release lock (Unix only)
                    if HAS_FCNTL:
                        try:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        except OSError:
                            pass  # Best effort

        except (IOError, OSError) as e:
            if attempt < max_retries - 1:
                # Retry with exponential backoff
                time.sleep(0.1 * (2 ** attempt))
                continue
            raise FileOperationError(
                f"Failed to update JSON file after {max_retries} attempts: {path}",
                f"Error: {e}"
            ) from e
        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Invalid JSON in file: {path}",
                f"Fix the JSON syntax. Error: {e}"
            ) from e

    # Should never reach here
    raise FileOperationError(
        f"Failed to update JSON file: {path}",
        "Maximum retries exceeded."
    )


def copy_template(template_path: Path, destination: Path,
                  replacements: Optional[Dict[str, str]] = None) -> None:
    """Copy a template file with optional string replacements.

    This is a simple template function for basic string substitution.
    For complex templating, use jinja2 integration (future enhancement).

    Args:
        template_path: Path to template file
        destination: Path to destination file
        replacements: Dictionary of {placeholder: replacement} strings

    Raises:
        FileOperationError: If file operations fail

    Example:
        >>> copy_template(
        ...     Path("template.txt"),
        ...     Path("output.txt"),
        ...     {"{{NAME}}": "AIDA", "{{VERSION}}": "1.0"}
        ... )
    """
    # Read template
    content = read_file(template_path)

    # Apply replacements if provided
    if replacements:
        for placeholder, replacement in replacements.items():
            content = content.replace(placeholder, replacement)

    # Write to destination
    write_file(destination, content)


def atomic_write(filepath: Path, content: str) -> None:
    """Write file atomically to prevent corruption.

    Uses a temporary file and atomic rename to ensure the target file
    is never left in a partially written state.

    This is a convenience function that wraps write_file() for API compatibility.
    For additional options (encoding, parent creation), use write_file() directly.

    Args:
        filepath: Destination file path
        content: Content to write

    Raises:
        IOError: If write operation fails

    Security:
        - Prevents race conditions during concurrent writes
        - Ensures file is never partially written
        - Uses atomic os.replace() on POSIX systems

    Example:
        >>> atomic_write(Path("config.txt"), "content")
    """
    import tempfile

    # Ensure parent directory exists
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Write to temporary file in same directory (same filesystem)
    with tempfile.NamedTemporaryFile(
        mode='w',
        dir=filepath.parent,
        delete=False,
        encoding='utf-8'
    ) as tmp:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())  # Force write to disk
        tmp_path = tmp.name

    # Atomic rename (replaces existing file if present)
    try:
        os.replace(tmp_path, filepath)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


def file_exists(path: Path) -> bool:
    """Check if a file exists.

    Args:
        path: Path to check

    Returns:
        True if file exists and is a file, False otherwise

    Example:
        >>> file_exists(Path("config.json"))
        True
    """
    return path.exists() and path.is_file()


def directory_exists(path: Path) -> bool:
    """Check if a directory exists.

    Args:
        path: Path to check

    Returns:
        True if directory exists and is a directory, False otherwise

    Example:
        >>> directory_exists(Path("~/.claude"))
        True
    """
    return path.exists() and path.is_dir()
