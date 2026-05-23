# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for plugin-manager scaffold.py main entry point."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add scripts directories to path
_project_root = Path(__file__).parent.parent.parent
_plugin_scripts = _project_root / "skills" / "plugin-manager" / "scripts"
sys.path.insert(0, str(_project_root / "scripts"))
sys.path.insert(0, str(_plugin_scripts))

# Clear cached operations modules to avoid cross-manager conflicts in pytest
for _mod_name in list(sys.modules):
    if _mod_name == "operations" or _mod_name.startswith("operations."):
        del sys.modules[_mod_name]
sys.modules.pop("_paths", None)

from operations import scaffold as _scaffold_mod  # noqa: E402

get_questions = _scaffold_mod.get_questions
execute = _scaffold_mod.execute

_ops_snapshot = {
    k: v for k, v in sys.modules.items()
    if k == "operations" or k.startswith("operations.")
}


class TestGetQuestionsNoContext(unittest.TestCase):
    """Test get_questions with no context."""

    @patch.object(_scaffold_mod, "infer_git_config", return_value={"author_name": "", "author_email": ""})
    @patch.object(_scaffold_mod, "check_gh_available", return_value=False)
    def test_returns_all_questions(self, mock_gh, mock_git):
        """With empty context, all questions should be returned."""
        result = get_questions({})
        question_ids = [q["id"] for q in result["questions"]]

        self.assertIn("plugin_name", question_ids)
        self.assertIn("description", question_ids)
        self.assertIn("license", question_ids)
        self.assertIn("language", question_ids)
        self.assertIn("target_directory", question_ids)
        self.assertIn("include_agent_stub", question_ids)
        self.assertIn("include_skill_stub", question_ids)
        self.assertIn("keywords", question_ids)
        self.assertIn("author_name", question_ids)
        self.assertIn("author_email", question_ids)

    @patch.object(_scaffold_mod, "infer_git_config", return_value={"author_name": "", "author_email": ""})
    @patch.object(_scaffold_mod, "check_gh_available", return_value=False)
    def test_no_github_question_without_gh(self, mock_gh, mock_git):
        """Should not ask about GitHub repo if gh is not available."""
        result = get_questions({})
        question_ids = [q["id"] for q in result["questions"]]
        self.assertNotIn("create_github_repo", question_ids)


class TestGetQuestionsPartialContext(unittest.TestCase):
    """Test get_questions with partial context."""

    @patch.object(_scaffold_mod, "infer_git_config", return_value={"author_name": "User", "author_email": "user@test.com"})
    @patch.object(_scaffold_mod, "check_gh_available", return_value=True)
    def test_filters_answered_questions(self, mock_gh, mock_git):
        """Already-provided fields should not generate questions."""
        context = {
            "plugin_name": "my-plugin",
            "description": "A test plugin for testing",
            "license": "MIT",
            "language": "python",
        }
        result = get_questions(context)
        question_ids = [q["id"] for q in result["questions"]]

        self.assertNotIn("plugin_name", question_ids)
        self.assertNotIn("description", question_ids)
        self.assertNotIn("license", question_ids)
        self.assertNotIn("language", question_ids)
        # Should still ask for target_directory, stubs, keywords
        self.assertIn("target_directory", question_ids)
        self.assertIn("include_agent_stub", question_ids)

    @patch.object(_scaffold_mod, "infer_git_config", return_value={"author_name": "User", "author_email": "user@test.com"})
    @patch.object(_scaffold_mod, "check_gh_available", return_value=False)
    def test_infers_git_config(self, mock_gh, mock_git):
        """Should infer author info from git config."""
        result = get_questions({})
        self.assertEqual(result["inferred"]["author_name"], "User")
        self.assertEqual(result["inferred"]["author_email"], "user@test.com")

        # Should not ask for author info since it was inferred
        question_ids = [q["id"] for q in result["questions"]]
        self.assertNotIn("author_name", question_ids)
        self.assertNotIn("author_email", question_ids)

    @patch.object(_scaffold_mod, "infer_git_config", return_value={"author_name": "", "author_email": ""})
    @patch.object(_scaffold_mod, "check_gh_available", return_value=True)
    def test_github_question_with_gh(self, mock_gh, mock_git):
        """Should ask about GitHub repo if gh is available."""
        result = get_questions({})
        question_ids = [q["id"] for q in result["questions"]]
        self.assertIn("create_github_repo", question_ids)


