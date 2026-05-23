#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""AIDA Global Installation Script - Fact-Based Two-Phase API

This script provides a two-phase fact-based installation API for global
AIDA setup. Global installation is completely automatic with NO user questions.

Phase 1: get_questions(context)
    - Detects environment facts (OS, tools, git config, paths)
    - Returns detected environment data
    - Returns empty questions list (global install asks nothing)

Phase 2: install(responses, inferred)
    - Receives detected environment facts
    - Creates ~/.claude/ directory structure
    - Writes aida.yml marker and user-context skill
    - Returns success status

Usage:
    # Phase 1: Detect environment (returns no questions)
    python install.py --get-questions --context='{"project_root": "/path"}'

    # Phase 2: Install with detected facts
    python install.py --install --responses='{}' \\
                                --inferred='{environment facts}'

Exit codes:
    0   - Success
    1   - Error occurred
"""

import sys
import json
import argparse
import tempfile
import os
import logging
import traceback
import platform
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone

import _paths  # noqa: F401

# Import utilities from the foundation module
from utils import (
    check_python_version,
    get_claude_dir,
    ensure_directory,
    read_json,
    write_json,
    file_exists,
    infer_preferences,
    safe_json_load,
    render_skill_directory,
    InstallationError,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Constants
AIDA_VERSION = "0.7.0"
AIDA_MARKER_FILE = "aida.yml"
USER_CONTEXT_SKILL_DIR = "skills/user-context"
SETTINGS_FILE = "settings.json"

# Get script directory for relative path resolution
SCRIPT_DIR = Path(__file__).parent
USER_CONTEXT_TEMPLATE = SCRIPT_DIR.parent / "templates" / "blueprints" / "user-context"

# Note: JSON safety limits and safe_json_load() now imported from utils.json_utils


def atomic_write(filepath: Path, content: str) -> None:
    """Write file atomically to prevent corruption.

    Uses a temporary file and atomic rename to ensure the target file
    is never left in a partially written state.

    Args:
        filepath: Destination file path
        content: Content to write

    Raises:
        IOError: If write operation fails

    Security:
        - Prevents race conditions during concurrent writes
        - Ensures file is never partially written
        - Uses atomic os.replace() on POSIX systems
    """
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


def detect_environment() -> Dict[str, Any]:
    """Detect comprehensive environment information.

    Detects facts that would be useful for Claude to know:
    - System information (OS, architecture, shell)
    - User information (username, name, email from git)
    - Tool locations and versions
    - Version managers
    - Common paths

    Returns:
        Dictionary of detected environment facts
    """
    env = {}

    # System information
    env['os_type'] = platform.system()  # Darwin, Linux, Windows
    env['os_version'] = platform.release()
    env['architecture'] = platform.machine()  # arm64, x86_64
    env['hostname'] = platform.node()

    # User information
    env['username'] = os.getenv('USER') or os.getenv('USERNAME') or 'unknown'
    env['home_directory'] = str(Path.home())

    # Shell detection
    shell = os.getenv('SHELL', '')
    if shell:
        env['shell'] = Path(shell).name  # bash, zsh, fish
    else:
        env['shell'] = 'unknown'

    # Git configuration
    try:
        result = subprocess.run(['git', 'config', '--global', 'user.name'],
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            env['git_user_name'] = result.stdout.strip()
    except Exception:
        pass

    try:
        result = subprocess.run(['git', 'config', '--global', 'user.email'],
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            env['git_user_email'] = result.stdout.strip()
    except Exception:
        pass

    # Try to extract GitHub username from git remotes
    try:
        result = subprocess.run(['git', 'config', '--global', '--get-regexp', 'remote.*.url'],
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            # Parse for github.com URLs
            for line in result.stdout.split('\n'):
                if 'github.com' in line:
                    # Extract username from git@github.com:username/repo or https://github.com/username/repo
                    if 'git@github.com:' in line:
                        parts = line.split('git@github.com:')[1].split('/')[0]
                        env['github_username'] = parts
                        break
                    elif 'https://github.com/' in line:
                        parts = line.split('https://github.com/')[1].split('/')[0]
                        env['github_username'] = parts
                        break
    except Exception:
        pass

    # Tool detection - check what's available
    tools = {}

    # Python
    python_path = shutil.which('python3') or shutil.which('python')
    if python_path:
        tools['python'] = python_path
        try:
            result = subprocess.run([python_path, '--version'],
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                tools['python_version'] = result.stdout.strip() or result.stderr.strip()
        except Exception:
            pass

    # Git
    git_path = shutil.which('git')
    if git_path:
        tools['git'] = git_path
        try:
            result = subprocess.run(['git', '--version'],
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                tools['git_version'] = result.stdout.strip()
        except Exception:
            pass

    # Node
    node_path = shutil.which('node')
    if node_path:
        tools['node'] = node_path
        try:
            result = subprocess.run(['node', '--version'],
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                tools['node_version'] = result.stdout.strip()
        except Exception:
            pass

    # Docker
    docker_path = shutil.which('docker')
    if docker_path:
        tools['docker'] = docker_path

    env['tools'] = tools

    # Version managers detection
    version_managers = {}

    pyenv_root = Path.home() / '.pyenv'
    if pyenv_root.exists():
        version_managers['pyenv'] = str(pyenv_root)

    nvm_root = Path.home() / '.nvm'
    if nvm_root.exists():
        version_managers['nvm'] = str(nvm_root)

    rbenv_root = Path.home() / '.rbenv'
    if rbenv_root.exists():
        version_managers['rbenv'] = str(rbenv_root)

    env['version_managers'] = version_managers

    # Common paths
    paths = {
        'home': env['home_directory'],
        'ssh_keys': str(Path.home() / '.ssh'),
        'config': str(Path.home() / '.config'),
    }

    # Try to detect projects directory
    common_project_dirs = ['Developer', 'Code', 'Projects', 'workspace', 'dev', 'src']
    for dirname in common_project_dirs:
        project_dir = Path.home() / dirname
        if project_dir.exists() and project_dir.is_dir():
            paths['projects'] = str(project_dir)
            break

    env['paths'] = paths

    return env


def render_aida_marker(detected_data: Dict[str, Any]) -> str:
    """Render aida.yml marker file content.

    This file serves as:
    1. Marker that AIDA is installed
    2. Version tracking
    3. Plugin list
    4. Installation metadata
    5. Skill update timestamps

    NOTE: User context facts are stored in ~/.claude/skills/user-context/SKILL.md
    This file contains ONLY metadata and timestamps.

    Args:
        detected_data: Detected environment data (unused, kept for signature compatibility)

    Returns:
        Rendered aida.yml content in YAML format (metadata only)
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Extract relevant metadata
    plugins = ["aida-core"]

    # Build YAML content (metadata only - NO preferences).
    # Leading `---` is required for yamllint's default `document-start`
    # rule, which the scaffolder enforces in every plugin we generate.
    content = f"""---
# AIDA Installation Marker
# This file indicates AIDA is installed and tracks metadata
# User preferences are stored in ~/.claude/skills/user-context/SKILL.md
version: "{AIDA_VERSION}"
installed: "{timestamp}"
last_updated: "{timestamp}"

plugins:
"""

    for plugin in plugins:
        content += f"  - {plugin}\n"

    # Track when skills were last updated
    content += "\nskills:\n"
    content += "  user-context:\n"
    content += f"    last_updated: \"{timestamp}\"\n"

    return content


