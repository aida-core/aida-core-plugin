# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Generator operations for plugin scaffolding.

Functions for creating directory structures, rendering templates,
and initializing git repositories for new plugin projects.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from shared.spdx import render_spdx_blocks, resolve_spdx_context
from shared.utils import render_template


def create_directory_structure(
    target: Path, language: str
) -> list[str]:
    """Create the directory structure for a new plugin.

    Args:
        target: Target directory path
        language: "python" or "typescript"

    Returns:
        List of created directory paths (relative to target)
    """
    dirs = [
        ".claude-plugin",
        ".github/workflows",
        "agents",
        "skills",
        "docs",
    ]

    if language == "python":
        dirs.extend([
            "scripts",
            "tests",
        ])
    elif language == "typescript":
        dirs.extend([
            "src",
            "tests",
        ])

    created = []
    for d in dirs:
        dir_path = target / d
        dir_path.mkdir(parents=True, exist_ok=True)
        created.append(d)

    return created


def render_shared_files(
    target: Path,
    variables: dict[str, Any],
    templates_dir: Path,
) -> list[str]:
    """Render language-independent template files.

    Args:
        target: Target directory path
        variables: Template variables
        templates_dir: Path to scaffold templates directory

    Returns:
        List of created file paths (relative to target)
    """
    shared_templates = {
        "shared/plugin.json.jinja2": (
            ".claude-plugin/plugin.json"
        ),
        "shared/marketplace.json.jinja2": (
            ".claude-plugin/marketplace.json"
        ),
        "shared/aida-config.json.jinja2": (
            ".claude-plugin/aida-config.json"
        ),
        "shared/claude-md.jinja2": "CLAUDE.md",
        "shared/contributing.md.jinja2": "CONTRIBUTING.md",
        "shared/readme.md.jinja2": "README.md",
        "shared/markdownlint.json.jinja2": (
            ".markdownlint.json"
        ),
        "shared/yamllint.yml.jinja2": ".yamllint.yml",
        "shared/frontmatter-schema.json.jinja2": (
            ".frontmatter-schema.json"
        ),
        # Authoritative roster behind the collective copyright
        # holder used in SPDX headers throughout the plugin.
        "shared/authors.jinja2": "AUTHORS",
    }
    # REUSE.toml only makes sense when the project has a real
    # SPDX license — UNLICENSED (proprietary, all-rights-reserved)
    # is not a valid SPDX identifier, so a REUSE.toml referencing
    # it would just produce noise.
    if variables.get("license_id") != "UNLICENSED":
        shared_templates["shared/reuse-toml.jinja2"] = "REUSE.toml"

    created = []
    for template_name, output_path in (
        shared_templates.items()
    ):
        content = render_template(
            templates_dir, template_name, variables
        )
        file_path = target / output_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        created.append(output_path)

    return created


def render_python_files(
    target: Path,
    variables: dict[str, Any],
    templates_dir: Path,
) -> list[str]:
    """Render Python-specific template files.

    Args:
        target: Target directory path
        variables: Template variables
        templates_dir: Path to scaffold templates directory

    Returns:
        List of created file paths (relative to target)
    """
    python_templates = {
        "python/pyproject.toml.jinja2": "pyproject.toml",
        "python/python-version.jinja2": ".python-version",
        "python/conftest.py.jinja2": "tests/conftest.py",
        "python/ci.yml.jinja2": (
            ".github/workflows/ci.yml"
        ),
    }

    created = []
    for template_name, output_path in (
        python_templates.items()
    ):
        content = render_template(
            templates_dir, template_name, variables
        )
        file_path = target / output_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        created.append(output_path)

    return created