class TestExecutePythonProject(unittest.TestCase):
    """Test execute with Python toolchain."""

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_creates_full_project(self, mock_commit, mock_git):
        """Should create a complete Python plugin project."""
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "test-plugin")

            context = {
                "plugin_name": "test-plugin",
                "description": "A test plugin for testing purposes",
                "license": "MIT",
                "language": "python",
                "target_directory": target,
                "author_name": "Test Author",
                "author_email": "test@example.com",
                "keywords": "test, plugin",
                "version": "0.1.0",
            }

            result = execute(context)

            self.assertTrue(result["success"], f"Execute failed: {result.get('message')}")
            self.assertEqual(result["language"], "python")
            self.assertEqual(result["path"], str(Path(target).resolve()))

            # Verify key files exist
            target_path = Path(result["path"])
            self.assertTrue((target_path / ".claude-plugin" / "plugin.json").exists())
            self.assertTrue((target_path / "CLAUDE.md").exists())
            self.assertTrue((target_path / "README.md").exists())
            self.assertTrue((target_path / "LICENSE").exists())
            self.assertTrue((target_path / "Makefile").exists())
            self.assertTrue((target_path / ".gitignore").exists())
            self.assertTrue((target_path / "pyproject.toml").exists())
            self.assertTrue((target_path / ".python-version").exists())
            self.assertTrue((target_path / "tests" / "conftest.py").exists())


class TestExecuteTypeScriptProject(unittest.TestCase):
    """Test execute with TypeScript toolchain."""

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_creates_full_project(self, mock_commit, mock_git):
        """Should create a complete TypeScript plugin project."""
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "ts-plugin")

            context = {
                "plugin_name": "ts-plugin",
                "description": "A TypeScript test plugin for testing",
                "license": "Apache-2.0",
                "language": "typescript",
                "target_directory": target,
                "author_name": "Test Author",
                "author_email": "test@example.com",
                "keywords": "",
                "version": "0.1.0",
            }

            result = execute(context)

            self.assertTrue(result["success"], f"Execute failed: {result.get('message')}")
            self.assertEqual(result["language"], "typescript")

            # Verify TypeScript-specific files
            target_path = Path(result["path"])
            self.assertTrue((target_path / "package.json").exists())
            self.assertTrue((target_path / "tsconfig.json").exists())
            self.assertTrue((target_path / "eslint.config.mjs").exists())
            self.assertTrue((target_path / ".prettierrc.json").exists())
            self.assertTrue((target_path / ".nvmrc").exists())
            self.assertTrue((target_path / "vitest.config.ts").exists())


class TestScaffoldedCiYamlParses(unittest.TestCase):
    """Regression guard for #74: scaffolded ci.yml must be valid YAML.

    The original bug used `{% raw %}…{% endraw %}` blocks to escape
    GitHub Actions `${{ … }}` expressions. With Jinja2's
    `trim_blocks=True`, `{% endraw %}` ate the trailing newline so
    `name:` and `uses:` ended up concatenated on a single line,
    producing a YAML parse error on the very first CI run of every
    scaffolded plugin. Fix landed in 1.5.0 by switching to
    `${{ '{{' }}…{{ '}}' }}` Jinja literals. This test pins the fix
    so any future template change that reintroduces the same shape
    fails loudly here instead of silently in user repos.
    """

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_python_scaffold_ci_yml_parses(self, mock_commit, mock_git):
        import yaml

        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "py-plugin")
            context = {
                "plugin_name": "py-plugin",
                "description": "A Python plugin for #74 regression testing",
                "license": "MIT",
                "language": "python",
                "target_directory": target,
                "author_name": "Test Author",
                "author_email": "test@example.com",
                "keywords": "",
                "version": "0.1.0",
            }
            result = execute(context)
            self.assertTrue(result["success"], result.get("message"))

            ci_yml = (
                Path(result["path"]) / ".github" / "workflows" / "ci.yml"
            )
            self.assertTrue(
                ci_yml.exists(), f"ci.yml not generated at {ci_yml}"
            )

            # Must parse without raising — the original bug raised
            # yaml.YAMLError on the mashed-together name/uses line.
            content = ci_yml.read_text(encoding="utf-8")
            parsed = yaml.safe_load(content)
            self.assertIsInstance(parsed, dict)
            self.assertEqual(parsed.get("name"), "CI")

            # And specifically: the `name: Set up Python` step must
            # have its own line, with `uses:` on the next line.
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if "Set up Python" in line and "name:" in line:
                    self.assertNotIn(
                        "uses:",
                        line,
                        f"`name:` and `uses:` mashed on line {i + 1}: {line!r}",
                    )
                    break
            else:
                self.fail(
                    "Expected a 'Set up Python' step in scaffolded ci.yml"
                )

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_typescript_scaffold_ci_yml_parses(self, mock_commit, mock_git):
        import yaml

        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "ts-plugin")
            context = {
                "plugin_name": "ts-plugin",
                "description": "A TypeScript plugin for #74 regression testing",
                "license": "MIT",
                "language": "typescript",
                "target_directory": target,
                "author_name": "Test Author",
                "author_email": "test@example.com",
                "keywords": "",
                "version": "0.1.0",
            }
            result = execute(context)
            self.assertTrue(result["success"], result.get("message"))

            ci_yml = (
                Path(result["path"]) / ".github" / "workflows" / "ci.yml"
            )
            self.assertTrue(ci_yml.exists())

            content = ci_yml.read_text(encoding="utf-8")
            parsed = yaml.safe_load(content)
            self.assertIsInstance(parsed, dict)
            self.assertEqual(parsed.get("name"), "CI")

            lines = content.splitlines()
            for i, line in enumerate(lines):
                if "Set up Node" in line and "name:" in line:
                    self.assertNotIn(
                        "uses:",
                        line,
                        f"`name:` and `uses:` mashed on line {i + 1}: {line!r}",
                    )
                    break
            else:
                self.fail(
                    "Expected a 'Set up Node' step in scaffolded ci.yml"
                )


