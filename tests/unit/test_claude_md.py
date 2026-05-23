# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for claude-md-manager CLAUDE.md operations.

This test suite covers the operations/claude_md.py module functionality including
CLAUDE.md detection, validation, audit scoring, and management operations.
"""

import sys
import unittest
import json
import tempfile
import shutil
from pathlib import Path
from unittest import mock

# Add scripts directories to path for imports
_project_root = Path(__file__).parent.parent.parent
SKILL_DIR = _project_root / "skills" / "claude-md-manager"
sys.path.insert(0, str(_project_root / "scripts"))
sys.path.insert(0, str(SKILL_DIR / "scripts"))
TEMPLATES_DIR = SKILL_DIR / "templates"

# Clear cached operations modules to avoid cross-manager conflicts in pytest
for _mod_name in list(sys.modules):
    if _mod_name == "operations" or _mod_name.startswith("operations."):
        del sys.modules[_mod_name]
sys.modules.pop("_paths", None)

from operations.utils import (  # noqa: E402
    get_project_root,
    parse_frontmatter,
    safe_json_load,
)
from operations.claude_md import (  # noqa: E402
    get_claude_md_path,
    find_claude_md,
    detect_sections,
    extract_commands_from_makefile,
    extract_commands_from_package_json,
    extract_readme_description,
    detect_project_context,
    validate_claude_md,
    calculate_audit_score,
    generate_audit_findings,
    get_questions,
    execute,
)

_ops_snapshot = {
    k: v for k, v in sys.modules.items()
    if k == "operations" or k.startswith("operations.")
}


class TestGetProjectRoot(unittest.TestCase):
    """Test project root detection."""

    def test_finds_git_root(self):
        """Test that get_project_root returns a valid path."""
        root = get_project_root()
        self.assertIsInstance(root, Path)
        self.assertTrue(root.exists())


class TestGetClaudeMdPath(unittest.TestCase):
    """Test CLAUDE.md path resolution."""

    def test_user_scope(self):
        """Test user scope returns home directory path."""
        path = get_claude_md_path("user")
        self.assertEqual(path.parent.name, ".claude")
        self.assertEqual(path.name, "CLAUDE.md")

    def test_project_scope(self):
        """Test project scope returns project root path."""
        path = get_claude_md_path("project")
        self.assertEqual(path.name, "CLAUDE.md")

    def test_plugin_scope(self):
        """Test plugin scope returns plugin directory path."""
        path = get_claude_md_path("plugin")
        self.assertEqual(path.parent.name, ".claude-plugin")


class TestFindClaudeMd(unittest.TestCase):
    """Test CLAUDE.md file discovery."""

    def test_find_all_scope(self):
        """Test finding all CLAUDE.md files."""
        files = find_claude_md("all")
        self.assertIsInstance(files, list)

    def test_find_user_scope(self):
        """Test finding user CLAUDE.md."""
        files = find_claude_md("user")
        self.assertIsInstance(files, list)

    def test_file_info_structure(self):
        """Test that found files have correct structure."""
        files = find_claude_md("all")
        for f in files:
            self.assertIn("scope", f)
            self.assertIn("path", f)
            self.assertIn("exists", f)


class TestParseFrontmatter(unittest.TestCase):
    """Test YAML frontmatter parsing."""

    def test_basic_frontmatter(self):
        """Test parsing basic frontmatter."""
        content = """---
type: documentation
title: Test CLAUDE.md
description: Test description
---

# Test Content

Body here."""

        frontmatter, body = parse_frontmatter(content)

        self.assertEqual(frontmatter["type"], "documentation")
        self.assertEqual(frontmatter["title"], "Test CLAUDE.md")
        self.assertIn("Test Content", body)

    def test_no_frontmatter(self):
        """Test parsing content without frontmatter."""
        content = "# Just Content\n\nNo frontmatter here."

        frontmatter, body = parse_frontmatter(content)

        self.assertEqual(frontmatter, {})
        self.assertEqual(body, content)

    def test_empty_content(self):
        """Test parsing empty content."""
        frontmatter, body = parse_frontmatter("")

        self.assertEqual(frontmatter, {})
        self.assertEqual(body, "")

    def test_frontmatter_with_quoted_values(self):
        """Test parsing quoted values in frontmatter."""
        content = """---
title: "Test Title"
description: 'Single quoted'
---