def get_questions(context: Dict[str, Any]) -> Dict[str, Any]:
    """Detect environment facts for global installation (Phase 1).

    Global installation is fully fact-based with NO user questions.
    This function:
    1. Detects user's environment facts (OS, tools, git config, etc.)
    2. Returns detected facts ready for installation
    3. Always returns empty questions list (global install asks nothing)

    Args:
        context: Project context dictionary containing:
            - project_root: Path to project root (optional, defaults to cwd)
            - is_update: Whether this is updating existing installation

    Returns:
        Dictionary containing:
            {
                "questions": [],        # Always empty for global install
                "inferred": {...},      # Auto-detected environment facts
            }

    Example:
        >>> context = {"project_root": "/path/to/project"}
        >>> result = get_questions(context)
        >>> # Returns: {"questions": [], "inferred": {environment facts}}
    """
    # Detect environment facts (OS, tools, git config, paths, etc.)
    environment = detect_environment()

    # Analyze project context for additional facts
    inferred = infer_preferences(context)

    # Merge environment facts into inferred data
    inferred['environment'] = environment

    # Global install is fact-based only - no questions
    return {
        "questions": [],
        "inferred": inferred,
    }


def install(responses: Dict[str, Any], inferred: Dict[str, Any] = None) -> Dict[str, Any]:
    """Write AIDA configuration files from responses (Phase 2).

    This function:
    1. Combines user responses with inferred data
    2. Creates skill directories
    3. Renders skill files from templates
    4. Updates settings.json

    Args:
        responses: User answers to questions (currently unused - reserved for future)
        inferred: Auto-detected environment facts (contains 'environment' key)

    Returns:
        Dictionary containing:
            {
                "success": True/False,
                "files_created": [...],
                "message": "..."
            }

    Raises:
        InstallationError: If installation fails

    Example:
        >>> responses = {}  # No responses needed - all auto-detected
        >>> inferred = {"environment": {"os_type": "Darwin", "tools": {...}}}
        >>> result = install(responses, inferred)
        >>> # Creates user-context skill with detected environment facts
    """
    # Combine responses (if any) with auto-detected environment data
    detected_environment = {**(inferred or {}), **responses}

    files_created = []

    try:
        # Check Python version
        check_python_version()

        claude_dir = get_claude_dir()

        # Create user-context skill directory
        user_context_dir = claude_dir / USER_CONTEXT_SKILL_DIR
        ensure_directory(user_context_dir)
        files_created.append(str(user_context_dir))

        # Verify template exists
        if not USER_CONTEXT_TEMPLATE.exists():
            raise InstallationError(
                f"User context template not found: {USER_CONTEXT_TEMPLATE}",
                "This is a bug - please report it"
            )

        # Render user context skill from Jinja2 template
        # This skill contains ONLY environment facts (OS, tools, paths, git config, etc.)
        logger.info(f"Rendering user-context skill to {user_context_dir}")
        template_vars = map_environment_to_template_vars(detected_environment)
        render_skill_directory(USER_CONTEXT_TEMPLATE, user_context_dir, template_vars)
        files_created.append(str(user_context_dir / "SKILL.md"))

        # Create AIDA marker file (atomic write)
        aida_marker_file = claude_dir / AIDA_MARKER_FILE
        aida_marker_content = render_aida_marker(detected_environment)
        atomic_write(aida_marker_file, aida_marker_content)
        files_created.append(str(aida_marker_file))

        # Update settings.json
        settings_file = claude_dir / SETTINGS_FILE
        if file_exists(settings_file):
            current_settings = read_json(settings_file)
        else:
            current_settings = {}

        if "enabledPlugins" not in current_settings:
            current_settings["enabledPlugins"] = {}
        current_settings["enabledPlugins"]["aida-core"] = True

        write_json(settings_file, current_settings)
        files_created.append(str(settings_file))

        return {
            "success": True,
            "files_created": files_created,
            "message": "AIDA installation complete! Restart Claude Code to load plugins."
        }

    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        # Log full error with traceback for debugging
        logger.error(f"Installation failed: {e}", exc_info=True)

        return {
            "success": False,
            "files_created": files_created,
            "message": f"Installation failed: {e}",
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }


def map_environment_to_template_vars(detected_data: Dict[str, Any]) -> Dict[str, str]:
    """Map detected environment data to flat template variables.

    Converts nested environment dictionary to flat key-value pairs required
    by Jinja2 template rendering (all values must be strings).

    Args:
        detected_data: Auto-detected environment data from detect_environment()

    Returns:
        Dictionary of template variables (all string values)
    """
    env = detected_data.get('environment', {})
    tools = env.get('tools', {})
    paths = env.get('paths', {})

    # Map to flat template variables (all strings for template validator)
    template_vars = {
        # Quick Reference
        'git_user_name': str(env.get('git_user_name', 'Not configured')),
        'git_user_email': str(env.get('git_user_email', 'Not configured')),
        'github_username': str(env.get('github_username', 'Not detected')),
        'projects_directory': str(paths.get('projects', 'Not detected')),
        'username': str(env.get('username', 'unknown')),
        'home_directory': str(env.get('home_directory', '~')),

        # System Environment
        'os_type': str(env.get('os_type', 'Unknown')),
        'os_version': str(env.get('os_version', '')),
        'architecture': str(env.get('architecture', '')),
        'shell': str(env.get('shell', 'unknown')),
        'hostname': str(env.get('hostname', 'unknown')),

        # Tools (individual paths and versions)
        'python_path': str(tools.get('python', '')) if 'python' in tools else '',
        'python_version': str(tools.get('python_version', '')),
        'git_path': str(tools.get('git', '')) if 'git' in tools else '',
        'git_version': str(tools.get('git_version', '')),
        'node_path': str(tools.get('node', '')) if 'node' in tools else '',
        'node_version': str(tools.get('node_version', '')),
        'docker_path': str(tools.get('docker', '')) if 'docker' in tools else '',

        # Paths
        'ssh_keys_path': str(paths.get('ssh_keys', '~/.ssh')),
        'config_path': str(paths.get('config', '~/.config')),

        # Timestamp
        'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
    }

    # Note: version_managers omitted - template will show "No version managers detected"
    # To support this properly, we'd need to flatten the dict or update template validator

    return template_vars