class TestScaffoldedLintBaseline(unittest.TestCase):
    """Regression guards for #82 + #92: lint config that actually works.

    The scaffold previously emitted three broken lint defaults:

    - #82.1: `lint-md` called `markdownlint` directly while the
      TypeScript package.json had no `markdownlint-cli` dependency,
      so fresh installs hit `markdownlint: No such file or directory`
    - #82.2: `lint-yaml` scanned `node_modules/`, producing hundreds
      of failures from third-party YAML
    - #82.3 / #92: markdownlint defaults conflicted with real
      AIDA-generated prose (template placeholders → MD033, tight
      technical content → MD022 / MD032, etc.)

    Plus Python scaffolds had no Node.js setup in their CI workflow,
    so `npx markdownlint-cli` would fail there too.

    These tests pin all four fixes together at the scaffold-output
    level — the rendered files have to be self-sufficient when a new
    plugin gets `npm install` / `pip install -e .[dev]` and runs
    `make lint`.
    """

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_typescript_package_includes_markdownlint_cli(
        self, mock_commit, mock_git
    ):
        """TS package.json must ship markdownlint-cli as a devDep."""
        import json as _json

        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "ts-plugin")
            context = {
                "plugin_name": "ts-plugin",
                "description": (
                    "A TypeScript plugin for #82 lint dep testing"
                ),
                "license": "MIT",
                "language": "typescript",
                "target_directory": target,
                "author_name": "Test",
                "author_email": "test@test.com",
                "keywords": "",
                "version": "0.1.0",
            }
            result = execute(context)
            self.assertTrue(result["success"], result.get("message"))

            pkg = _json.loads(
                (Path(result["path"]) / "package.json").read_text()
            )
            dev_deps = pkg.get("devDependencies", {})
            self.assertIn(
                "markdownlint-cli",
                dev_deps,
                f"package.json missing markdownlint-cli devDep; "
                f"got {sorted(dev_deps)}",
            )

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_makefile_uses_npx_for_markdownlint(
        self, mock_commit, mock_git
    ):
        """Makefile lint-md must use `npx --yes markdownlint-cli`.

        Direct `markdownlint` invocation only works when the binary
        is globally installed — broken on fresh TS scaffolds and on
        Python scaffolds without an explicit global install. `npx
        --yes` resolves to the devDep on TS, and prompt-suppresses
        on first run elsewhere.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "py-plugin")
            context = {
                "plugin_name": "py-plugin",
                "description": (
                    "A Python plugin for #82 makefile testing"
                ),
                "license": "MIT",
                "language": "python",
                "target_directory": target,
                "author_name": "Test",
                "author_email": "test@test.com",
                "keywords": "",
                "version": "0.1.0",
            }
            result = execute(context)
            self.assertTrue(result["success"], result.get("message"))

            makefile = (
                Path(result["path"]) / "Makefile"
            ).read_text()

            # lint-md and lint-fix-md must call npx markdownlint-cli
            # with explicit --config so auto-discovery quirks don't
            # silently drop our config.
            for marker in (
                "npx --yes markdownlint-cli",
                "--config .markdownlint.json",
            ):
                self.assertIn(
                    marker,
                    makefile,
                    f"Makefile missing required marker: {marker!r}",
                )

            # The old `markdownlint '**/*.md'` direct invocation
            # without npx must not appear — it's the broken shape.
            for line in makefile.splitlines():
                stripped = line.lstrip()
                self.assertFalse(
                    stripped.startswith("markdownlint ")
                    and "npx" not in stripped,
                    f"Direct `markdownlint` call (no npx): {line!r}",
                )

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_python_ci_yml_sets_up_node(self, mock_commit, mock_git):
        """Python scaffold ci.yml must install Node before make lint.

        `make lint` calls `lint-md`, which shells out to npx /
        markdownlint-cli (a Node tool). Hosted Ubuntu runners have
        Node pre-installed, but the workflow still needs an explicit
        `actions/setup-node@v4` step so the version is pinned and
        npm cache is set up.
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "py-plugin")
            context = {
                "plugin_name": "py-plugin",
                "description": (
                    "A Python plugin for #82 ci-yml testing"
                ),
                "license": "MIT",
                "language": "python",
                "target_directory": target,
                "author_name": "Test",
                "author_email": "test@test.com",
                "keywords": "",
                "version": "0.1.0",
            }
            result = execute(context)
            self.assertTrue(result["success"], result.get("message"))

            ci = (
                Path(result["path"])
                / ".github"
                / "workflows"
                / "ci.yml"
            ).read_text()
            self.assertIn(
                "actions/setup-node@v4",
                ci,
                "Python ci.yml missing setup-node step — `npx "
                "markdownlint-cli` will fail without Node.",
            )
    """Test execute with agent stub."""

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_creates_agent_stub(self, mock_commit, mock_git):
        """Should create an agent stub when requested."""
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "stub-plugin")

            context = {
                "plugin_name": "stub-plugin",
                "description": "A plugin with agent stub for testing",
                "license": "MIT",
                "language": "python",
                "target_directory": target,
                "author_name": "Test",
                "author_email": "test@test.com",
                "include_agent_stub": True,
                "agent_stub_name": "my-agent",
                "agent_stub_description": "A test agent for the plugin",
            }

            result = execute(context)
            self.assertTrue(result["success"], f"Execute failed: {result.get('message')}")

            target_path = Path(result["path"])
            self.assertTrue(
                (target_path / "agents" / "my-agent" / "my-agent.md").exists()
            )