Body."""

        frontmatter, body = parse_frontmatter(content)

        self.assertEqual(frontmatter["title"], "Test Title")
        self.assertEqual(frontmatter["description"], "Single quoted")


class TestDetectSections(unittest.TestCase):
    """Test section detection in CLAUDE.md content."""

    def test_detect_overview(self):
        """Test detection of overview section."""
        content = "## Project Overview\n\nDescription here."
        sections = detect_sections(content)
        self.assertIn("overview", sections)

    def test_detect_commands(self):
        """Test detection of commands section."""
        content = "## Key Commands\n\n```bash\nmake test\n```"
        sections = detect_sections(content)
        self.assertIn("commands", sections)

    def test_detect_architecture(self):
        """Test detection of architecture section."""
        content = "## Architecture\n\nSystem design."
        sections = detect_sections(content)
        self.assertIn("architecture", sections)

    def test_detect_conventions(self):
        """Test detection of conventions section."""
        content = "## Coding Conventions\n\nStyle guide."
        sections = detect_sections(content)
        self.assertIn("conventions", sections)

    def test_detect_constraints(self):
        """Test detection of constraints section."""
        content = "## Important Constraints\n\nLimitations."
        sections = detect_sections(content)
        self.assertIn("constraints", sections)

    def test_detect_multiple_sections(self):
        """Test detection of multiple sections."""
        content = """## Overview

Project desc.

## Key Commands

```bash
make test
```

## Architecture

System design.
"""
        sections = detect_sections(content)
        self.assertIn("overview", sections)
        self.assertIn("commands", sections)
        self.assertIn("architecture", sections)


class TestExtractCommandsFromMakefile(unittest.TestCase):
    """Test command extraction from Makefile."""

    def setUp(self):
        """Set up temporary directory with test Makefile."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_basic_targets(self):
        """Test extracting basic make targets."""
        makefile_content = """
test:  # Run tests
	pytest

build:  # Build project
	npm run build

lint:
	flake8
"""
        (self.temp_path / "Makefile").write_text(makefile_content)

        commands = extract_commands_from_makefile(self.temp_path)

        self.assertTrue(len(commands) >= 2)
        command_names = [c["command"] for c in commands]
        self.assertIn("make test", command_names)
        self.assertIn("make build", command_names)

    def test_skip_internal_targets(self):
        """Test that internal targets are skipped."""
        makefile_content = """
.PHONY: all
_internal:
	echo internal

test:  # Run tests
	pytest
"""
        (self.temp_path / "Makefile").write_text(makefile_content)

        commands = extract_commands_from_makefile(self.temp_path)

        command_names = [c["command"] for c in commands]
        self.assertNotIn("make .PHONY", command_names)
        self.assertNotIn("make _internal", command_names)

    def test_no_makefile(self):
        """Test handling when no Makefile exists."""
        commands = extract_commands_from_makefile(self.temp_path)
        self.assertEqual(commands, [])


class TestExtractCommandsFromPackageJson(unittest.TestCase):
    """Test command extraction from package.json."""

    def setUp(self):
        """Set up temporary directory with test package.json."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_npm_scripts(self):
        """Test extracting npm scripts."""
        package_json = {
            "name": "test-project",
            "scripts": {
                "test": "jest",
                "build": "webpack",
                "start": "node server.js"
            }
        }
        (self.temp_path / "package.json").write_text(json.dumps(package_json))

        commands = extract_commands_from_package_json(self.temp_path)

        self.assertTrue(len(commands) >= 2)
        command_names = [c["command"] for c in commands]
        self.assertIn("npm run test", command_names)
        self.assertIn("npm run build", command_names)

    def test_skip_hook_scripts(self):
        """Test that pre/post hooks are skipped."""
        package_json = {
            "scripts": {
                "test": "jest",
                "pretest": "npm run lint",
                "postbuild": "npm run deploy"
            }
        }
        (self.temp_path / "package.json").write_text(json.dumps(package_json))

        commands = extract_commands_from_package_json(self.temp_path)

        command_names = [c["command"] for c in commands]
        self.assertNotIn("npm run pretest", command_names)
        self.assertNotIn("npm run postbuild", command_names)

    def test_no_package_json(self):
        """Test handling when no package.json exists."""
        commands = extract_commands_from_package_json(self.temp_path)
        self.assertEqual(commands, [])


class TestExtractReadmeDescription(unittest.TestCase):
    """Test README description extraction."""

    def setUp(self):
        """Set up temporary directory with test README."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_first_paragraph(self):
        """Test extracting first paragraph from README."""
        readme_content = """# Test Project

This is the project description that should be extracted.

## Installation

Install instructions here.
"""
        (self.temp_path / "README.md").write_text(readme_content)

        description = extract_readme_description(self.temp_path)

        self.assertIsNotNone(description)
        self.assertIn("project description", description)

    def test_skip_frontmatter(self):
        """Test that frontmatter is skipped."""
        readme_content = """---
title: Test
---

# Project Name

Actual description here.
"""
        (self.temp_path / "README.md").write_text(readme_content)

        description = extract_readme_description(self.temp_path)

        self.assertIsNotNone(description)
        self.assertIn("description", description.lower())

    def test_no_readme(self):
        """Test handling when no README exists."""
        description = extract_readme_description(self.temp_path)
        self.assertIsNone(description)