def main() -> int:
    """Main CLI entry point with two-phase API.

    Returns:
        Exit code (0 = success, 1 = error)
    """
    parser = argparse.ArgumentParser(
        description="AIDA Installation - Two-Phase API"
    )

    parser.add_argument(
        "--get-questions",
        action="store_true",
        help="Phase 1: Analyze context and return questions (outputs JSON)"
    )

    parser.add_argument(
        "--install",
        action="store_true",
        help="Phase 2: Install AIDA with provided responses (outputs JSON)"
    )

    parser.add_argument(
        "--context",
        type=str,
        help="JSON string containing project context for Phase 1"
    )

    parser.add_argument(
        "--responses",
        type=str,
        help="JSON string containing user responses for Phase 2"
    )

    parser.add_argument(
        "--inferred",
        type=str,
        help="JSON string containing inferred data for Phase 2"
    )

    args = parser.parse_args()

    try:
        # Phase 1: Get Questions
        if args.get_questions:
            context = safe_json_load(args.context) if args.context else {}
            result = get_questions(context)
            print(json.dumps(result, indent=2))
            return 0

        # Phase 2: Install
        elif args.install:
            if not args.responses:
                print(json.dumps({
                    "success": False,
                    "message": "--responses required for --install"
                }))
                return 1

            responses = safe_json_load(args.responses)
            inferred = safe_json_load(args.inferred) if args.inferred else {}

            result = install(responses, inferred)
            print(json.dumps(result, indent=2))

            return 0 if result["success"] else 1

        else:
            parser.print_help()
            return 1

    except ValueError as e:
        # Handles both JSON decode errors and validation errors from safe_json_load
        logger.error(f"JSON validation error: {e}")
        print(json.dumps({
            "success": False,
            "message": f"JSON validation error: {e}"
        }))
        return 1

    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        # Log unexpected errors with full traceback
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(json.dumps({
            "success": False,
            "message": f"Error: {e}",
            "error_type": type(e).__name__
        }))
        return 1


if __name__ == "__main__":
    sys.exit(main())