def render_typescript_files(
    target: Path,
    variables: dict[str, Any],
    templates_dir: Path,
) -> list[str]:
    """Render TypeScript-specific template files.

    Args:
        target: Target directory path
        variables: Template variables
        templates_dir: Path to scaffold templates directory

    Returns:
        List of created file paths (relative to target)
    """
    ts_templates = {
        "typescript/package.json.jinja2": "package.json",
        "typescript/tsconfig.json.jinja2": "tsconfig.json",
        "typescript/eslint.config.mjs.jinja2": (
            "eslint.config.mjs"
        ),
        "typescript/prettierrc.json.jinja2": (
            ".prettierrc.json"
        ),
        "typescript/nvmrc.jinja2": ".nvmrc",
        "typescript/vitest.config.ts.jinja2": (
            "vitest.config.ts"
        ),
        "typescript/index.ts.jinja2": "src/index.ts",
        "typescript/index.test.ts.jinja2": (
            "tests/index.test.ts"
        ),
        "typescript/ci.yml.jinja2": (
            ".github/workflows/ci.yml"
        ),
    }

    created = []
    for template_name, output_path in (
        ts_templates.items()
    ):
        content = render_template(
            templates_dir, template_name, variables
        )
        file_path = target / output_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        created.append(output_path)

    return created


def render_none_files(
    target: Path,
    variables: dict[str, Any],
    templates_dir: Path,
) -> list[str]:
    """Render files for a skills-only (no toolchain) plugin.

    Skills-only plugins skip every Python and TypeScript toolchain
    artifact (no pyproject.toml, no package.json, no tests/conftest,
    no .python-version / .nvmrc). The only language-flavored file
    rendered here is the CI workflow, which still installs Python
    and Node so `make lint` can run end-to-end against the
    Markdown/YAML/REUSE checks.

    Args:
        target: Target directory path
        variables: Template variables
        templates_dir: Path to scaffold templates directory

    Returns:
        List of created file paths (relative to target)
    """
    none_templates = {
        "none/ci.yml.jinja2": ".github/workflows/ci.yml",
    }

    created = []
    for template_name, output_path in none_templates.items():
        content = render_template(
            templates_dir, template_name, variables
        )
        file_path = target / output_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        created.append(output_path)

    return created


def render_stub_agent(
    target: Path,
    name: str,
    description: str,
    extension_templates_dir: Path,
    timestamp: str = "",
    spdx_context: dict[str, str] | None = None,
) -> list[str]:
    """Render an agent stub using extension templates.

    Args:
        target: Target directory path
        name: Agent name (kebab-case)
        description: Agent description
        extension_templates_dir: Path to agent extension
            templates directory
        timestamp: ISO 8601 timestamp
        spdx_context: ``{year, copyright_holder, license_id}``
            used to render SPDX headers in generated files. If
            absent, defaults are computed via ``resolve_spdx_context``.

    Returns:
        List of created file paths (relative to target)
    """
    if not timestamp:
        from datetime import datetime, timezone

        timestamp = datetime.now(timezone.utc).isoformat()

    spdx = resolve_spdx_context(spdx_context or {})
    spdx_blocks = render_spdx_blocks(spdx)

    variables = {
        "name": name,
        "description": description,
        "version": "0.1.0",
        "tags": ["custom"],
        "timestamp": timestamp,
        **spdx,
        **spdx_blocks,
    }

    content = render_template(
        extension_templates_dir,
        "agent/agent.md.jinja2",
        variables,
    )

    agent_dir = target / "agents" / name
    agent_dir.mkdir(parents=True, exist_ok=True)

    agent_file = agent_dir / f"{name}.md"
    agent_file.write_text(content)

    # Create knowledge directory with a templated index. Rendered
    # via render_template (not an f-string) so the SPDX header
    # format stays in lock-step with the rest of the scaffolding.
    knowledge_dir = agent_dir / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    index_content = render_template(
        extension_templates_dir,
        "agent/knowledge-index.md.jinja2",
        variables,
    )
    (knowledge_dir / "index.md").write_text(index_content)

    return [
        f"agents/{name}/{name}.md",
        f"agents/{name}/knowledge/index.md",
    ]