class TestDetectProjectContext(unittest.TestCase):
    """Test project context detection."""

    def setUp(self):
        """Set up temporary directory with test project files."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_python_project(self):
        """Test detection of Python project."""
        (self.temp_path / "pyproject.toml").write_text("[project]\nname = 'test'")

        context = detect_project_context(self.temp_path)

        self.assertIn("Python", context["languages"])

    def test_detect_javascript_project(self):
        """Test detection of JavaScript project."""
        (self.temp_path / "package.json").write_text('{"name": "test"}')

        context = detect_project_context(self.temp_path)

        self.assertIn("JavaScript", context["languages"])

    def test_detect_typescript_project(self):
        """Test detection of TypeScript project."""
        (self.temp_path / "package.json").write_text('{"name": "test"}')
        (self.temp_path / "tsconfig.json").write_text('{}')

        context = detect_project_context(self.temp_path)

        self.assertIn("TypeScript", context["languages"])

    def test_detect_git_tool(self):
        """Test detection of Git."""
        (self.temp_path / ".git").mkdir()

        context = detect_project_context(self.temp_path)

        self.assertIn("Git", context["tools"])

    def test_detect_docker_tool(self):
        """Test detection of Docker."""
        (self.temp_path / "Dockerfile").write_text("FROM alpine")

        context = detect_project_context(self.temp_path)

        self.assertIn("Docker", context["tools"])

    def test_project_name_from_path(self):
        """Test that project name is extracted from path."""
        context = detect_project_context(self.temp_path)

        self.assertEqual(context["name"], self.temp_path.name)


class TestValidateClaudeMd(unittest.TestCase):
    """Test CLAUDE.md validation."""

    def setUp(self):
        """Set up temporary directory with test CLAUDE.md."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_validate_complete_file(self):
        """Test validation of a complete CLAUDE.md file."""
        content = """---
type: documentation
title: Test CLAUDE.md
---

# CLAUDE.md

## Project Overview

Test project description.

## Key Commands

```bash
make test
```
"""
        claude_md = self.temp_path / "CLAUDE.md"
        claude_md.write_text(content)

        results = validate_claude_md(claude_md)

        self.assertTrue(results["valid"])
        self.assertEqual(len(results["errors"]), 0)

    def test_validate_missing_frontmatter(self):
        """Test validation warns about missing frontmatter."""
        content = """# CLAUDE.md

## Project Overview

Description.

## Key Commands

```bash
make test
```
"""
        claude_md = self.temp_path / "CLAUDE.md"
        claude_md.write_text(content)

        results = validate_claude_md(claude_md)

        self.assertIn("Missing frontmatter", results["checks"]["structure"]["details"])

    def test_validate_missing_required_sections(self):
        """Test validation fails when missing required sections."""
        content = """---
type: documentation
---

# CLAUDE.md

Just some content without proper sections.
"""
        claude_md = self.temp_path / "CLAUDE.md"
        claude_md.write_text(content)

        results = validate_claude_md(claude_md)

        self.assertFalse(results["valid"])
        self.assertTrue(len(results["errors"]) > 0)

    def test_validate_user_scope_no_required_sections(self):
        """User-scope files don't need overview/commands sections.

        Regression for #99: previously the validator applied
        project-scope required-sections to every file, so a perfectly
        well-formed user-scope CLAUDE.md (Default Behaviors / Patterns
        / Tool Config) was flagged invalid. User-scope is free-form
        preferences and has no required sections.
        """
        content = """---
type: documentation
title: User CLAUDE.md
---

# CLAUDE.md

## Default Behaviors

Be terse.

## Cross-Project Patterns

Conventional commits.

## Editor/Tool Configuration

VS Code.
"""
        claude_md = self.temp_path / "CLAUDE.md"
        claude_md.write_text(content)

        results = validate_claude_md(claude_md, scope="user")

        self.assertTrue(
            results["valid"],
            f"user-scope should be valid; got errors: {results['errors']}",
        )
        self.assertEqual(results["errors"], [])

    def test_validate_plugin_scope_no_required_sections(self):
        """Plugin-scope files don't need overview/commands either.

        Same #99 family: plugin-scope templates don't ship an Overview
        or Key Commands section, so requiring them produced false
        negatives on the scaffold's own output.
        """
        content = """---
type: documentation
title: Demo Plugin
---

# Demo Plugin

## Usage

Run things.
"""
        claude_md = self.temp_path / "CLAUDE.md"
        claude_md.write_text(content)

        results = validate_claude_md(claude_md, scope="plugin")

        self.assertTrue(
            results["valid"],
            f"plugin-scope should be valid; got errors: {results['errors']}",
        )

    def test_validate_project_scope_still_requires_sections(self):
        """Project-scope keeps the existing overview/commands requirement.

        Guard against the #99 fix accidentally relaxing project-scope
        validation, which is the most common case.
        """
        content = """---
type: documentation
---

# CLAUDE.md

Just some content without proper sections.
"""
        claude_md = self.temp_path / "CLAUDE.md"
        claude_md.write_text(content)

        results = validate_claude_md(claude_md, scope="project")

        self.assertFalse(results["valid"])
        joined_errors = " ".join(results["errors"])
        self.assertIn("overview", joined_errors)
        self.assertIn("commands", joined_errors)

    def test_validate_nonexistent_file(self):
        """Test validation handles nonexistent file."""
        results = validate_claude_md(self.temp_path / "nonexistent.md")

        self.assertFalse(results["valid"])
        self.assertIn("does not exist", results["errors"][0])

    def test_validate_sensitive_data_warning(self):
        """Test validation warns about potential sensitive data."""
        content = """---
type: documentation
---

# CLAUDE.md

## Project Overview

Test project.

## Key Commands

```bash
API_KEY="sk-12345678"
```
"""
        claude_md = self.temp_path / "CLAUDE.md"
        claude_md.write_text(content)

        results = validate_claude_md(claude_md)

        warning_present = any("sensitive" in w.lower() for w in results["warnings"])
        self.assertTrue(warning_present)


