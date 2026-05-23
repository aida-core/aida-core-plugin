# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""AIDA Utilities - Foundation module for AIDA installation scripts.

This package provides common utilities for version checking, path resolution,
error handling, file operations, and template rendering used across all AIDA M1 scripts.

Example:
    >>> from utils import check_python_version, get_claude_dir, read_json, render_skill_directory
    >>> check_python_version()  # Raises VersionError if Python < 3.8
    >>> claude_dir = get_claude_dir()  # Returns Path("~/.claude")
    >>> config = read_json(claude_dir / "config.json")
    >>> render_skill_directory(template_dir, output_dir, variables)
"""

# Cross-package path setup must run before any `from shared.*` import.
# The dep-management helpers (#20) live in `scripts/shared/` so they
# can be reused by plugin-manager too — adding `scripts/` to sys.path
# here lets `from shared.dependencies import ...` resolve in the
# re-export block below without forcing each caller to do the setup.
import sys as _sys
from pathlib import Path as _Path

_SHARED_ROOT = (
    _Path(__file__).parent.parent.parent.parent.parent / "scripts"
)
if str(_SHARED_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_SHARED_ROOT))

# Version checking
from .version import (
    check_python_version,
    get_python_version,
    is_compatible_version,
    format_version,
    MIN_PYTHON_VERSION,
)

# Path resolution
from .paths import (
    get_home_dir,
    get_claude_dir,
    get_aida_skills_dir,
    get_aida_plugin_dirs,
    ensure_directory,
    resolve_path,
    is_subdirectory,
    get_relative_path,
)

# JSON utilities
from .json_utils import (
    safe_json_load,
    MAX_JSON_SIZE,
    MAX_JSON_DEPTH,
)

# File operations
from .files import (
    read_file,
    write_file,
    read_json,
    write_json,
    write_yaml,
    update_json,
    copy_template,
    file_exists,
    directory_exists,
    atomic_write,
)

# Questionnaire system
from .questionnaire import (
    run_questionnaire,  # Keep for backwards compatibility / standalone use
    load_questionnaire,
    filter_questions,
    questions_to_dict,
)

# Inference system
from .inference import (
    infer_preferences,
    detect_languages,
    detect_tools,
    detect_coding_standards,
    detect_testing_approach,
    detect_project_type,
)

# Plugin discovery
from .plugins import (
    discover_installed_plugins,
    get_plugins_with_config,
    validate_plugin_config,
    generate_plugin_checklist,
    generate_plugin_preference_questions,
)

# Plugin dependency management (#20). Pure helpers live in
# scripts/shared/dependencies.py so plugin-manager (which has its
# own `utils` namespace) can import them without cross-skill
# acrobatics. Re-exported here so existing `from utils import ...`
# call sites still resolve.
from shared.dependencies import (
    check_dependencies,
    parse_version_spec,
    version_satisfies,
)

# Agent discovery
from .agents import (
    discover_agents,
    generate_agent_routing_section,
    update_agent_routing,
)

# Template rendering
from .template_renderer import (
    render_template,
    render_filename,
    render_skill_directory,
    is_binary_file,
    is_template_file,
    get_output_filename,
)

# Project context (split / merge of aida-project-context.yml and .local.yml)
from .project_context import (
    PROJECT_CONTEXT_FILE,
    PROJECT_CONTEXT_LOCAL_FILE,
    split_context,
    merge_context,
    load_project_context,
    write_project_context,
    ensure_gitignore_entry,
)

# Error classes
from .errors import (
    AidaError,
    VersionError,
    PathError,
    FileOperationError,
    ConfigurationError,
    InstallationError,
)

__version__ = "0.1.0"

__all__ = [
    # Version checking
    "check_python_version",
    "get_python_version",
    "is_compatible_version",
    "format_version",
    "MIN_PYTHON_VERSION",
    # Path resolution
    "get_home_dir",
    "get_claude_dir",
    "get_aida_skills_dir",
    "get_aida_plugin_dirs",
    "ensure_directory",
    "resolve_path",
    "is_subdirectory",
    "get_relative_path",
    # JSON utilities
    "safe_json_load",
    "MAX_JSON_SIZE",
    "MAX_JSON_DEPTH",
    # File operations
    "read_file",
    "write_file",
    "read_json",
    "write_json",
    "write_yaml",
    "update_json",
    "copy_template",
    "file_exists",
    "directory_exists",
    "atomic_write",
    # Questionnaire system
    "run_questionnaire",
    "load_questionnaire",
    "filter_questions",
    "questions_to_dict",
    # Inference system
    "infer_preferences",
    "detect_languages",
    "detect_tools",
    "detect_coding_standards",
    "detect_testing_approach",
    "detect_project_type",
    # Plugin discovery
    "discover_installed_plugins",
    "get_plugins_with_config",
    "validate_plugin_config",
    "generate_plugin_checklist",
    "generate_plugin_preference_questions",
    # Plugin dependency management (#20)
    "check_dependencies",
    "parse_version_spec",
    "version_satisfies",
    # Agent discovery
    "discover_agents",
    "generate_agent_routing_section",
    "update_agent_routing",
    # Template rendering
    "render_template",
    "render_filename",
    "render_skill_directory",
    "is_binary_file",
    "is_template_file",
    "get_output_filename",
    # Project context split/merge
    "PROJECT_CONTEXT_FILE",
    "PROJECT_CONTEXT_LOCAL_FILE",
    "split_context",
    "merge_context",
    "load_project_context",
    "write_project_context",
    "ensure_gitignore_entry",
    # Error classes
    "AidaError",
    "VersionError",
    "PathError",
    "FileOperationError",
    "ConfigurationError",
    "InstallationError",
]
