#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Plugin Scaffolding Operations - Two-Phase API

Scaffolds a complete Claude Code plugin project as a new local git
repository with language-specific tooling (Python or TypeScript).

Usage (via manage.py):
    # Phase 1: Get questions (returns JSON)
    python manage.py --get-questions --context='{"operation": "scaffold", ...}'

    # Phase 2: Execute scaffolding (returns JSON)
    python manage.py --execute --context='{"operation": "scaffold", ...}'
"""

import shlex
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utils import (
    validate_name,
    validate_description,
    validate_version,
    to_kebab_case,
)
from .scaffold_ops.context import (
    infer_git_config,
    validate_target_directory,
    check_gh_available,
    resolve_default_target,
)
from .scaffold_ops.licenses import (
    get_license_text,
    PROMPT_LICENSE_OPTIONS,
    is_valid_license_id,
)
from .scaffold_ops.generators import (
    create_directory_structure,
    render_shared_files,
    render_none_files,
    render_python_files,
    render_typescript_files,
    render_stub_agent,
    render_stub_skill,
    assemble_gitignore,
    assemble_makefile,
    initialize_git,
    create_initial_commit,
)
from .constants import SUPPORTED_LANGUAGES
from .shared import build_template_variables

logger = logging.getLogger(__name__)

# Paths
_OPS_DIR = Path(__file__).parent
_SCRIPTS_DIR = _OPS_DIR.parent
_SKILL_DIR = _SCRIPTS_DIR.parent
_PROJECT_ROOT = _SKILL_DIR.parent.parent

SCAFFOLD_TEMPLATES_DIR = _SKILL_DIR / "templates" / "scaffold"
EXTENSION_TEMPLATES_DIR = _SKILL_DIR / "templates" / "extension"

# Stub templates for agent/skill stubs live in their respective
# manager skills.  The render_stub_agent/skill helpers expect a
# base directory containing ``agent/agent.md.jinja2`` or
# ``skill/SKILL.md.jinja2`` respectively.
AGENT_TEMPLATES_DIR = (
    _PROJECT_ROOT / "skills" / "agent-manager" / "templates"
)
SKILL_TEMPLATES_DIR = (
    _PROJECT_ROOT / "skills" / "skill-manager" / "templates"
)


def get_questions(
    context: dict[str, Any],
) -> dict[str, Any]:
    """Phase 1: Analyze context, return questions for missing info.

    Args:
        context: Partial context from the user/orchestrator

    Returns:
        Dictionary with 'questions' list and 'inferred' data
    """
    questions: list[dict[str, Any]] = []
    inferred: dict[str, Any] = {}

    # Infer git config for author info
    git_config = infer_git_config()
    if git_config["author_name"]:
        inferred["author_name"] = git_config["author_name"]
    if git_config["author_email"]:
        inferred["author_email"] = git_config["author_email"]

    # Plugin name
    if not context.get("plugin_name"):
        questions.append(
            {
                "id": "plugin_name",
                "question": "What is the plugin name?",
                "type": "text",
                "hint": (
                    "Use kebab-case "
                    "(e.g., 'my-awesome-plugin')"
                ),
                "required": True,
                "validation": (
                    "Must start with lowercase letter, "
                    "contain only lowercase letters, "
                    "numbers, and hyphens (2-50 chars)"
                ),
            }
        )

    # Description
    if not context.get("description"):
        questions.append(
            {
                "id": "description",
                "question": (
                    "Provide a short description "
                    "for the plugin"
                ),
                "type": "text",
                "hint": (
                    "10-500 characters, used in "
                    "plugin.json and README"
                ),
                "required": True,
            }
        )

    # License. Capped at 4 mutually-exclusive named options to fit
    # AskUserQuestion's option cap. AskUserQuestion supplies its own
    # "Other" automatically — picking it lets the user type any SPDX
    # id (MPL-2.0, BSD-3-Clause, LGPL-3.0-or-later, …) and the
    # scaffold writes a placeholder LICENSE for unknown ids (#85,
    # #111).
    if not context.get("license"):
        questions.append(
            {
                "id": "license",
                "question": (
                    "Which license should the plugin use? "
                    "Pick 'Other' to type a custom SPDX id."
                ),
                "type": "choice",
                "options": PROMPT_LICENSE_OPTIONS,
                "default": "UNLICENSED",
            }
        )

    # Language. "none" is a skills-only / markdown-only flavor — no
    # Python or TypeScript toolchain files. Explicit confirmation
    # here so the scaffold doesn't silently default to Python for
    # plugins that ship pure agents / skills / CLAUDE.md content
    # (#96 — a markdown-only plugin previously got the full Python
    # toolchain by default and had to manually rip it out).
    if not context.get("language"):
        questions.append(
            {
                "id": "language",
                "question": (
                    "Which language toolchain? "
                    "('none' = skills-only, no Python or TypeScript)"
                ),
                "type": "choice",
                "options": list(SUPPORTED_LANGUAGES),
                "default": "python",
            }
        )

    # Target directory
    if not context.get("target_directory"):
        plugin_name = context.get(
            "plugin_name", "my-plugin"
        )
        default_target = resolve_default_target(plugin_name)
        questions.append(
            {
                "id": "target_directory",
                "question": (
                    "Where should the plugin be created?"
                ),
                "type": "text",
                "default": default_target,
                "hint": (
                    "Absolute or relative path to an empty "
                    "or non-existent directory"
                ),
            }
        )

    # Agent stub
    if "include_agent_stub" not in context:
        questions.append(
            {
                "id": "include_agent_stub",
                "question": (
                    "Include an example agent stub?"
                ),
                "type": "boolean",
                "default": False,
            }
        )

    # Skill stub
    if "include_skill_stub" not in context:
        questions.append(
            {
                "id": "include_skill_stub",
                "question": (
                    "Include an example skill stub?"
                ),
                "type": "boolean",
                "default": False,
            }
        )

    # Keywords
    if "keywords" not in context:
        questions.append(
            {
                "id": "keywords",
                "question": (
                    "Comma-separated keywords/tags "
                    "for the marketplace listing"
                ),
                "type": "text",
                "default": "",
                "hint": (
                    "Optional. E.g.: "
                    "'productivity, automation, tooling'"
                ),
                "required": False,
            }
        )

    # GitHub repo creation (only if gh available)
    if (
        "create_github_repo" not in context
        and check_gh_available()
    ):
        questions.append(
            {
                "id": "create_github_repo",
                "question": (
                    "Create a GitHub repository "
                    "after scaffolding?"
                ),
                "type": "boolean",
                "default": False,
            }
        )

    # Author info (only if not inferred)
    if not inferred.get("author_name") and not context.get(
        "author_name"
    ):
        questions.append(
            {
                "id": "author_name",
                "question": "Author name",
                "type": "text",
                "required": True,
            }
        )

    if not inferred.get("author_email") and not context.get(
        "author_email"
    ):
        questions.append(
            {
                "id": "author_email",
                "question": "Author email",
                "type": "text",
                "required": True,
            }
        )

    return {
        "questions": questions,
        "inferred": inferred,
        "phase": "get_questions",
    }


def execute(context: dict[str, Any]) -> dict[str, Any]:
    """Phase 2: Execute scaffolding with the provided context.

    Args:
        context: Full context with all required fields

    Returns:
        Result dictionary with success status and details
    """
    # Validate required fields
    plugin_name = context.get("plugin_name", "")
    if not plugin_name:
        return {
            "success": False,
            "message": "plugin_name is required",
        }

    plugin_name = to_kebab_case(plugin_name)

    is_valid, error = validate_name(plugin_name)
    if not is_valid:
        return {
            "success": False,
            "message": f"Invalid plugin name: {error}",
        }

    description = context.get("description", "")
    is_valid, error = validate_description(description)
    if not is_valid:
        return {
            "success": False,
            "message": f"Invalid description: {error}",
        }

    version = context.get("version", "0.1.0")
    is_valid, error = validate_version(version)
    if not is_valid:
        return {
            "success": False,
            "message": f"Invalid version: {error}",
        }

    language = context.get("language", "python")
    if language not in SUPPORTED_LANGUAGES:
        return {
            "success": False,
            "message": f"Unsupported language: {language}",
        }

    license_id = context.get("license", "UNLICENSED")
    if not is_valid_license_id(license_id):
        return {
            "success": False,
            "message": (
                f"Invalid license: {license_id!r}. Expected an "
                f"SPDX id (e.g., 'MIT', 'MPL-2.0', 'Apache-2.0') "
                f"or 'UNLICENSED' for proprietary projects."
            ),
        }

    author_name = context.get("author_name", "")
    author_email = context.get("author_email", "")
    if not author_name or not author_name.strip():
        return {
            "success": False,
            "message": "author_name is required",
        }
    if not author_email or not author_email.strip():
        return {
            "success": False,
            "message": "author_email is required",
        }

    # Resolve target directory
    target_str = context.get("target_directory", "")
    if not target_str:
        target_str = resolve_default_target(plugin_name)

    target = Path(target_str).resolve()

    is_valid, error = validate_target_directory(str(target))
    if not is_valid:
        return {
            "success": False,
            "message": (
                f"Invalid target directory: {error}"
            ),
        }

    # Build template variables
    try:
        license_text = get_license_text(
            license_id,
            str(datetime.now(timezone.utc).year),
            author_name,
        )
    except ValueError as e:
        return {"success": False, "message": str(e)}

    # Build context dict for the shared variable builder
    build_context = dict(context)
    build_context.update({
        "plugin_name": plugin_name,
        "description": description,
        "version": version,
        "author_name": author_name,
        "author_email": author_email,
        "license_id": license_id,
        "language": language,
    })

    variables = build_template_variables(
        build_context, license_text
    )

    # Create the project
    all_files: list[str] = []

    try:
        target.mkdir(parents=True, exist_ok=True)

        create_directory_structure(target, language)

        all_files.extend(
            render_shared_files(
                target, variables, SCAFFOLD_TEMPLATES_DIR
            )
        )

        if language == "python":
            all_files.extend(
                render_python_files(
                    target,
                    variables,
                    SCAFFOLD_TEMPLATES_DIR,
                )
            )
        elif language == "typescript":
            all_files.extend(
                render_typescript_files(
                    target,
                    variables,
                    SCAFFOLD_TEMPLATES_DIR,
                )
            )
        else:  # "none" — skills-only plugin
            all_files.extend(
                render_none_files(
                    target,
                    variables,
                    SCAFFOLD_TEMPLATES_DIR,
                )
            )

        all_files.append(
            assemble_gitignore(
                target, language, SCAFFOLD_TEMPLATES_DIR
            )
        )
        all_files.append(
            assemble_makefile(
                target,
                language,
                variables,
                SCAFFOLD_TEMPLATES_DIR,
            )
        )

        # Write LICENSE + REUSE-required LICENSES/<id>.txt copy.
        # LICENSE stays at repo root for GitHub display; the
        # LICENSES directory is what `reuse lint` looks at.
        license_path = target / "LICENSE"
        license_path.write_text(license_text)
        all_files.append("LICENSE")
        if license_id != "UNLICENSED":
            licenses_dir = target / "LICENSES"
            licenses_dir.mkdir(exist_ok=True)
            (licenses_dir / f"{license_id}.txt").write_text(
                license_text
            )
            all_files.append(f"LICENSES/{license_id}.txt")

        # Optional stubs
        spdx_for_stubs = {
            "year": variables["year"],
            "copyright_holder": variables["copyright_holder"],
            "license_id": variables["license_id"],
        }
        if context.get("include_agent_stub"):
            stub_files = render_stub_agent(
                target,
                variables["agent_stub_name"],
                variables["agent_stub_description"],
                AGENT_TEMPLATES_DIR,
                timestamp=variables["timestamp"],
                spdx_context=spdx_for_stubs,
            )
            all_files.extend(stub_files)

        if context.get("include_skill_stub"):
            stub_files = render_stub_skill(
                target,
                variables["skill_stub_name"],
                variables["skill_stub_description"],
                language,
                SKILL_TEMPLATES_DIR,
                timestamp=variables["timestamp"],
                spdx_context=spdx_for_stubs,
            )
            all_files.extend(stub_files)

        # Initialize git
        git_initialized = initialize_git(target)
        git_committed = False
        if git_initialized:
            git_committed = create_initial_commit(target)

    except Exception as e:
        logger.error(
            "Scaffolding failed: %s", e, exc_info=True
        )
        return {
            "success": False,
            "message": f"Scaffolding failed: {e}",
            "error_type": type(e).__name__,
            "path": str(target),
            "files_created": sorted(all_files),
        }

    return {
        "success": True,
        "message": (
            f"Plugin '{plugin_name}' scaffolded successfully"
        ),
        "path": str(target),
        "files_created": sorted(all_files),
        "language": language,
        "git_initialized": git_initialized,
        "git_committed": git_committed,
        "create_github_repo": context.get(
            "create_github_repo", False
        ),
        "next_steps": _build_next_steps(
            plugin_name,
            target,
            language,
            context.get("create_github_repo", False),
        ),
    }


def _build_next_steps(
    plugin_name: str,
    target: Path,
    language: str,
    create_repo: bool,
) -> list[str]:
    """Build list of suggested next steps."""
    steps = [f"cd {shlex.quote(str(target))}"]

    if language == "python":
        steps.append('pip install -e ".[dev]"')
    elif language == "typescript":
        steps.append("npm install")
    else:  # "none" — skills-only plugin
        # No language deps to install; the lint tools (`reuse`,
        # `markdownlint-cli`) come from the CI workflow's install
        # step. For local dev, see CONTRIBUTING.md.
        steps.append(
            "# (skills-only: no language deps to install)"
        )

    steps.append("make lint  # verify project structure")
    if language != "none":
        steps.append("make test  # run initial tests")

    if create_repo:
        steps.append(
            f"gh repo create {plugin_name} "
            "--public --source=. --push"
        )

    return steps