class TestCalculateAuditScore(unittest.TestCase):
    """Test audit score calculation."""

    def test_perfect_score_components(self):
        """Test that a well-structured file scores high."""
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "checks": {
                "structure": {"pass": True, "details": ""},
                "consistency": {"pass": True, "details": ""},
                "best_practices": {"pass": True, "details": ""},
                "alignment": {"pass": True, "details": ""},
            }
        }
        sections = ["overview", "commands", "architecture", "conventions", "constraints"]

        score = calculate_audit_score(results, sections)

        self.assertGreaterEqual(score, 90)

    def test_errors_reduce_score(self):
        """Test that errors reduce the score."""
        results = {
            "valid": False,
            "errors": ["error1", "error2"],
            "warnings": [],
            "checks": {
                "structure": {"pass": False, "details": ""},
                "consistency": {"pass": True, "details": ""},
                "best_practices": {"pass": True, "details": ""},
                "alignment": {"pass": True, "details": ""},
            }
        }
        sections = []

        score = calculate_audit_score(results, sections)

        self.assertLess(score, 70)

    def test_score_bounded_0_100(self):
        """Test that score is always between 0 and 100."""
        results = {
            "valid": False,
            "errors": ["e1", "e2", "e3", "e4", "e5", "e6", "e7", "e8", "e9", "e10"],
            "warnings": ["w1", "w2", "w3", "w4", "w5"],
            "checks": {
                "structure": {"pass": False, "details": ""},
                "consistency": {"pass": False, "details": ""},
                "best_practices": {"pass": False, "details": ""},
                "alignment": {"pass": False, "details": ""},
            }
        }
        sections = []

        score = calculate_audit_score(results, sections)

        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


class TestGenerateAuditFindings(unittest.TestCase):
    """Test audit findings generation."""

    def setUp(self):
        """Set up temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_findings_for_missing_overview(self):
        """Test findings include missing overview."""
        claude_md = self.temp_path / "CLAUDE.md"
        content = """## Key Commands