class TestExecuteWithSkillStub(unittest.TestCase):
    """Test execute with skill stub."""

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_creates_skill_stub(self, mock_commit, mock_git):
        """Should create a skill stub when requested."""
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "skill-plugin")

            context = {
                "plugin_name": "skill-plugin",
                "description": "A plugin with skill stub for testing",
                "license": "MIT",
                "language": "python",
                "target_directory": target,
                "author_name": "Test",
                "author_email": "test@test.com",
                "include_skill_stub": True,
                "skill_stub_name": "my-skill",
                "skill_stub_description": "A test skill for the plugin",
            }

            result = execute(context)
            self.assertTrue(result["success"], f"Execute failed: {result.get('message')}")

            target_path = Path(result["path"])
            self.assertTrue(
                (target_path / "skills" / "my-skill" / "SKILL.md").exists()
            )


class TestExecuteValidation(unittest.TestCase):
    """Test execute input validation."""

    def test_rejects_missing_name(self):
        """Should reject execution without plugin_name."""
        result = execute({})
        self.assertFalse(result["success"])
        self.assertIn("plugin_name", result["message"])

    def test_rejects_invalid_name(self):
        """Should reject plugin names that can't be auto-converted to valid kebab-case."""
        # "!!!" converts to empty string via to_kebab_case, which fails validation
        result = execute({"plugin_name": "!!!", "description": "A valid description"})
        self.assertFalse(result["success"])
        self.assertIn("invalid plugin name", result["message"].lower())

    def test_auto_converts_name_to_kebab_case(self):
        """Should auto-convert names to kebab-case before validation."""
        # "Invalid Name!" should be auto-converted to "invalid-name" which is valid
        result = execute({
            "plugin_name": "Invalid Name!",
            "description": "Short",  # Will fail on description, not name
        })
        # This fails on description (too short), proving name was accepted
        self.assertFalse(result["success"])
        self.assertIn("description", result["message"].lower())

    def test_rejects_invalid_description(self):
        """Should reject invalid descriptions."""
        result = execute({"plugin_name": "valid-name", "description": "Short"})
        self.assertFalse(result["success"])
        self.assertIn("description", result["message"].lower())

    def test_rejects_invalid_language(self):
        """Should reject unsupported languages."""
        result = execute({
            "plugin_name": "test-plugin",
            "description": "A valid description for testing",
            "language": "rust",
        })
        self.assertFalse(result["success"])
        self.assertIn("Unsupported language", result["message"])

    def test_rejects_missing_author(self):
        """Should reject execution without author_name."""
        result = execute({
            "plugin_name": "test-plugin",
            "description": "A valid description for testing",
        })
        self.assertFalse(result["success"])
        self.assertIn("author_name", result["message"])

    def test_rejects_missing_author_email(self):
        """Should reject execution without author_email."""
        result = execute({
            "plugin_name": "test-plugin",
            "description": "A valid description for testing",
            "author_name": "Test",
        })
        self.assertFalse(result["success"])
        self.assertIn("author_email", result["message"])

    def test_rejects_existing_non_empty_directory(self):
        """Should reject non-empty target directory."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "existing"
            target.mkdir()
            (target / "file.txt").write_text("content")

            result = execute({
                "plugin_name": "test-plugin",
                "description": "A valid description for testing",
                "target_directory": str(target),
                "author_name": "Test",
                "author_email": "test@test.com",
            })
            self.assertFalse(result["success"])
            self.assertIn("not empty", result["message"])


class TestExecuteGitInit(unittest.TestCase):
    """Test git initialization during scaffolding."""

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_git_init_creates_git_dir(self, mock_commit, mock_git):
        """Should report git initialization status."""
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "git-plugin")

            context = {
                "plugin_name": "git-plugin",
                "description": "A plugin to test git init behavior",
                "license": "MIT",
                "language": "python",
                "target_directory": target,
                "author_name": "Test",
                "author_email": "test@test.com",
            }

            result = execute(context)
            self.assertTrue(result["success"])
            self.assertTrue(result["git_initialized"])
            self.assertTrue(result["git_committed"])


class TestPythonVersionNormalization(unittest.TestCase):
    """Test python_version normalization to X.Y format."""

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_strips_patch_version(self, mock_commit, mock_git):
        """Should normalize 3.11.4 to 3.11 in pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "ver-plugin")

            context = {
                "plugin_name": "ver-plugin",
                "description": "A plugin to test version normalization",
                "license": "MIT",
                "language": "python",
                "target_directory": target,
                "author_name": "Test",
                "author_email": "test@test.com",
                "python_version": "3.11.4",
            }

            result = execute(context)
            self.assertTrue(result["success"], f"Execute failed: {result.get('message')}")

            # The .python-version file should have X.Y format
            target_path = Path(result["path"])
            py_version = (target_path / ".python-version").read_text().strip()
            self.assertEqual(py_version, "3.11")

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_keeps_xy_format(self, mock_commit, mock_git):
        """Should leave 3.12 as-is."""
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "ver2-plugin")

            context = {
                "plugin_name": "ver2-plugin",
                "description": "A plugin to test version normalization",
                "license": "MIT",
                "language": "python",
                "target_directory": target,
                "author_name": "Test",
                "author_email": "test@test.com",
                "python_version": "3.12",
            }

            result = execute(context)
            self.assertTrue(result["success"], f"Execute failed: {result.get('message')}")

            target_path = Path(result["path"])
            py_version = (target_path / ".python-version").read_text().strip()
            self.assertEqual(py_version, "3.12")