def render_stub_skill(
    target: Path,
    name: str,
    description: str,
    language: str,
    extension_templates_dir: Path,
    timestamp: str = "",
    spdx_context: dict[str, str] | None = None,
) -> list[str]:
    """Render a skill stub using extension templates.

    Args:
        target: Target directory path
        name: Skill name (kebab-case)
        description: Skill description
        language: "python" or "typescript"
        extension_templates_dir: Path to skill extension
            templates directory
        timestamp: ISO 8601 timestamp
        spdx_context: ``{year, copyright_holder, license_id}``
            used to render SPDX headers in generated files. If
            absent, defaults are computed via ``resolve_spdx_context``.

    Returns:
        List of created file paths (relative to target)
    """
    if not timestamp:
        from datetime import datetime, timezone

        timestamp = datetime.now(timezone.utc).isoformat()

    script_extension = (
        ".py" if language == "python" else ".ts"
    )

    spdx = resolve_spdx_context(spdx_context or {})
    spdx_blocks = render_spdx_blocks(spdx)

    variables = {
        "name": name,
        "description": description,
        "version": "0.1.0",
        "tags": ["custom"],
        "timestamp": timestamp,
        "script_extension": script_extension,
        **spdx,
        **spdx_blocks,
    }

    content = render_template(
        extension_templates_dir,
        "skill/SKILL.md.jinja2",
        variables,
    )

    skill_dir = target / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content)

    # Create scripts and references dirs with .gitkeep
    for subdir in ("scripts", "references"):
        d = skill_dir / subdir
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitkeep").write_text("")

    return [
        f"skills/{name}/SKILL.md",
        f"skills/{name}/scripts/.gitkeep",
        f"skills/{name}/references/.gitkeep",
    ]


def assemble_gitignore(
    target: Path, language: str, templates_dir: Path
) -> str:
    """Assemble a .gitignore from shared + language blocks.

    Args:
        target: Target directory path
        language: "python", "typescript", or "none" (skills-only —
            no language-specific fragment added; only the shared
            patterns apply)
        templates_dir: Path to scaffold templates directory

    Returns:
        Path to created .gitignore (relative to target)
    """
    parts = []

    shared_content = render_template(
        templates_dir,
        "shared/gitignore-shared.jinja2",
        {},
    )
    parts.append(shared_content)

    if language == "python":
        lang_content = render_template(
            templates_dir,
            "python/gitignore-python.jinja2",
            {},
        )
        parts.append(lang_content)
    elif language == "typescript":
        lang_content = render_template(
            templates_dir,
            "typescript/gitignore-node.jinja2",
            {},
        )
        parts.append(lang_content)
    # language == "none": no language-specific fragment — the
    # shared block (OS, IDE, .claude/settings.local.json) is all a
    # skills-only plugin needs.

    gitignore_path = target / ".gitignore"
    gitignore_path.write_text("\n".join(parts))

    return ".gitignore"


def assemble_makefile(
    target: Path,
    language: str,
    variables: dict[str, Any],
    templates_dir: Path,
) -> str:
    """Assemble a Makefile from header + language targets.

    Args:
        target: Target directory path
        language: "python", "typescript", or "none" (skills-only —
            uses a stub fragment with `lint:` aggregate but no
            install/test targets for a language toolchain)
        variables: Template variables
        templates_dir: Path to scaffold templates directory

    Returns:
        Path to created Makefile (relative to target)
    """
    parts = []

    header = render_template(
        templates_dir,
        "shared/makefile-header.jinja2",
        variables,
    )
    parts.append(header)

    if language == "python":
        lang_targets = render_template(
            templates_dir,
            "python/makefile-python.jinja2",
            variables,
        )
    elif language == "typescript":
        lang_targets = render_template(
            templates_dir,
            "typescript/makefile-typescript.jinja2",
            variables,
        )
    else:  # "none" — skills-only plugin
        lang_targets = render_template(
            templates_dir,
            "none/makefile-none.jinja2",
            variables,
        )
    parts.append(lang_targets)

    makefile_path = target / "Makefile"
    makefile_path.write_text("\n".join(parts))

    return "Makefile"


def initialize_git(target: Path) -> bool:
    """Initialize a git repository in the target directory.

    Args:
        target: Target directory path

    Returns:
        True if git init succeeded
    """
    try:
        result = subprocess.run(
            ["git", "init"],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def create_initial_commit(target: Path) -> bool:
    """Create the initial commit in the scaffolded repo.

    Args:
        target: Target directory path

    Returns:
        True if commit succeeded
    """
    try:
        add_result = subprocess.run(
            ["git", "add", "."],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if add_result.returncode != 0:
            return False

        commit_result = subprocess.run(
            [
                "git",
                "commit",
                "-m",
                "Initial scaffold from aida-core "
                "plugin-manager",
            ],
            cwd=target,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return commit_result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