```bash
make test
```
"""
        claude_md.write_text(content)
        validation = validate_claude_md(claude_md)
        detected = {"description": "Test project", "commands": [], "languages": []}

        findings = generate_audit_findings(claude_md, content, validation, detected)

        finding_ids = [f["id"] for f in findings]
        self.assertIn("missing-overview", finding_ids)

    def test_findings_for_missing_commands(self):
        """Test findings include missing commands."""
        claude_md = self.temp_path / "CLAUDE.md"
        content = """## Project Overview

Test description.
"""
        claude_md.write_text(content)
        validation = validate_claude_md(claude_md)
        detected = {"description": "Test", "commands": [], "languages": []}

        findings = generate_audit_findings(claude_md, content, validation, detected)

        finding_ids = [f["id"] for f in findings]
        self.assertIn("missing-commands", finding_ids)

    def test_findings_include_fix_suggestions(self):
        """Test that findings include fix suggestions."""
        claude_md = self.temp_path / "CLAUDE.md"
        content = "## Something Else"
        claude_md.write_text(content)
        validation = validate_claude_md(claude_md)
        detected = {
            "description": "Test project",
            "commands": [{"command": "make test", "description": "Run tests"}],
            "languages": ["Python"]
        }

        findings = generate_audit_findings(claude_md, content, validation, detected)

        critical_findings = [f for f in findings if f["category"] == "critical"]
        for f in critical_findings:
            if f.get("fix"):
                self.assertIn("content", f["fix"])


class TestGetQuestions(unittest.TestCase):
    """Test question generation."""

    def test_create_without_scope(self):
        """Test create operation asks for scope when not provided."""
        context = {"operation": "create"}
        result = get_questions(context)

        question_ids = [q["id"] for q in result["questions"]]
        self.assertIn("scope", question_ids)

    def test_create_with_scope(self):
        """Test create operation infers context when scope provided."""
        context = {"operation": "create", "scope": "project"}
        result = get_questions(context)

        self.assertIn("inferred", result)

    def test_list_no_questions(self):
        """Test list operation doesn't need questions."""
        context = {"operation": "list", "scope": "all"}
        result = get_questions(context)

        self.assertEqual(len(result["questions"]), 0)

    def test_validate_no_questions(self):
        """Test validate operation returns results directly."""
        context = {"operation": "validate", "scope": "all"}
        result = get_questions(context)

        self.assertIn("inferred", result)


class TestExecute(unittest.TestCase):
    """Test operation execution."""

    def test_execute_list(self):
        """Test list operation execution."""
        context = {"operation": "list", "scope": "all"}
        result = execute(context, {}, TEMPLATES_DIR)

        self.assertTrue(result["success"])
        self.assertIn("files", result)
        self.assertIn("count", result)

    def test_execute_validate(self):
        """Test validate operation execution."""
        context = {"operation": "validate", "scope": "all"}
        result = execute(context, {}, TEMPLATES_DIR)

        self.assertTrue(result["success"])
        self.assertIn("results", result)

    def test_execute_unknown_operation(self):
        """Test unknown operation fails."""
        context = {"operation": "unknown"}
        result = execute(context, {}, TEMPLATES_DIR)

        self.assertFalse(result["success"])
        self.assertIn("Unknown operation", result["message"])