class TestExecuteTypescriptFiles(unittest.TestCase):
    """Test TypeScript scaffolding creates new files (index.ts, test, CI)."""

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_creates_typescript_entry_point(self, mock_commit, mock_git):
        """Should create src/index.ts and tests/index.test.ts."""
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "ts-entry-plugin")

            context = {
                "plugin_name": "ts-entry-plugin",
                "description": "A TypeScript plugin to test entry point files",
                "license": "MIT",
                "language": "typescript",
                "target_directory": target,
                "author_name": "Test",
                "author_email": "test@test.com",
            }

            result = execute(context)
            self.assertTrue(result["success"], f"Execute failed: {result.get('message')}")

            target_path = Path(result["path"])
            self.assertTrue(
                (target_path / "src" / "index.ts").exists(),
                "src/index.ts should exist",
            )
            self.assertTrue(
                (target_path / "tests" / "index.test.ts").exists(),
                "tests/index.test.ts should exist",
            )

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_creates_ci_workflow(self, mock_commit, mock_git):
        """Should create .github/workflows/ci.yml for TypeScript."""
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "ts-ci-plugin")

            context = {
                "plugin_name": "ts-ci-plugin",
                "description": "A TypeScript plugin to test CI workflow",
                "license": "MIT",
                "language": "typescript",
                "target_directory": target,
                "author_name": "Test",
                "author_email": "test@test.com",
            }

            result = execute(context)
            self.assertTrue(result["success"], f"Execute failed: {result.get('message')}")

            target_path = Path(result["path"])
            ci_path = target_path / ".github" / "workflows" / "ci.yml"
            self.assertTrue(ci_path.exists(), ".github/workflows/ci.yml should exist")

            # Verify it's a valid YAML-like file with expected content
            ci_content = ci_path.read_text()
            self.assertIn("name:", ci_content)


