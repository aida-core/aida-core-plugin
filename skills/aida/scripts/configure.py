#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""AIDA Project Configuration Script - Two-Phase API

This script provides a two-phase project configuration API designed for integration
with AIDA skills. Instead of interactive CLI prompts, it:

Phase 1: get_questions(context)
    - Analyzes project context (languages, frameworks, structure)
    - Detects project type, team size, testing approach
    - Infers project preferences automatically
    - Returns filtered list of questions that need user input

Phase 2: configure(responses, inferred)
    - Receives combined responses and inferred data
    - Creates project-specific skills (project-context, project-documentation)
    - Returns success status

This allows AIDA to ask smart questions using AskUserQuestion tool
and handle the configuration orchestration.

Usage:
    # Phase 1: Get questions
    python configure.py --get-questions --context='{"project_root": "/path"}'

    # Phase 2: Configure
    python configure.py --configure --responses='{"project_type": "Web app"}' \\
                                     --inferred='{"languages": "Python, JS"}'

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import _paths  # noqa: F401

# Import utilities from the foundation module
from utils import (
    get_claude_dir,
    ensure_directory,
    load_questionnaire,
    detect_languages,
    detect_tools,
    detect_project_type,
    detect_testing_approach,
    render_skill_directory,
    safe_json_load,
    load_project_context,
    write_project_context,
    ensure_gitignore_entry,
    FileOperationError,
    ConfigurationError,
    InstallationError,
)

import yaml
HAS_YAML = True

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Constants
def _read_plugin_version() -> str:
    """Read version from plugin.json."""
    plugin_json = Path(__file__).parent.parent.parent.parent / ".claude-plugin" / "plugin.json"
    try:
        data = json.loads(plugin_json.read_text(encoding="utf-8"))
        return data.get("version", "0.0.0")
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return "0.0.0"


AIDA_VERSION = _read_plugin_version()
AIDA_MARKER_FILE = "aida.yml"
PROJECT_CONTEXT_FILE = "aida-project-context.yml"
PROJECT_CONTEXT_SKILL_DIR = "skills/project-context"
PROJECT_DOCUMENTATION_SKILL_DIR = "skills/project-documentation"
USER_CONTEXT_SKILL_DIR = "skills/user-context"

# Get path to questionnaire template (relative to this script)
SCRIPT_DIR = Path(__file__).parent
CONFIGURE_QUESTIONNAIRE = SCRIPT_DIR.parent / "templates" / "questionnaires" / "configure.yml"
PROJECT_CONTEXT_TEMPLATE = SCRIPT_DIR.parent / "templates" / "blueprints" / "project-context"
PROJECT_DOCUMENTATION_TEMPLATE = SCRIPT_DIR.parent / "templates" / "blueprints" / "project-documentation"

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
    except OSError:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            # Best-effort cleanup on failure
            pass
        raise


def render_aida_project_marker(preferences: Dict[str, Any], project_name: str) -> str:
    """Render aida.yml project marker file content.

    This file serves as:
    1. Marker that AIDA is configured for this project
    2. Version tracking
    3. Plugin list
    4. Project metadata

    Args:
        preferences: Combined user responses and inferred data
        project_name: Name of the project

    Returns:
        Rendered aida.yml content in YAML format
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Plugins enabled for this project. Starts empty — projects add
    # entries via /aida config (plugins selection) or by editing the
    # file directly. Previously hardcoded to "aida-workflow-commands",
    # which doesn't exist as a plugin and produced a dead reference
    # in every generated aida.yml (#83).
    plugins: List[str] = []

    # Build configuration section from preferences
    config = {}
    if "project_type" in preferences:
        config["project_type"] = preferences["project_type"]
    if "team_collaboration" in preferences:
        config["team_collaboration"] = preferences["team_collaboration"]
    if "testing_approach" in preferences:
        config["testing_approach"] = preferences["testing_approach"]
    if "documentation_level" in preferences:
        config["documentation_level"] = preferences["documentation_level"]

    # Build YAML content. Leading `---` is required for yamllint's
    # default `document-start` rule (which the scaffolder enforces in
    # every plugin we generate).
    content = f"""---
# AIDA Project Configuration Marker
# This file indicates AIDA is configured for this project
version: "{AIDA_VERSION}"
configured: "{timestamp}"

project:
  name: "{project_name}"
