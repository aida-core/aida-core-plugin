# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for plugin-manager generator operations."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

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

import operations.scaffold_ops.generators as _generators_mod  # noqa: E402

from operations.scaffold_ops.generators import (  # noqa: E402
    create_directory_structure,
    render_shared_files,
    assemble_gitignore,
    assemble_makefile,
    initialize_git,
    create_initial_commit,
)

TEMPLATES_DIR = _project_root / "skills" / "plugin-manager" / "templates" / "scaffold"

_ops_snapshot = {
    k: v for k, v in sys.modules.items()
    if k == "operations" or k.startswith("operations.")
}


class TestCreateDirectoryStructure(unittest.TestCase):
    """Test directory structure creation."""

    def test_python_structure(self):
        """Should create Python-specific directories."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            created = create_directory_structure(target, "python")
            self.assertIn(".claude-plugin", created)
            self.assertIn(".github/workflows", created)
            self.assertIn("agents", created)
            self.assertIn("skills", created)
            self.assertIn("scripts", created)
            self.assertIn("tests", created)
            self.assertIn("docs", created)
            # Verify directories actually exist
            self.assertTrue((target / ".claude-plugin").is_dir())
            self.assertTrue((target / "scripts").is_dir())
            self.assertTrue((target / "tests").is_dir())
            self.assertTrue((target / ".github" / "workflows").is_dir())

    def test_typescript_structure(self):
        """Should create TypeScript-specific directories."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            created = create_directory_structure(target, "typescript")
            self.assertIn(".claude-plugin", created)
            self.assertIn(".github/workflows", created)
            self.assertIn("agents", created)
            self.assertIn("skills", created)
            self.assertIn("src", created)
            self.assertIn("tests", created)
            self.assertIn("docs", created)
            # Verify directories actually exist
            self.assertTrue((target / ".claude-plugin").is_dir())
            self.assertTrue((target / "src").is_dir())
            self.assertTrue((target / "tests").is_dir())
            self.assertTrue((target / ".github" / "workflows").is_dir())

    def test_python_does_not_create_src(self):
        """Python should not create src/ directory."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            created = create_directory_structure(target, "python")
            self.assertNotIn("src", created)

    def test_typescript_does_not_create_scripts(self):
        """TypeScript should not create scripts/ directory."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            created = create_directory_structure(target, "typescript")
            self.assertNotIn("scripts", created)