class TestExecuteCreate(unittest.TestCase):
    """Test create operation execution."""

    def setUp(self):
        """Set up temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        # Create .git to make it look like a project root
        (self.temp_path / ".git").mkdir()
        self.original_cwd = Path.cwd()

    def tearDown(self):
        """Clean up temporary directory."""
        import os
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_without_overwrite_fails_for_existing(self):
        """Test create fails when file exists without overwrite."""
        import os
        os.chdir(self.temp_path)

        # Create existing CLAUDE.md
        (self.temp_path / "CLAUDE.md").write_text("# Existing")

        context = {"operation": "create", "scope": "project"}
        result = execute(context, {}, TEMPLATES_DIR)

        self.assertFalse(result["success"])
        self.assertIn("already exists", result["message"])

    def test_create_user_scope_persists_responses(self):
        """User-scope create wires --responses payload into template_vars.

        Regression for #98: previously execute_create only built
        template_vars from project-scope keys, so user-scope responses
        (default_behaviors / patterns / tool_config) were silently
        dropped and the file rendered with placeholder text while the
        operation still returned success:true.
        """
        import os
        os.chdir(self.temp_path)

        fake_home = self.temp_path / "fake_home"
        (fake_home / ".claude").mkdir(parents=True)

        responses = {
            "default_behaviors": "Be terse. No emojis.",
            "patterns": "Conventional commits everywhere.",
            "tool_config": "VS Code; iTerm2; 1Password CLI.",
        }
        context = {"operation": "create", "scope": "user"}

        with mock.patch.object(Path, "home", return_value=fake_home):
            result = execute(context, responses, TEMPLATES_DIR)

        self.assertTrue(result["success"], result.get("message"))

        written = (fake_home / ".claude" / "CLAUDE.md").read_text()
        self.assertIn("Be terse. No emojis.", written)
        self.assertIn("Conventional commits everywhere.", written)
        self.assertIn("VS Code; iTerm2; 1Password CLI.", written)
        # And the placeholder text must NOT be there
        self.assertNotIn(
            "Add your preferred default behaviors here.", written
        )

    def test_create_plugin_scope_persists_responses(self):
        """Plugin-scope create wires --responses into template_vars.

        Same root cause as #98: plugin.md.jinja2 references plugin_type,
        provides, usage, config_options, extension_points — none were
        threaded through before. Covered here to prevent the same
        regression in the plugin-scope path.
        """
        import os
        os.chdir(self.temp_path)
        (self.temp_path / ".claude-plugin").mkdir()

        responses = {
            "plugin_type": "Skill collection",
            "provides": ["agent-manager", "skill-manager"],
            "usage": "Invoke /aida agent create to scaffold an agent.",
            "config_options": "No runtime config — operates on files.",
            "extension_points": "Drop new templates in templates/.",
        }
        context = {
            "operation": "create",
            "scope": "plugin",
            "name": "Demo Plugin",
            "description": "Demo plugin for testing.",
        }

        result = execute(context, responses, TEMPLATES_DIR)
        self.assertTrue(result["success"], result.get("message"))

        written = (
            self.temp_path / ".claude-plugin" / "CLAUDE.md"
        ).read_text()
        self.assertIn("Skill collection", written)
        self.assertIn("agent-manager", written)
        self.assertIn(
            "Invoke /aida agent create to scaffold an agent.", written
        )
        self.assertIn(
            "No runtime config — operates on files.", written
        )
        self.assertIn(
            "Drop new templates in templates/.", written
        )


class TestSafeJsonLoad(unittest.TestCase):
    """Test safe JSON loading."""

    def test_valid_json(self):
        """Test loading valid JSON."""
        result = safe_json_load('{"key": "value"}')
        self.assertEqual(result, {"key": "value"})

    def test_empty_string(self):
        """Test loading empty string returns empty dict."""
        result = safe_json_load("")
        self.assertEqual(result, {})

    def test_invalid_json(self):
        """Test invalid JSON raises ValueError."""
        with self.assertRaises(ValueError):
            safe_json_load("{invalid json}")

    def test_size_limit(self):
        """Test oversized JSON is rejected."""
        large_json = json.dumps({"data": "x" * (100 * 1024 + 1)})
        with self.assertRaises(ValueError) as cm:
            safe_json_load(large_json)
        self.assertIn("size limit", str(cm.exception).lower())


def run_tests():
    """Run all tests and return results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestGetProjectRoot))
    suite.addTests(loader.loadTestsFromTestCase(TestGetClaudeMdPath))
    suite.addTests(loader.loadTestsFromTestCase(TestFindClaudeMd))
    suite.addTests(loader.loadTestsFromTestCase(TestParseFrontmatter))
    suite.addTests(loader.loadTestsFromTestCase(TestDetectSections))
    suite.addTests(loader.loadTestsFromTestCase(TestExtractCommandsFromMakefile))
    suite.addTests(loader.loadTestsFromTestCase(TestExtractCommandsFromPackageJson))
    suite.addTests(loader.loadTestsFromTestCase(TestExtractReadmeDescription))
    suite.addTests(loader.loadTestsFromTestCase(TestDetectProjectContext))
    suite.addTests(loader.loadTestsFromTestCase(TestValidateClaudeMd))
    suite.addTests(loader.loadTestsFromTestCase(TestCalculateAuditScore))
    suite.addTests(loader.loadTestsFromTestCase(TestGenerateAuditFindings))
    suite.addTests(loader.loadTestsFromTestCase(TestGetQuestions))
    suite.addTests(loader.loadTestsFromTestCase(TestExecute))
    suite.addTests(loader.loadTestsFromTestCase(TestExecuteCreate))
    suite.addTests(loader.loadTestsFromTestCase(TestSafeJsonLoad))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


if __name__ == "__main__":
    result = run_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
