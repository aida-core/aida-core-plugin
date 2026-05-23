# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Project context inference utilities for AIDA.

This module provides functionality to analyze project files and infer
user preferences, tools, and patterns automatically. This reduces the
number of questions AIDA needs to ask during installation.
"""

from pathlib import Path
from typing import Dict, Optional, Set, Any

from .files import file_exists, read_file, FileOperationError


# Security constants
MAX_SEARCH_DEPTH = 3  # Maximum directory depth for file searches

# Documentation level thresholds (character counts)
README_LENGTH_COMPREHENSIVE = 5000  # Indicates detailed documentation
README_LENGTH_STANDARD = 1000       # Indicates basic documentation


def safe_rglob(root: Path, pattern: str, max_depth: int = MAX_SEARCH_DEPTH) -> bool:
    """Safely search for files with depth limit and symlink protection.

    This function prevents path traversal attacks and resource exhaustion
    by limiting search depth, skipping symlinks, and returning on first match.

    Args:
        root: Root directory to search
        pattern: Glob pattern to match
        max_depth: Maximum directory depth (default: 3)

    Returns:
        True if at least one matching file exists, False otherwise

    Security:
        - Skips symbolic links to prevent circular reference attacks
        - Limits search depth to prevent deep directory DoS
        - Returns immediately on first match (early termination)
    """
    try:
        for path in root.rglob(pattern):
            # Skip symlinks to prevent circular references and traversal attacks
            if path.is_symlink():
                continue

            # Check depth limit
            try:
                depth = len(path.relative_to(root).parts)
                if depth > max_depth:
                    continue
            except ValueError:
                # Path is not relative to root (shouldn't happen with rglob)
                continue

            # Found at least one valid match
            return True

        return False
    except (OSError, PermissionError):
        # Handle filesystem errors gracefully
        return False


def detect_languages(project_root: Path) -> Set[str]:
    """Detect programming languages used in the project.

    Args:
        project_root: Root directory of the project

    Returns:
        Set of detected language names
    """
    languages = set()

    # Check for common language indicators
    indicators = {
        "Python": ["*.py", "requirements.txt", "setup.py", "pyproject.toml"],
        "JavaScript": ["*.js", "package.json", "*.mjs"],
        "TypeScript": ["*.ts", "*.tsx", "tsconfig.json"],
        "Go": ["*.go", "go.mod"],
        "Rust": ["*.rs", "Cargo.toml"],
        "Java": ["*.java", "pom.xml", "build.gradle"],
        "PHP": ["*.php", "composer.json"],
        "Ruby": ["*.rb", "Gemfile"],
        "C/C++": ["*.c", "*.cpp", "*.h", "CMakeLists.txt"],
    }

    for lang, patterns in indicators.items():
        for pattern in patterns:
            if pattern.startswith("*."):
                # File extension check - use safe search with deeper depth for monorepos
                if safe_rglob(project_root, pattern, max_depth=8):
                    languages.add(lang)
                    break
            else:
                # Specific file check
                if (project_root / pattern).exists():
                    languages.add(lang)
                    break

    return languages


def detect_tools(project_root: Path) -> Set[str]:
    """Detect development tools used in the project.

    Args:
        project_root: Root directory of the project

    Returns:
        Set of detected tool names
    """
    tools = set()

    # Version control
    if (project_root / ".git").exists():
        tools.add("Git")

    # Containers
    if (project_root / "Dockerfile").exists() or (project_root / "docker-compose.yml").exists():
        tools.add("Docker")

    # CI/CD
    if (project_root / ".github" / "workflows").exists():
        tools.add("GitHub Actions")
    if (project_root / ".gitlab-ci.yml").exists():
        tools.add("GitLab CI")
    if (project_root / "Jenkinsfile").exists():
        tools.add("Jenkins")

    # Testing frameworks
    if file_exists(project_root / "pytest.ini") or file_exists(project_root / "setup.cfg"):
        try:
            if "pytest" in read_file(project_root / "requirements.txt"):
                tools.add("pytest")
        except (FileOperationError, IOError, OSError):
            pass

    if (project_root / "package.json").exists():
        try:
            content = read_file(project_root / "package.json")
            if "jest" in content:
                tools.add("Jest")
            if "vitest" in content:
                tools.add("Vitest")
        except (FileOperationError, IOError, OSError):
            pass

    # Editors (from dotfiles)
    if (project_root / ".vscode").exists():
        tools.add("VS Code")
    if (project_root / ".idea").exists():
        tools.add("IntelliJ/PyCharm")

    return tools


def detect_coding_standards(project_root: Path) -> Optional[str]:
    """Infer coding standards from project configuration files.

    Args:
        project_root: Root directory of the project

    Returns:
        Inferred coding standards string, or None if cannot determine
    """
    standards = []

    # Python standards
    if (project_root / "pyproject.toml").exists():
        try:
            content = read_file(project_root / "pyproject.toml")
            if "black" in content:
                standards.append("Black")
            if "flake8" in content or "tool.flake8" in content:
                standards.append("flake8")
            if "mypy" in content:
                standards.append("mypy type checking")
        except (FileOperationError, IOError, OSError):
            pass

    if (project_root / ".editorconfig").exists():
        standards.append("EditorConfig")

    # JavaScript/TypeScript
    if (project_root / ".eslintrc.json").exists() or (project_root / ".eslintrc.js").exists():
        try:
            content = read_file(project_root / ".eslintrc.json")
            if "airbnb" in content:
                standards.append("Airbnb style")
            elif "standard" in content:
                standards.append("Standard JS")
            else:
                standards.append("ESLint")
        except (FileOperationError, IOError, OSError):
            standards.append("ESLint")

    if (project_root / ".prettierrc").exists():
        standards.append("Prettier")

    # PHP
    if (project_root / "phpcs.xml").exists():
        standards.append("PHP CodeSniffer")

    if standards:
        return ", ".join(standards)

    return None


def detect_testing_approach(project_root: Path) -> Optional[str]:
    """Infer testing approach from project structure and configuration.

    Args:
        project_root: Root directory of the project

    Returns:
        Inferred testing approach, or None if cannot determine
    """
    # Check for test directories
    test_dirs = ["tests/", "test/", "spec/", "__tests__/"]
    has_tests = any((project_root / d).exists() for d in test_dirs)

    if not has_tests:
        return "Minimal - manual testing only"

    # Check for TDD indicators
    if (project_root / "pytest.ini").exists():
        try:
            content = read_file(project_root / "pytest.ini")
            if "coverage" in content:
                return "Comprehensive unit + integration tests"
        except (FileOperationError, IOError, OSError):
            pass
        return "Unit tests for critical paths"

    # Check for BDD frameworks
    if file_exists(project_root / "features"):
        return "BDD - behavior-driven development"

    if has_tests:
        return "Unit tests for critical paths"

    return None


def _detect_language_families(project_root: Path) -> list:
    """Detect language ecosystems present in the project (#86).

    Scans for canonical manifest files and returns the set of
    language families found. Used as a fallback when framework-
    specific detection doesn't match a recognizable pattern.

    Returns:
        Sorted list of language family strings (deterministic
        order for multi-language repos). Empty list if no
        manifest files are found.
    """
    langs = []

    # Node ecosystem: distinguish TypeScript vs JavaScript by
    # tsconfig.json presence. Both share package.json.
    if (project_root / "package.json").exists():
        if (project_root / "tsconfig.json").exists():
            langs.append("Node/TypeScript")
        else:
            langs.append("Node/JavaScript")

    # Python: pyproject.toml is the modern marker; fall back to
    # legacy setup.py / requirements.txt without double-counting
    # if pyproject.toml is also present.
    if (project_root / "pyproject.toml").exists():
        langs.append("Python")
    elif (
        (project_root / "setup.py").exists()
        or (project_root / "requirements.txt").exists()
    ):
        langs.append("Python")

    # Other ecosystems — single canonical manifest per language
    if (project_root / "Cargo.toml").exists():
        langs.append("Rust")
    if (project_root / "go.mod").exists():
        langs.append("Go")
    if (project_root / "Gemfile").exists():
        langs.append("Ruby")
    if (project_root / "composer.json").exists():
        langs.append("PHP")

    return sorted(langs)


def detect_project_type(project_root: Path) -> Optional[str]:
    """Infer project type from structure and configuration.

    Args:
        project_root: Root directory of the project

    Returns:
        Inferred project type, or None if cannot determine
    """
    # Web application indicators
    if (project_root / "package.json").exists():
        try:
            content = read_file(project_root / "package.json")
            if "next" in content or "react" in content:
                return "Web application (frontend)"
            if "express" in content or "fastify" in content:
                return "Web application (backend)"
        except (FileOperationError, IOError, OSError):
            pass

    # Python web frameworks
    if any((project_root / f).exists() for f in ["manage.py", "app.py", "main.py"]):
        try:
            for f in ["manage.py", "app.py", "main.py"]:
                if (project_root / f).exists():
                    content = read_file(project_root / f)
                    if "django" in content.lower():
                        return "Web application (backend)"
                    if "flask" in content.lower():
                        return "Web application (backend)"
                    if "fastapi" in content.lower():
                        return "Web application (backend)"
        except (FileOperationError, IOError, OSError):
            pass

    # CLI tool
    if (project_root / "setup.py").exists() or (project_root / "pyproject.toml").exists():
        try:
            content = ""
            if (project_root / "setup.py").exists():
                content = read_file(project_root / "setup.py")
            elif (project_root / "pyproject.toml").exists():
                content = read_file(project_root / "pyproject.toml")

            if "console_scripts" in content or "entry_points" in content:
                return "CLI tool or utility"
        except (FileOperationError, IOError, OSError):
            pass

    # Library
    if (project_root / "setup.py").exists() or (project_root / "__init__.py").exists():
        return "Library or framework"

    # Language-family fallback (#86): when no specific framework
    # / artifact pattern matches but the project clearly uses one
    # or more known languages, return that rather than letting
    # the auto-generated SKILL.md claim "Unknown" on every
    # multi-language repo.
    langs = _detect_language_families(project_root)
    if langs:
        return " + ".join(langs)

    return None


def detect_project_structure(project_root: Path) -> Dict[str, Any]:
    """Detect comprehensive project structure and organization facts.

    This function detects FACTS about the project structure, not preferences.
    It looks for existing files and directories to understand how the project
    is organized.

    Args:
        project_root: Root directory of the project

    Returns:
        Dictionary containing detected project structure facts
    """
    structure = {}

    # Documentation directories
    docs_candidates = ["docs/", "doc/", "documentation/", "wiki/"]
    for candidate in docs_candidates:
        if (project_root / candidate).is_dir():
            structure["docs_directory"] = candidate
            structure["has_docs_directory"] = True
            break
    else:
        structure["has_docs_directory"] = False
        structure["docs_directory"] = None

    # Changelog detection
    changelog_files = [
        "CHANGELOG.md", "CHANGELOG.rst", "CHANGELOG.txt",
        "HISTORY.md", "HISTORY.rst",
        "NEWS.md", "RELEASES.md"
    ]
    found_changelogs = []
    for changelog in changelog_files:
        if (project_root / changelog).exists():
            found_changelogs.append(changelog)

    structure["has_changelog"] = len(found_changelogs) > 0
    structure["changelog_files"] = found_changelogs

    # Docker detection
    structure["has_dockerfile"] = (project_root / "Dockerfile").exists()
    structure["has_docker_compose"] = (
        (project_root / "docker-compose.yml").exists() or
        (project_root / "docker-compose.yaml").exists()
    )
    structure["uses_docker"] = structure["has_dockerfile"] or structure["has_docker_compose"]

    # Testing directories
    test_directories = []
    test_candidates = ["tests/", "test/", "spec/", "__tests__/"]
    for candidate in test_candidates:
        if (project_root / candidate).is_dir():
            test_directories.append(candidate)

    structure["has_tests"] = len(test_directories) > 0
    structure["test_directories"] = test_directories

    # Source code organization
    src_directories = []
    src_candidates = ["src/", "lib/", "pkg/", "app/"]
    for candidate in src_candidates:
        if (project_root / candidate).is_dir():
            src_directories.append(candidate)

    structure["has_src_directory"] = len(src_directories) > 0
    structure["src_directories"] = src_directories

    # CI/CD detection
    structure["has_github_actions"] = (project_root / ".github" / "workflows").is_dir()
    structure["has_gitlab_ci"] = (project_root / ".gitlab-ci.yml").exists()
    structure["has_ci_cd"] = structure["has_github_actions"] or structure["has_gitlab_ci"]

    # Package management files
    structure["has_package_json"] = (project_root / "package.json").exists()
    structure["has_requirements_txt"] = (project_root / "requirements.txt").exists()
    structure["has_pyproject_toml"] = (project_root / "pyproject.toml").exists()
    structure["has_gemfile"] = (project_root / "Gemfile").exists()
    structure["has_go_mod"] = (project_root / "go.mod").exists()
    structure["has_cargo_toml"] = (project_root / "Cargo.toml").exists()

    # README detection
    readme_files = ["README.md", "README.rst", "README.txt", "README"]
    for readme in readme_files:
        if (project_root / readme).exists():
            structure["has_readme"] = True
            structure["readme_file"] = readme
            try:
                content = read_file(project_root / readme)
                structure["readme_length"] = len(content)
            except (FileOperationError, IOError, OSError):
                structure["readme_length"] = 0
            break
    else:
        structure["has_readme"] = False
        structure["readme_file"] = None
        structure["readme_length"] = 0

    # License detection
    license_files = ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"]
    for lic_file in license_files:
        if (project_root / lic_file).exists():
            structure["has_license"] = True
            structure["license_file"] = lic_file
            break
    else:
        structure["has_license"] = False
        structure["license_file"] = None

    # Contributing guide
    structure["has_contributing"] = (
        (project_root / "CONTRIBUTING.md").exists() or
        (project_root / "CONTRIBUTING.rst").exists()
    )

    # Version control detection
    if (project_root / ".git").is_dir():
        structure["vcs"] = "git"
        structure["has_vcs"] = True
    elif (project_root / ".hg").is_dir():
        structure["vcs"] = "mercurial"
        structure["has_vcs"] = True
    elif (project_root / ".svn").is_dir():
        structure["vcs"] = "svn"
        structure["has_vcs"] = True
    else:
        structure["vcs"] = None
        structure["has_vcs"] = False

    # Git-specific checks (if using git)
    if structure["vcs"] == "git":
        structure["has_gitignore"] = (project_root / ".gitignore").exists()
        structure["has_gitattributes"] = (project_root / ".gitattributes").exists()
    else:
        structure["has_gitignore"] = False
        structure["has_gitattributes"] = False

    return structure


def infer_preferences(context: Dict[str, Any]) -> Dict[str, Any]:
    """Infer project facts from project context.

    IMPORTANT: This function now returns FACTS about the project,
    not preferences or opinions. All detected information should be
    verifiable and objective.

    This is the main inference function that analyzes the project and
    returns inferred values for questionnaire questions.

    Args:
        context: Project context dictionary containing:
            - project_root: Path to project root
            - files_analyzed: List of files analyzed by AIDA
            - readme_content: README content if available

    Returns:
        Dictionary of inferred project facts
    """
    inferred = {}
    project_root = Path(context.get("project_root", "."))

    # Detect languages and tools (FACTS)
    languages = detect_languages(project_root)
    tools = detect_tools(project_root)

    # Store as facts
    inferred["languages"] = ", ".join(sorted(languages)) if languages else "Unknown"
    inferred["tools"] = ", ".join(sorted(tools)) if tools else "None detected"

    # Detect coding standards (FACTS - what's actually configured)
    standards = detect_coding_standards(project_root)
    if standards:
        inferred["coding_standards"] = standards

    # Detect testing approach (FACT - what's currently set up)
    testing = detect_testing_approach(project_root)
    if testing:
        inferred["testing_approach"] = testing

    # Detect project type (FACT - based on actual structure)
    proj_type = detect_project_type(project_root)
    if proj_type:
        inferred["project_type"] = proj_type

    # Detect comprehensive project structure (ALL FACTS)
    structure = detect_project_structure(project_root)
    inferred.update(structure)

    # Documentation level from README (FACT - actual length)
    if inferred.get("readme_length", 0) > README_LENGTH_COMPREHENSIVE:
        inferred["documentation_level"] = "Comprehensive - Full guides, examples, architecture docs"
    elif inferred.get("readme_length", 0) > README_LENGTH_STANDARD:
        inferred["documentation_level"] = "Standard - README, API docs, inline comments"
    elif inferred.get("has_readme"):
        inferred["documentation_level"] = "Minimal - README and inline comments"

    # Detect team collaboration (INFER from project structure)
    if inferred.get("has_contributing") or inferred.get("has_github_actions"):
        inferred["team_collaboration"] = "Open source with external contributors"
    elif inferred.get("has_ci_cd"):
        inferred["team_collaboration"] = "Small team (2-5 people) with frequent sync"
    else:
        inferred["team_collaboration"] = "Solo project - just me"

    return inferred