class TestRenderSharedFiles(unittest.TestCase):
    """Test shared file rendering."""
    # REUSE-IgnoreStart — assertions reference literal SPDX strings.

    def _build_variables(self, **overrides):
        from operations.shared import build_template_variables
        context = {
            "plugin_name": "test-plugin",
            "description": "A test plugin for testing",
            "version": "0.1.0",
            "author_name": "Test Author",
            "author_email": "test@example.com",
            "license_id": "MIT",
            "language": "python",
            "python_version": "3.11",
            "node_version": "20",
            "keywords": "test",
            "repository_url": "",
            "include_agent_stub": False,
            "include_skill_stub": False,
        }
        context.update(overrides)
        return build_template_variables(context, "MIT License text here")

    def test_produces_expected_files(self):
        """Should render all shared template files."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            target.mkdir(exist_ok=True)

            created = render_shared_files(
                target, self._build_variables(), TEMPLATES_DIR
            )

            expected_files = [
                ".claude-plugin/plugin.json",
                ".claude-plugin/marketplace.json",
                ".claude-plugin/aida-config.json",
                "CLAUDE.md",
                "README.md",
                ".markdownlint.json",
                ".yamllint.yml",
                ".frontmatter-schema.json",
                "AUTHORS",
                "REUSE.toml",
            ]

            for f in expected_files:
                self.assertIn(f, created, f"Missing file: {f}")
                self.assertTrue((target / f).exists(), f"File not created: {f}")

    def test_emits_spdx_headers_in_markdown(self):
        """Markdown files (README, CLAUDE.md) carry SPDX headers."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            render_shared_files(
                target, self._build_variables(), TEMPLATES_DIR
            )
            for fname in ("README.md", "CLAUDE.md"):
                content = (target / fname).read_text()
                self.assertIn(
                    "SPDX-FileCopyrightText: 2026", content,
                    f"{fname} missing copyright header",
                )
                self.assertIn(
                    "SPDX-License-Identifier: MIT", content,
                    f"{fname} missing license header",
                )

    def test_emits_spdx_headers_in_yaml(self):
        """yamllint config carries an SPDX header in hash style."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            render_shared_files(
                target, self._build_variables(), TEMPLATES_DIR
            )
            content = (target / ".yamllint.yml").read_text()
            self.assertIn("# SPDX-FileCopyrightText:", content)
            self.assertIn("# SPDX-License-Identifier: MIT", content)

    def test_authors_file_lists_initial_author(self):
        """Generated AUTHORS file names the scaffolding author."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            render_shared_files(
                target, self._build_variables(), TEMPLATES_DIR
            )
            content = (target / "AUTHORS").read_text()
            self.assertIn("Test Author", content)
            self.assertIn("test@example.com", content)

    def test_reuse_toml_skips_json(self):
        """REUSE.toml lists JSON in the skip-with-attribution annotations."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            render_shared_files(
                target, self._build_variables(), TEMPLATES_DIR
            )
            content = (target / "REUSE.toml").read_text()
            self.assertIn("**.json", content)
            self.assertIn("MIT", content)

    def test_unlicensed_skips_spdx_license_line(self):
        """For UNLICENSED, copyright-text appears but license-id is suppressed."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            variables = self._build_variables(license_id="UNLICENSED")
            render_shared_files(target, variables, TEMPLATES_DIR)
            content = (target / "README.md").read_text()
            self.assertIn("SPDX-FileCopyrightText:", content)
            # UNLICENSED is not an SPDX identifier; skip the line.
            self.assertNotIn(
                "SPDX-License-Identifier: UNLICENSED", content,
            )

    def test_unlicensed_skips_reuse_toml(self):
        """UNLICENSED has no SPDX id, so REUSE.toml would just emit noise."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            variables = self._build_variables(license_id="UNLICENSED")
            created = render_shared_files(
                target, variables, TEMPLATES_DIR
            )
            self.assertNotIn("REUSE.toml", created)
            self.assertFalse((target / "REUSE.toml").exists())
    # REUSE-IgnoreEnd

    def test_yamllint_config_ignores_node_modules(self):
        """yamllint must skip node_modules / venv / generated dirs.

        Regression for #82 bug 2: `yamllint -c .yamllint.yml .`
        recursively scans `node_modules/` by default, producing
        hundreds of failures from third-party YAML we don't own. The
        config's top-level `ignore:` block prunes those.
        """
        import yaml

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            render_shared_files(
                target, self._build_variables(), TEMPLATES_DIR
            )
            yamllint_cfg = yaml.safe_load(
                (target / ".yamllint.yml").read_text()
            )

            ignore_field = yamllint_cfg.get("ignore", "")
            # `ignore:` is a YAML literal block scalar; parse it as
            # newline-separated paths.
            ignored = {
                line.strip()
                for line in ignore_field.splitlines()
                if line.strip()
            }
            for required in (
                "node_modules/",
                "dist/",
                "coverage/",
                "build/",
                "__pycache__/",
                ".venv/",
                "venv/",
            ):
                self.assertIn(
                    required,
                    ignored,
                    f"yamllint config must ignore {required}; "
                    f"got: {ignored}",
                )

    def test_markdownlint_disables_real_prose_rules(self):
        """Markdownlint must disable rules that conflict with skill /
        agent prose.

        Regression for #82 bug 3 + #92: AIDA skill stubs use
        `<PRD>` / `<ticket>` placeholders (would trip MD033 inline
        HTML), tight technical prose without blanks around lists or
        headings (MD032 / MD022), bold-as-heading patterns like
        `**Last updated:** ...` (MD036), code blocks without language
        tags in docs (MD040), and bare URLs (MD034). Across 9 repos
        and ~40 PRs in the reporter's environment, none of these
        rules caught real problems — they all flagged stylistic
        conventions in scaffolded output.

        These rules must be explicitly set to `false`:
        """
        import json as _json

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            render_shared_files(
                target, self._build_variables(), TEMPLATES_DIR
            )
            cfg = _json.loads(
                (target / ".markdownlint.json").read_text()
            )
            for rule in (
                "MD022",
                "MD025",
                "MD032",
                "MD033",
                "MD034",
                "MD036",
                "MD040",
                "MD041",
            ):
                self.assertIs(
                    cfg.get(rule),
                    False,
                    f"markdownlint rule {rule} must be disabled; "
                    f"got {cfg.get(rule)!r}",
                )


class TestAssembleGitignore(unittest.TestCase):
    """Test .gitignore assembly."""

    def test_python_gitignore(self):
        """Python gitignore should include Python-specific patterns."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            assemble_gitignore(target, "python", TEMPLATES_DIR)
            content = (target / ".gitignore").read_text()
            self.assertIn("__pycache__", content)
            self.assertIn(".DS_Store", content)
            self.assertNotIn("node_modules", content)

    def test_typescript_gitignore(self):
        """TypeScript gitignore should include Node-specific patterns."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            assemble_gitignore(target, "typescript", TEMPLATES_DIR)
            content = (target / ".gitignore").read_text()
            self.assertIn("node_modules", content)
            self.assertIn(".DS_Store", content)
            self.assertNotIn("__pycache__", content)

    def test_gitignore_differs_by_language(self):
        """Python and TypeScript gitignores should differ."""
        with tempfile.TemporaryDirectory() as tmp:
            py_target = Path(tmp) / "python"
            py_target.mkdir()
            ts_target = Path(tmp) / "typescript"
            ts_target.mkdir()

            assemble_gitignore(py_target, "python", TEMPLATES_DIR)
            assemble_gitignore(ts_target, "typescript", TEMPLATES_DIR)

            py_content = (py_target / ".gitignore").read_text()
            ts_content = (ts_target / ".gitignore").read_text()

            self.assertNotEqual(py_content, ts_content)

    def test_gitignore_does_not_blanket_ignore_claude_dir(self):
        """Regression: gitignore must not blanket-ignore .claude/.

        #95: a bare `.claude/` entry shadows the shared project config
        that `/aida config` writes (aida.yml, aida-project-context.yml,
        rendered project-context skill) — those are *committable*
        team-shared state, not user-local. The convention is to ignore
        only `.claude/settings.local.json` (Claude Code's own
        local-overrides file).

        Fixed in PR #62 (commit 48a882c). This test pins the fix so a
        future template edit can't silently reintroduce the broad
        pattern.
        """
        for lang in ("python", "typescript"):
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp)
                assemble_gitignore(target, lang, TEMPLATES_DIR)
                content = (target / ".gitignore").read_text()

                # The narrow, correct exclusion must be present.
                self.assertIn(
                    ".claude/settings.local.json",
                    content,
                    f"{lang}: gitignore must exclude "
                    f"settings.local.json",
                )

                # The broad pattern must NOT appear as a standalone
                # ignore line. Check line-by-line (substring would
                # false-positive on `.claude/settings.local.json`).
                for line in content.splitlines():
                    stripped = line.strip()
                    self.assertNotEqual(
                        stripped,
                        ".claude/",
                        f"{lang}: gitignore has blanket '.claude/' "
                        f"that would shadow shared project config",
                    )
                    self.assertNotEqual(
                        stripped,
                        ".claude",
                        f"{lang}: gitignore has blanket '.claude' "
                        f"that would shadow shared project config",
                    )

    def test_gitignore_avoids_broad_file_name_blanket_patterns(self):
        """Regression: gitignore must not contain broad blanket
        patterns that match by file *name* rather than location.

        #91 background: the reporter scaffolded 9 repos using a
        kitchen-sink monorepo `.gitignore` and silently lost 11 files
        because patterns like `*secrets*`, `*credentials*`, and `lib/`
        matched legitimate code:

            - `lib/` swallowed an AWS CDK stack directory
            - `*secrets*` swallowed `SecretsStack.ts` (which *manages*
              secrets — it doesn't *contain* any)
            - `*credentials*` swallowed similar `*CredentialsStack.ts`

        AIDA's plugin scaffold already meets the slim-fragment design
        the issue asks for (shared + per-language fragments, ~10-16
        patterns each, no name-based blanket blocks). This test pins
        that policy so future contributions can't drift toward the
        kitchen-sink shape.
        """
        forbidden = {
            "lib/": "matches CDK / Node lib directories",
            "*secrets*": (
                "matches legitimate filenames like SecretsStack.ts"
            ),
            "*credentials*": (
                "matches legitimate filenames like CredentialsStack.ts"
            ),
            "*.key": "would swallow JWT / crypto sample fixtures",
            "*.pem": "would swallow PEM fixtures in tests",
            # `*.env*` would also match `.env.example` / `.env.sample`
            # which teams typically want to commit.
            "*.env*": "would swallow .env.example / .env.sample",
        }

        for lang in ("python", "typescript"):
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp)
                assemble_gitignore(target, lang, TEMPLATES_DIR)
                lines = [
                    line.strip()
                    for line in (target / ".gitignore")
                    .read_text()
                    .splitlines()
                ]
                for pattern, reason in forbidden.items():
                    self.assertNotIn(
                        pattern,
                        lines,
                        f"{lang} gitignore contains forbidden broad "
                        f"pattern {pattern!r} — {reason}",
                    )

    def test_gitignore_stays_slim(self):
        """Regression: the assembled gitignore must stay slim.

        #91 motivation was a kitchen-sink universal gitignore that
        silently swallowed legitimate files. AIDA's design is small,
        flavor-specific fragments; that property is observable as a
        line-count budget. The current python and typescript outputs
        are ~30 lines each (including section comments and blank
        lines). The budget below leaves slack for one or two more
        narrow patterns per language without re-opening the door to
        the kitchen-sink failure mode.

        If you find yourself raising this budget, prefer adding a new
        per-flavor fragment (see scaffolding-workflow.md > Gitignore
        Policy) over appending more patterns to an existing one.
        """
        MAX_LINES = 50

        for lang in ("python", "typescript"):
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp)
                assemble_gitignore(target, lang, TEMPLATES_DIR)
                line_count = len(
                    (target / ".gitignore")
                    .read_text()
                    .splitlines()
                )
                self.assertLessEqual(
                    line_count,
                    MAX_LINES,
                    f"{lang} gitignore is {line_count} lines, exceeds "
                    f"slim budget of {MAX_LINES}. Either trim, or "
                    f"split into a new per-flavor fragment.",
                )


class TestAssembleMakefile(unittest.TestCase):
    """Test Makefile assembly."""

    def test_python_makefile(self):
        """Python Makefile should include ruff and pytest targets."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            variables = {
                "plugin_name": "test-plugin",
                "plugin_display_name": "Test Plugin",
            }
            assemble_makefile(target, "python", variables, TEMPLATES_DIR)
            content = (target / "Makefile").read_text()
            self.assertIn("ruff", content)
            self.assertIn("pytest", content)

    def test_typescript_makefile(self):
        """TypeScript Makefile should include eslint and vitest targets."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            variables = {
                "plugin_name": "test-plugin",
                "plugin_display_name": "Test Plugin",
            }
            assemble_makefile(target, "typescript", variables, TEMPLATES_DIR)
            content = (target / "Makefile").read_text()
            self.assertIn("lint", content)
            self.assertIn("vitest", content)

    def test_makefile_differs_by_language(self):
        """Python and TypeScript Makefiles should differ."""
        with tempfile.TemporaryDirectory() as tmp:
            py_target = Path(tmp) / "python"
            py_target.mkdir()
            ts_target = Path(tmp) / "typescript"
            ts_target.mkdir()

            variables = {
                "plugin_name": "test-plugin",
                "plugin_display_name": "Test Plugin",
            }

            assemble_makefile(py_target, "python", variables, TEMPLATES_DIR)
            assemble_makefile(ts_target, "typescript", variables, TEMPLATES_DIR)

            py_content = (py_target / "Makefile").read_text()
            ts_content = (ts_target / "Makefile").read_text()

            self.assertNotEqual(py_content, ts_content)


class TestInitializeGit(unittest.TestCase):
    """Test git initialization."""

    @patch.object(_generators_mod.subprocess, "run")
    def test_success(self, mock_run):
        """Should return True on successful git init."""
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as tmp:
            result = initialize_git(Path(tmp))
            self.assertTrue(result)

    @patch.object(_generators_mod.subprocess, "run")
    def test_failure(self, mock_run):
        """Should return False when git is not available."""
        mock_run.side_effect = FileNotFoundError("git not found")
        with tempfile.TemporaryDirectory() as tmp:
            result = initialize_git(Path(tmp))
            self.assertFalse(result)


class TestCreateInitialCommit(unittest.TestCase):
    """Test initial commit creation."""

    @patch.object(_generators_mod.subprocess, "run")
    def test_success(self, mock_run):
        """Should return True when both add and commit succeed."""
        mock_run.return_value = MagicMock(returncode=0)
        result = create_initial_commit(Path("/tmp/test"))
        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 2)

    @patch.object(_generators_mod.subprocess, "run")
    def test_failure_on_add(self, mock_run):
        """Should return False when git add fails."""
        mock_run.return_value = MagicMock(returncode=1)
        result = create_initial_commit(Path("/tmp/test"))
        self.assertFalse(result)

    @patch.object(_generators_mod.subprocess, "run")
    def test_failure_on_commit(self, mock_run):
        """Should return False when git commit fails after add succeeds."""
        add_result = MagicMock(returncode=0)
        commit_result = MagicMock(returncode=1)
        mock_run.side_effect = [add_result, commit_result]
        result = create_initial_commit(Path("/tmp/test"))
        self.assertFalse(result)

    @patch.object(_generators_mod.subprocess, "run")
    def test_failure_on_file_not_found(self, mock_run):
        """Should return False when git is not available."""
        mock_run.side_effect = FileNotFoundError("git not found")
        result = create_initial_commit(Path("/tmp/test"))
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