class TestExecutePythonCIWorkflow(unittest.TestCase):
    """Test Python scaffolding creates CI workflow."""

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_creates_ci_workflow(self, mock_commit, mock_git):
        """Should create .github/workflows/ci.yml for Python."""
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "py-ci-plugin")

            context = {
                "plugin_name": "py-ci-plugin",
                "description": "A Python plugin to test CI workflow creation",
                "license": "MIT",
                "language": "python",
                "target_directory": target,
                "author_name": "Test",
                "author_email": "test@test.com",
            }

            result = execute(context)
            self.assertTrue(result["success"], f"Execute failed: {result.get('message')}")

            target_path = Path(result["path"])
            ci_path = target_path / ".github" / "workflows" / "ci.yml"
            self.assertTrue(ci_path.exists(), ".github/workflows/ci.yml should exist")

            ci_content = ci_path.read_text()
            self.assertIn("name:", ci_content)


class TestPartialFailureResponse(unittest.TestCase):
    """Test that partial failure includes path and files_created."""

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    @patch.object(_scaffold_mod, "render_typescript_files", side_effect=RuntimeError("Template error"))
    def test_includes_path_and_files_on_failure(self, mock_ts, mock_commit, mock_git):
        """Should include path and files_created in error response."""
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "fail-plugin")

            context = {
                "plugin_name": "fail-plugin",
                "description": "A plugin that will fail during scaffolding",
                "license": "MIT",
                "language": "typescript",
                "target_directory": target,
                "author_name": "Test",
                "author_email": "test@test.com",
            }

            result = execute(context)
            self.assertFalse(result["success"])
            self.assertIn("path", result)
            self.assertIn("files_created", result)
            self.assertIn("error_type", result)
            self.assertEqual(result["error_type"], "RuntimeError")
            # Some shared files should have been created before failure
            self.assertIsInstance(result["files_created"], list)


class TestExecuteLicensesDirectory(unittest.TestCase):
    """Test that LICENSES/<id>.txt is emitted for SPDX licenses but skipped for UNLICENSED."""

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_writes_licenses_dir_for_spdx_license(self, mock_commit, mock_git):
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "spdx-plugin")
            result = execute({
                "plugin_name": "spdx-plugin",
                "description": "An SPDX-licensed plugin for testing",
                "license": "MIT",
                "language": "python",
                "target_directory": target,
                "author_name": "Test",
                "author_email": "test@test.com",
            })
            self.assertTrue(result["success"], result.get("message"))
            target_path = Path(result["path"])
            self.assertTrue(
                (target_path / "LICENSES" / "MIT.txt").exists(),
                "LICENSES/MIT.txt should exist for an MIT-licensed scaffold",
            )

    @patch.object(_scaffold_mod, "initialize_git", return_value=True)
    @patch.object(_scaffold_mod, "create_initial_commit", return_value=True)
    def test_skips_licenses_dir_for_unlicensed(self, mock_commit, mock_git):
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / "proprietary-plugin")
            result = execute({
                "plugin_name": "proprietary-plugin",
                "description": "A proprietary plugin for testing",
                "license": "UNLICENSED",
                "language": "python",
                "target_directory": target,
                "author_name": "Test",
                "author_email": "test@test.com",
            })
            self.assertTrue(result["success"], result.get("message"))
            target_path = Path(result["path"])
            self.assertFalse(
                (target_path / "LICENSES").exists(),
                "LICENSES/ should not be emitted for UNLICENSED scaffolds",
            )
            # LICENSE at root still exists for GitHub display
            self.assertTrue((target_path / "LICENSE").exists())


if __name__ == "__main__":
    unittest.main()