"""

    if "project_type" in config:
        content += f"  type: \"{config['project_type']}\"\n"

    content += "\nplugins:\n"
    for plugin in plugins:
        content += f"  - {plugin}\n"

    if config:
        content += "\nsettings:\n"
        for key, value in config.items():
            if key != "project_type":  # Already added to project section
                content += f"  {key}: \"{value}\"\n"

    return content


def check_aida_installed() -> bool:
    """Check if AIDA has been installed (checks for aida.yml marker).

    Returns:
        True if aida.yml marker file exists, False otherwise
    """
    claude_dir = get_claude_dir()
    aida_marker = claude_dir / AIDA_MARKER_FILE
    return aida_marker.exists()


def detect_vcs_info(project_root: Path) -> Dict[str, Any]:
    """Detect version control system information.

    Args:
        project_root: Path to project root

    Returns:
        Dictionary with VCS details
    """
    vcs = {}

    # Check for Git
    git_dir = project_root / ".git"
    if git_dir.exists():
        vcs["type"] = "git"
        vcs["has_vcs"] = True

        # Check if it's a worktree or bare repo
        vcs["uses_worktrees"] = git_dir.is_file()  # .git file = worktree

        # Try to detect remote URL and infer hosting
        try:
            import subprocess
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                remote_url = result.stdout.strip()
                vcs["remote_url"] = remote_url
                vcs["is_github"] = "github.com" in remote_url.lower()
                vcs["is_gitlab"] = "gitlab" in remote_url.lower()
            else:
                vcs["remote_url"] = None
                vcs["is_github"] = False
                vcs["is_gitlab"] = False
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            # Git command failed or not available
            vcs["remote_url"] = None
            vcs["is_github"] = False
            vcs["is_gitlab"] = False
    else:
        vcs["type"] = "none"
        vcs["has_vcs"] = False
        vcs["uses_worktrees"] = False
        vcs["remote_url"] = None
        vcs["is_github"] = False
        vcs["is_gitlab"] = False

    return vcs


def _detect_existing_context(
    project_root: Path,
) -> Dict[str, str]:
    """Detect existing project-context files (#84).

    The generated project-context SKILL.md should reference rich
    hand-written context the user has already provided rather than
    re-claiming "no conventions documented". This helper returns a
    flat dict of template variables that the SKILL.md template
    consumes:

      - has_claude_md: 'true' / 'false'
      - claude_md_path: relative path to the CLAUDE.md (or '')
      - has_knowledge_dir: 'true' / 'false'
      - knowledge_dir: directory name like 'knowledge/' (or '')
      - has_knowledge_index: 'true' / 'false'
      - knowledge_index_path: relative path to the index (or '')

    Search order:
      - CLAUDE.md: project root, then .claude/CLAUDE.md
      - knowledge index: knowledge/index.md, then
        knowledge/README.md, then docs/index.md
    """
    result: Dict[str, str] = {
        "has_claude_md": "false",
        "claude_md_path": "",
        "has_knowledge_dir": "false",
        "knowledge_dir": "",
        "has_knowledge_index": "false",
        "knowledge_index_path": "",
    }

    claude_md_candidates = (
        project_root / "CLAUDE.md",
        project_root / ".claude" / "CLAUDE.md",
    )
    for candidate in claude_md_candidates:
        if candidate.is_file():
            result["has_claude_md"] = "true"
            result["claude_md_path"] = str(
                candidate.relative_to(project_root)
            )
            break

    knowledge_root = project_root / "knowledge"
    if knowledge_root.is_dir():
        result["has_knowledge_dir"] = "true"
        result["knowledge_dir"] = "knowledge/"

    index_candidates = (
        project_root / "knowledge" / "index.md",
        project_root / "knowledge" / "README.md",
        project_root / "docs" / "index.md",
    )
    for candidate in index_candidates:
        if candidate.is_file():
            result["has_knowledge_index"] = "true"
            result["knowledge_index_path"] = str(
                candidate.relative_to(project_root)
            )
            break

    return result


def detect_files(project_root: Path) -> Dict[str, bool]:
    """Detect presence of common project files.

    Args:
        project_root: Path to project root

    Returns:
        Dictionary of boolean flags for file existence
    """
    files = {}

    # Check for common files
    files["has_readme"] = any((project_root / name).exists()
                             for name in ["README.md", "README.rst", "README.txt", "README"])
    files["has_license"] = any((project_root / name).exists()
                              for name in ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"])
    files["has_gitignore"] = (project_root / ".gitignore").exists()
    files["has_dockerfile"] = (project_root / "Dockerfile").exists()
    files["has_docker_compose"] = any((project_root / name).exists()
                                     for name in ["docker-compose.yml", "docker-compose.yaml", "compose.yml"])
    files["has_changelog"] = any((project_root / name).exists()
                                for name in ["CHANGELOG.md", "HISTORY.md", "RELEASES.md", "NEWS.md"])
    files["has_contributing"] = any((project_root / name).exists()
                                   for name in ["CONTRIBUTING.md", "CONTRIBUTING.rst", "CONTRIBUTING"])

    # Check for test directories
    files["has_tests"] = any((project_root / name).exists()
                            for name in ["test", "tests", "spec", "__tests__", "test_", "tests_"])

    # Check for CI/CD
    files["has_ci_cd"] = ((project_root / ".github" / "workflows").exists() or
                         (project_root / ".gitlab-ci.yml").exists() or
                         (project_root / ".circleci").exists() or
                         (project_root / "Jenkinsfile").exists() or
                         (project_root / ".travis.yml").exists())

    # Check for docs directory
    files["has_docs_directory"] = any((project_root / name).exists()
                                     for name in ["docs", "doc", "documentation"])

    return files


def detect_project_info(project_root: Path) -> Dict[str, Any]:
    """Detect comprehensive project information with structured schema.

    Analyzes the project directory to detect:
    - Project metadata (name, path)
    - Version control information
    - File presence (README, LICENSE, etc.)
    - Languages and tools
    - Inferred facts (project type, team size, etc.)
    - Preference placeholders (null for unknowns)

    Args:
        project_root: Path to project root directory

    Returns:
        Dictionary of detected project information in structured schema

    Example:
        >>> info = detect_project_info(Path("/path/to/project"))
        >>> print(info["vcs"]["type"])
        'git'
    """
    # Project metadata
    config = {
        "version": AIDA_VERSION,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "config_complete": False,

        # Basic info
        "project_name": project_root.name,
        "project_root": str(project_root),
    }

    # Detect VCS info
    config["vcs"] = detect_vcs_info(project_root)

    # Detect file presence
    config["files"] = detect_files(project_root)

    # Detect languages
    languages = detect_languages(project_root)
    config["languages"] = {
        "primary": list(languages)[0] if languages else "Unknown",
        "all": list(languages) if languages else []
    }

    # Detect tools and frameworks
    tools = detect_tools(project_root)
    config["tools"] = {
        "detected": list(tools) if tools else []
    }

    # Detect testing framework
    testing = detect_testing_approach(project_root)
    if testing:
        config["tools"]["testing_framework"] = testing

    # Detect project type
    project_type = detect_project_type(project_root)

    # Check for README and estimate documentation level
    readme_path = project_root / "README.md"
    doc_level = None
    if readme_path.exists():
        try:
            readme_content = readme_path.read_text(encoding='utf-8')
            # Estimate documentation level based on README length
            if len(readme_content) > 5000:
                doc_level = "Comprehensive - Full guides, examples, architecture docs"
            elif len(readme_content) > 1000:
                doc_level = "Standard - README, API docs, inline comments"
            else:
                doc_level = "Minimal - README and inline comments"
        except (FileNotFoundError, PermissionError, UnicodeDecodeError):
            # Can't read README to estimate documentation level
            pass

    # Infer team collaboration
    has_contributing = config["files"]["has_contributing"]
    has_code_owners = (project_root / ".github" / "CODEOWNERS").exists()
    has_ci = config["files"]["has_ci_cd"]

    if has_contributing or has_code_owners:
        team_collab = "Open source with external contributors"
    elif has_ci and config["vcs"]["has_vcs"]:
        team_collab = "Small team (2-5 people) with frequent sync"
    else:
        team_collab = "Solo project - just me"

    # Inferred facts
    config["inferred"] = {
        "project_type": project_type if project_type else "Unknown",
        "team_collaboration": team_collab,
        "documentation_level": doc_level if doc_level else "Minimal",
        "code_organization": "Follow existing pattern"  # Can be enhanced later
    }

    # Preferences (all null initially - need to ask)
    config["preferences"] = {
        "branching_model": None,
        "issue_tracking": "GitHub Issues" if config["vcs"].get("is_github") else None,
        "github_project_board": None,
        "jira_config": None,
        "confluence_spaces": None,
        "project_conventions": None,
        "api_docs_approach": None,
    }

    return config


def validate_project_root(project_root_str: str) -> Path:
    """Validate that project root is safe and legitimate.

    This function prevents path traversal attacks and access to sensitive
    system directories by validating the project root path.

    Args:
        project_root_str: Path to project root as string

    Returns:
        Validated and resolved Path object

    Raises:
        ValueError: If path is invalid, doesn't exist, or points to sensitive directory

    Security:
        - Prevents access to system directories (/etc, /sys, /proc, etc.)
        - Prevents access to sensitive home directory dotfiles (.ssh, .aws, etc.)
        - Requires path to exist and be a directory
    """
    # Resolve and expand path
    try:
        project_root = Path(project_root_str).expanduser().resolve()
    except (ValueError, RuntimeError) as e:
        raise ValueError(f"Invalid project root path: {e}")

    # Must be a directory that exists
    if not project_root.exists():
        raise ValueError(f"Project root does not exist: {project_root}")
    if not project_root.is_dir():
        raise ValueError(f"Project root is not a directory: {project_root}")

    # Prevent system directory access
    system_dirs = ['/etc', '/sys', '/proc', '/var', '/usr', '/bin', '/sbin', '/root']
    for system_dir in system_dirs:
        system_path = Path(system_dir).resolve()
        try:
            # Check if project_root is the system dir or inside it
            if project_root == system_path or project_root.is_relative_to(system_path):
                raise ValueError(f"Cannot configure system directory: {project_root}")
        except (ValueError, AttributeError):
            # is_relative_to not available in Python < 3.9, fall back to string check
            if str(project_root).startswith(str(system_path)):
                raise ValueError(f"Cannot configure system directory: {project_root}")

    # Prevent home directory sensitive dotfile access
    try:
        home_dir = Path.home()
        sensitive_dirs = {'.ssh', '.aws', '.gnupg', '.config', '.kube'}
        if project_root.parent == home_dir and project_root.name in sensitive_dirs:
            raise ValueError(f"Cannot configure sensitive directory: {project_root}")
    except (RuntimeError, KeyError):
        # If home directory cannot be determined, skip this check
        pass

    return project_root


def infer_project_preferences(context: Dict[str, Any]) -> Dict[str, Any]:
    """Infer project preferences from context.

    Args:
        context: Project context dictionary containing:
            - project_root: Path to project root (optional)
            - Other context information

    Returns:
        Dictionary of inferred preferences

    Example:
        >>> context = {"project_root": "/path/to/project"}
        >>> inferred = infer_project_preferences(context)
        >>> print(inferred.get("project_type"))
        'Web application (full-stack)'
    """
    inferred = {}

    # Get project root from context (with null check and validation)
    project_root_str = context.get("project_root") or os.getcwd()
    project_root = validate_project_root(project_root_str)

    # Detect project information
    project_info = detect_project_info(project_root)

    # Map detected information to questionnaire answers

    # Project type (if detected confidently)
    if project_info.get("project_type"):
        inferred["project_type"] = project_info["project_type"]

    # Team collaboration (if inferred)
    if project_info.get("team_collaboration"):
        inferred["team_collaboration"] = project_info["team_collaboration"]

    # Testing approach (if detected)
    if project_info.get("testing_approach"):
        inferred["testing_approach"] = project_info["testing_approach"]

    # Documentation level (if estimated)
    if project_info.get("documentation_level"):
        inferred["documentation_level"] = project_info["documentation_level"]

    # Store full project info for later use
    inferred["_project_info"] = project_info

    return inferred


def get_questions(context: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze context and return questions that need user input (Phase 1).

    New config-driven approach:
    1. Checks that AIDA is installed
    2. Detects all project information (facts + preferences with nulls)
    3. Saves to .claude/aida-project-context.yml
    4. Identifies preference gaps (null values)
    5. Returns minimal questions only for gaps

    Args:
        context: Project context dictionary containing:
            - project_root: Path to project root (optional, defaults to cwd)
            - is_update: Whether this is updating existing config (optional)

    Returns:
        Dictionary containing:
            {
                "questions": [...],      # Questions for null preferences only
                "inferred": {...},       # Auto-detected facts
                "project_info": {...},   # Detected project information (legacy)
                "template": "configure"  # Which template was used
            }

    Raises:
        InstallationError: If AIDA is not installed
        FileOperationError: If config cannot be saved

    Example:
        >>> context = {"project_root": "/path/to/project"}
        >>> result = get_questions(context)
        >>> # Returns 0-3 questions for unknown preferences only
    """
    # Check that AIDA is installed first
    if not check_aida_installed():
        raise InstallationError(
            "AIDA is not installed yet",
            "Please run 'python install.py' or use the AIDA install skill first"
        )

    # Get project root from context (with validation)
    project_root_str = context.get("project_root") or os.getcwd()
    project_root = validate_project_root(project_root_str)

    # Detect all project information (comprehensive)
    project_config = detect_project_info(project_root)

    # Save to .claude/aida-project-context.yml + aida-project-context.local.yml
    # (split: project-level facts in the committed file, user-specific
    # data in the gitignored .local overlay — see issue #65)
    try:
        project_path, _ = write_project_context(project_root, project_config)
        logger.info(f"Saved project configuration to {project_path}")
    except (OSError, PermissionError) as e:
        logger.warning(f"Could not save project config: {e}")
        # Continue anyway - not critical for this phase

    # Identify gaps in preferences (null values)
    preferences = project_config.get("preferences", {})
    questions = []

    # Branching model (ask if null and using git).
    # Capped at 4 mutually-exclusive named models — AskUserQuestion
    # caps at 4 options and supplies its own "Other" automatically,
    # which covers "Custom workflow" and "No specific model" (#85).
    if preferences.get("branching_model") is None and project_config["vcs"]["type"] == "git":
        questions.append({
            "id": "branching_model",
            "question": "What branching model does this project follow?",
            "type": "choice",
            "required": True,
            "help": (
                "AIDA suggests branch names and merge strategies "
                "based on this model. Pick 'Other' if your project "
                "uses a custom workflow or no specific model."
            ),
            "options": [
                "GitHub Flow (feature branches → main)",
                "Git Flow (main, develop, feature, release, hotfix)",
                "GitLab Flow (feature branches → main → environments)",
                "Trunk-based (commit directly to main, short-lived branches)",
            ]
        })

    # Issue tracking (ask if null, but already defaulted to GitHub
    # Issues if GitHub). Capped at 4 — AskUserQuestion adds its own
    # "Other" so users on Linear, Asana, etc. can type it in. The
    # explicit "Other (not supported …)" entry was redundant with
    # that built-in (#85).
    if preferences.get("issue_tracking") is None:
        questions.append({
            "id": "issue_tracking",
            "question": "What issue tracking system does this project use?",
            "type": "choice",
            "required": True,
            "help": (
                "AIDA provides native MCP integration for GitHub and "
                "JIRA/Atlassian. Pick 'Other' for anything else and "
                "note the system in your project conventions."
            ),
            "options": [
                "GitHub Issues",
                "GitHub Projects (project board)",
                "JIRA/Atlassian",
                "None - informal tracking only",
            ]
        })

    # Project conventions (optional but helpful)
    if preferences.get("project_conventions") is None:
        questions.append({
            "id": "project_conventions",
            "question": "What are the key conventions or patterns for this project?",
            "type": "multiline",
            "required": False,
            "help": "Examples:\n- \"Use Redux for state management\"\n- \"All API calls go in /services directory\"\n- \"Feature flags required for new features\"\n\nThis helps AIDA understand how to structure code for THIS specific project."
        })

    # Plugin config discovery
    config_plugins = []
    try:
        from utils.plugins import (
            discover_installed_plugins,
            get_plugins_with_config,
            generate_plugin_checklist,
            generate_plugin_preference_questions,
        )
        all_plugins = discover_installed_plugins()
        config_plugins = get_plugins_with_config(all_plugins)
        plugin_checklist = generate_plugin_checklist(config_plugins)
        if plugin_checklist:
            questions.insert(0, plugin_checklist)
            # Generate preference questions for all config plugins;
            # the UI uses the condition field to show only selected ones
            all_names = [p["name"] for p in config_plugins]
            pref_questions = generate_plugin_preference_questions(
                all_names, config_plugins
            )
            for pq in pref_questions:
                pq["condition"] = {"selected_plugins": pq.get(
                    "_plugin_name", ""
                )}
                pq.pop("_plugin_name", None)
            questions.extend(pref_questions)
    except (ImportError, FileNotFoundError, ValueError) as e:
        # Plugin discovery can fail if modules aren't available or config is invalid
        logger.warning("Plugin discovery failed (non-critical): %s", e)

    # Agent discovery
    discovered_agents = []
    try:
        from utils.agents import discover_agents
        discovered_agents = discover_agents(project_root)
    except (ImportError, FileNotFoundError, ValueError) as e:
        # Agent discovery can fail if modules aren't available or config is invalid
        logger.warning(
            "Agent discovery failed (non-critical): %s", e
        )

    # Return minimal question set
    return {
        "questions": questions,
        "inferred": project_config.get("inferred", {}),
        "project_info": project_config,  # Return full config for compatibility
        "template": "configure",
        "config_plugins": config_plugins,
        "discovered_agents": discovered_agents,
    }


def validate_responses(responses: Dict[str, Any]) -> None:
    """Validate that responses match expected questionnaire schema.

    This function prevents injection attacks and configuration errors by
    validating that user responses match the expected question IDs and
    values defined in the questionnaire.

    Args:
        responses: User answers to validate

    Raises:
        ConfigurationError: If responses contain invalid keys or values

    Security:
        - Prevents injection of unexpected configuration keys
        - Validates enum values match questionnaire options
        - Protects against malformed or malicious responses
    """
    # Load questionnaire to get valid options
    try:
        questions = load_questionnaire(CONFIGURE_QUESTIONNAIRE)
    except (FileNotFoundError, PermissionError, yaml.YAMLError) as e:
        logger.warning(f"Could not load questionnaire for validation: {e}")
        # If we can't load questionnaire, skip validation (graceful degradation)
        return

    # Build schema from questionnaire
    valid_ids = set()
    enum_validators = {}

    for question in questions:
        q_id = question.get('id')
        if not q_id:
            continue

        valid_ids.add(q_id)

        # For choice questions, validate enum values
        if question.get('type') == 'choice' and 'options' in question:
            enum_validators[q_id] = set(question['options'])

    # Validate responses
    for key, value in responses.items():
        # Warn about unexpected keys (but don't fail - could be from future versions)
        if key not in valid_ids:
            logger.warning(f"Unexpected response key: {key} (not in questionnaire)")

        # Validate enum values for choice questions
        if key in enum_validators:
            if value not in enum_validators[key]:
                valid_options = ', '.join(sorted(enum_validators[key]))
                raise ConfigurationError(
                    f"Invalid value for {key}: '{value}'",
                    f"Valid options are: {valid_options}"
                )

        # Validate value types and sanitize
        if not isinstance(value, (str, int, float, bool)):
            raise ConfigurationError(
                f"Invalid value type for {key}: {type(value).__name__}",
                "Values must be strings, numbers, or booleans"
            )


def configure(responses: Dict[str, Any], inferred: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create project configuration from YAML config + responses (Phase 2 - New).

    New YAML-based approach:
    1. Load existing aida-project-context.yml (created in Phase 1)
    2. Update preferences with user responses
    3. Map YAML config to template variables
    4. Render project-context skill from template
    5. Mark config_complete = true

    Args:
        responses: User answers to preference questions
        inferred: Ignored (kept for backward compatibility)

    Returns:
        Dictionary containing:
            {
                "success": True/False,
                "files_created": [...],
                "message": "...",
                "config_path": "..."
            }

    Example:
        >>> responses = {"branching_model": "GitHub Flow"}
        >>> result = configure(responses)
        >>> # Updates YAML and creates skill
    """
    files_created = []

    try:
        # Check that AIDA is installed
        if not check_aida_installed():
            raise InstallationError(
                "AIDA is not installed yet",
                "Please run 'python install.py' or use the AIDA install skill first"
            )

        # Get project root from current working directory
        project_root = Path.cwd()
        config_path = project_root / ".claude" / PROJECT_CONTEXT_FILE

        # Load existing YAML config (should exist from Phase 1).
        # load_project_context merges aida-project-context.yml with the
        # gitignored .local overlay so we operate on a single dict,
        # then re-split on write.
        if not config_path.exists():
            raise FileOperationError(
                f"Project config not found: {config_path}",
                "Run 'python configure.py --get-questions' first to detect project facts"
            )

        config = load_project_context(project_root)

        # Update preferences with user responses
        for key, value in responses.items():
            if key in config.get("preferences", {}):
                config["preferences"][key] = value
                logger.info(f"Updated preference: {key} = {value}")

        # Store plugin preferences
        # Question IDs use format: plugin_{name}__{key} with __
        # as delimiter to avoid collisions with underscores in names
        selected_plugins = responses.pop("selected_plugins", None)
        plugin_prefs = {}
        for key in list(responses.keys()):
            if key.startswith("plugin_"):
                value = responses.pop(key)
                rest = key[len("plugin_"):]
                sep_idx = rest.find("__")
                if sep_idx > 0:
                    p_name = rest[:sep_idx]
                    p_key = rest[sep_idx + 2:].replace("_", ".")
                    if p_name not in plugin_prefs:
                        plugin_prefs[p_name] = {"enabled": True}
                    plugin_prefs[p_name][p_key] = value

        # Mark unselected plugins as disabled
        if selected_plugins is not None:
            try:
                from utils.plugins import (
                    discover_installed_plugins,
                    get_plugins_with_config,
                )
                all_p = discover_installed_plugins()
                cfg_p = get_plugins_with_config(all_p)
                for plugin in cfg_p:
                    pn = plugin["name"]
                    if pn not in (selected_plugins or []):
                        if pn not in plugin_prefs:
                            plugin_prefs[pn] = {"enabled": False}
            except (ImportError, ValueError):
                # Plugin discovery or processing failed
                logger.warning(
                    "Failed to mark unselected plugins (non-critical)",
                    exc_info=True,
                )

        if plugin_prefs:
            config["plugins"] = plugin_prefs

        # Mark configuration as complete
        config["config_complete"] = True
        config["last_updated"] = datetime.now(timezone.utc).isoformat()

        # Save updated config — split into committed + .local overlay.
        project_path, local_path = write_project_context(project_root, config)
        files_created.append(str(project_path))
        files_created.append(str(local_path))
        logger.info(f"Updated {project_path} and {local_path}")

        # Add the .local file to .gitignore so contributors don't accidentally
        # commit each other's paths/timestamps. No-op if the entry is already
        # present or if the project has no .gitignore.
        try:
            if ensure_gitignore_entry(project_root):
                logger.info("Added aida-project-context.local.yml to .gitignore")
        except (OSError, PermissionError) as e:
            logger.warning(f"Could not update .gitignore: {e}")

        # Map YAML config to template variables (all strings for Jinja2)
        template_vars = {
            'project_name': config['project_name'],
            'project_type': config['inferred']['project_type'],
            'team_collaboration': config['inferred']['team_collaboration'],
            'documentation_level': config['inferred']['documentation_level'],
            'code_organization': config['inferred']['code_organization'],

            # VCS
            'vcs': config['vcs']['type'],
            'uses_worktrees': 'Yes - Bare repo with all branches as sibling worktrees' if config['vcs']['uses_worktrees'] else 'No',
            'branching_model': config['preferences']['branching_model'] or 'Not specified',

            # Files (convert booleans to strings)
            'has_readme': 'true' if config['files']['has_readme'] else 'false',
            'readme_file': 'README.md',
            'has_license': 'true' if config['files']['has_license'] else 'false',
            'license_file': 'LICENSE',
            'has_gitignore': 'true' if config['files']['has_gitignore'] else 'false',
            'has_changelog': 'true' if config['files']['has_changelog'] else 'false',
            'changelog_files': '',
            'changelog_intent': '',
            'has_contributing': 'true' if config['files']['has_contributing'] else 'false',
            'has_docs_directory': 'true' if config['files']['has_docs_directory'] else 'false',
            'docs_directory': 'docs',
            'docs_directory_intent': 'README.md only',
            'has_tests': 'true' if config['files']['has_tests'] else 'false',
            # Note: test_directories and src_directories are intentionally left empty.
            # Current detection only checks for existence (has_tests boolean), not actual
            # directory names. Template uses these empty values to show fallback text.
            # Future enhancement: Detect actual directory names (tests/ vs test/ vs spec/).
            'test_directories': '',
            'src_directories': '',
            'has_dockerfile': 'true' if config['files']['has_dockerfile'] else 'false',
            'has_docker_compose': 'true' if config['files']['has_docker_compose'] else 'false',
            'has_ci_cd': 'true' if config['files']['has_ci_cd'] else 'false',
            'has_github_actions': 'true' if (project_root / ".github" / "workflows").exists() else 'false',
            'has_gitlab_ci': 'true' if (project_root / ".gitlab-ci.yml").exists() else 'false',

            # Languages
            'languages': config['languages']['primary'],

            # Tools
            'tools': ', '.join(config['tools']['detected']) if config['tools']['detected'] else 'None',
            'testing_framework': config['tools'].get('testing_framework', 'Unknown'),
            'testing_framework_intent': config['tools'].get('testing_framework', 'Unknown'),
            'testing_approach': config['tools'].get('testing_framework', 'Unknown'),

            # Package managers (check project root)
            'has_package_json': 'true' if (project_root / "package.json").exists() else 'false',
            'has_requirements_txt': 'true' if (project_root / "requirements.txt").exists() else 'false',
            'has_pyproject_toml': 'true' if (project_root / "pyproject.toml").exists() else 'false',
            'has_gemfile': 'true' if (project_root / "Gemfile").exists() else 'false',
            'has_go_mod': 'true' if (project_root / "go.mod").exists() else 'false',
            'has_cargo_toml': 'true' if (project_root / "Cargo.toml").exists() else 'false',

            # Preferences
            'issue_tracking': config['preferences']['issue_tracking'] or '',
            'project_conventions': config['preferences']['project_conventions'] or '',
            'api_docs_intent': config['preferences'].get('api_docs_approach') or '',
            'github_project_config': config['preferences'].get('github_project_board') or '',
            'jira_config': config['preferences'].get('jira_config') or '',
            'confluence_config': config['preferences'].get('confluence_spaces') or '',

            # Docker & CI/CD intents
            'uses_docker': 'true' if config['files']['has_dockerfile'] or config['files']['has_docker_compose'] else 'false',
            'docker_compose_intent': 'Not configured',
            'ci_cd_intent': 'Not configured',
            'uses_confluence': 'true' if config['preferences'].get('confluence_spaces') else 'false',

            # Coding standards
            'coding_standards': '',

            # Timestamp
            'timestamp': datetime.now().isoformat(),
        }

        # Existing-context detection (#84): when the project already
        # has a CLAUDE.md / knowledge index / docs, the generated
        # SKILL.md should reference them rather than re-claiming
        # "no conventions documented".
        existing_context = _detect_existing_context(project_root)
        template_vars.update(existing_context)

        # Get actual README length (not hardcoded)
        if config['files']['has_readme']:
            readme_path = project_root / 'README.md'
            try:
                template_vars['readme_length'] = str(len(readme_path.read_text(encoding='utf-8')))
            except (FileNotFoundError, PermissionError, UnicodeDecodeError):
                # Can't read README file
                template_vars['readme_length'] = '0'
        else:
            template_vars['readme_length'] = '0'

        # Create skills directory
        project_skills_dir = project_root / ".claude" / "skills"
        ensure_directory(project_skills_dir)

        # Create project-context skill directory
        project_context_output = project_root / ".claude" / "skills" / "project-context"
        ensure_directory(project_context_output)

        # Verify template exists
        if not PROJECT_CONTEXT_TEMPLATE.exists():
            raise InstallationError(
                f"Project context template not found: {PROJECT_CONTEXT_TEMPLATE}",
                "This is a bug - please report it"
            )

        # Render project-context skill from template
        logger.info(f"Rendering project-context skill to {project_context_output}")
        render_skill_directory(
            PROJECT_CONTEXT_TEMPLATE,
            project_context_output,
            template_vars
        )
        files_created.append(str(project_context_output / "SKILL.md"))

        # Update CLAUDE.md with agent routing directives
        try:
            from utils.agents import update_agent_routing
            routing_result = update_agent_routing(
                project_root=project_root
            )
            if routing_result["success"]:
                logger.info(routing_result["message"])
                if routing_result.get("path"):
                    files_created.append(
                        routing_result["path"]
                    )
        except (ImportError, FileNotFoundError, ValueError) as e:
            # Agent routing can fail if modules aren't available or config is invalid
            logger.warning(
                "Agent routing update failed"
                " (non-critical): %s",
                e,
            )

        # Write aida.yml marker so detect.py reports project_configured: true
        marker_path = project_root / ".claude" / AIDA_MARKER_FILE
        marker_content = render_aida_project_marker(
            preferences=config.get("preferences", {}),
            project_name=config["project_name"],
        )
        atomic_write(marker_path, marker_content)
        files_created.append(str(marker_path))
        logger.info(f"Created project marker: {marker_path}")

        # Nudge user toward expert configuration if experts available
        try:
            from utils.agents import discover_agents
            agents = discover_agents(project_root=project_root)
            has_experts = any(
                a.get("expert-role") or a.get("expert_role")
                for a in agents
            )
            project_config = yaml.safe_load(
                config_path.read_text()
            ) or {}
            has_expert_config = "experts" in project_config

            if has_experts and not has_expert_config:
                print(
                    "\nExpert agents detected from installed plugins.\n"
                    "Run `/aida expert list configure` to select which "
                    "experts are active for this project."
                )
        except Exception:
            logger.debug("Expert nudge check failed", exc_info=True)

        message = (
            "Project configuration complete! "
            "Created project-context skill in .claude/skills/\n"
            "Next step: Run /aida config permissions to "
            "configure Claude Code permissions."
        )

        return {
            "success": True,
            "files_created": files_created,
            "message": message,
            "config_path": str(config_path)
        }

    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        # Intentionally broad: top-level handler for any unexpected error during configuration
        # Ensures we always return a structured response even for unanticipated failures
        logger.error(f"Configuration failed: {e}", exc_info=True)

        return {
            "success": False,
            "files_created": files_created,
            "message": f"Configuration failed: {e}",
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }


def main() -> int:
    """Main CLI entry point with two-phase API.

    Returns:
        Exit code (0 = success, 1 = error)
    """
    parser = argparse.ArgumentParser(
        description="AIDA Project Configuration - Two-Phase API"
    )

    parser.add_argument(
        "--get-questions",
        action="store_true",
        help="Phase 1: Analyze context and return questions (outputs JSON)"
    )

    parser.add_argument(
        "--configure",
        action="store_true",
        help="Phase 2: Configure project with provided responses (outputs JSON)"
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

        # Phase 2: Configure
        elif args.configure:
            if not args.responses:
                print(json.dumps({
                    "success": False,
                    "message": "--responses required for --configure"
                }))
                return 1

            responses = safe_json_load(args.responses)
            inferred = safe_json_load(args.inferred) if args.inferred else {}

            result = configure(responses, inferred)
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
        # Intentionally broad: top-level CLI error handler catches any unexpected exceptions
        # Ensures the program always exits gracefully with a structured error response
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(json.dumps({
            "success": False,
            "message": f"Error: {e}",
            "error_type": type(e).__name__
        }))
        return 1


if __name__ == "__main__":
    sys.exit(main())
