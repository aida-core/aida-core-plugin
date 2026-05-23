# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for plugin-manager update scanner."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add scripts directories to path
_project_root = Path(__file__).parent.parent.parent
_plugin_scripts = (
    _project_root / "skills" / "plugin-manager" / "scripts"
)
sys.path.insert(0, str(_project_root / "scripts"))
sys.path.insert(0, str(_plugin_scripts))

# Clear cached operations modules to avoid cross-manager
# conflicts in pytest
for _mod_name in list(sys.modules):
    if _mod_name == "operations" or _mod_name.startswith(
        "operations."
    ):
        del sys.modules[_mod_name]
sys.modules.pop("_paths", None)

from operations.update_ops.scanner import (  # noqa: E402
    _detect_language,
    _read_generator_version,
    _read_plugin_metadata,
    scan_plugin,
)
from operations.update_ops.models import (  # noqa: E402
    FileCategory,
    FileStatus,
    MergeStrategy,
)
from operations.constants import (  # noqa: E402
    GENERATOR_VERSION,
)
import operations.scaffold_ops.context as _context_mod  # noqa: E402

_ops_snapshot = {
    k: v for k, v in sys.modules.items()
    if k == "operations" or k.startswith("operations.")
}

TEMPLATES_DIR = (
    _plugin_scripts.parent / "templates" / "scaffold"
)

_GIT_MOCK_RETURN = {
    "author_name": "Test Author",
    "author_email": "test@test.com",
}


def _create_test_plugin(
    base_dir: Path,
    name: str = "test-plugin",
    language: str = "python",
    generator_version: str | None = GENERATOR_VERSION,
    include_all_files: bool = False,
) -> Path:
    """Create a minimal plugin directory for testing."""
    plugin_dir = base_dir / name
    plugin_dir.mkdir(parents=True)

    # .claude-plugin/plugin.json (required)
    meta_dir = plugin_dir / ".claude-plugin"
    meta_dir.mkdir()
    plugin_json = {
        "name": name,
        "version": "0.1.0",
        "description": "A test plugin for unit testing",
        "author": "Test Author",
        "license": "MIT",
        "keywords": ["test"],
        "repository": "",
    }
    (meta_dir / "plugin.json").write_text(
        json.dumps(plugin_json, indent=2)
    )

    # .claude-plugin/aida-config.json
    aida_config: dict = {
        "config": {},
        "recommendedPermissions": {},
        "agents": [],
        "skills": [],
    }
    if generator_version is not None:
        aida_config["generator_version"] = generator_version
    (meta_dir / "aida-config.json").write_text(
        json.dumps(aida_config, indent=2)
    )

    # Language marker
    if language == "python":
        (plugin_dir / "pyproject.toml").write_text(
            '[project]\nname = "test-plugin"\n'
        )
    else:
        (plugin_dir / "package.json").write_text(
            '{"name": "test-plugin"}\n'
        )

    return plugin_dir


class TestReadPluginMetadata(unittest.TestCase):
    """Test _read_plugin_metadata helper."""

    def test_reads_valid_plugin_json(self):
        """Should read and return parsed plugin.json fields."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(Path(tmp))
            result = _read_plugin_metadata(plugin_dir)

            self.assertEqual(result["name"], "test-plugin")
            self.assertEqual(result["version"], "0.1.0")
            self.assertEqual(result["license"], "MIT")
            self.assertIn("description", result)

    def test_returns_empty_on_missing_file(self):
        """Should return empty dict when plugin.json is absent."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "no-plugin"
            plugin_dir.mkdir()
            result = _read_plugin_metadata(plugin_dir)
            self.assertEqual(result, {})

    def test_returns_empty_on_invalid_json(self):
        """Should return empty dict on malformed JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "bad-json"
            plugin_dir.mkdir()
            meta_dir = plugin_dir / ".claude-plugin"
            meta_dir.mkdir()
            (meta_dir / "plugin.json").write_text(
                "{not valid json!!"
            )
            result = _read_plugin_metadata(plugin_dir)
            self.assertEqual(result, {})


class TestReadGeneratorVersion(unittest.TestCase):
    """Test _read_generator_version helper."""

    def test_reads_version_from_aida_config(self):
        """Should read generator_version from aida-config."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(
                Path(tmp),
                generator_version="1.2.3",
            )
            result = _read_generator_version(plugin_dir)
            self.assertEqual(result, "1.2.3")

    def test_defaults_to_zero_on_missing_file(self):
        """Should return 0.0.0 when aida-config is absent."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "no-config"
            plugin_dir.mkdir()
            (plugin_dir / ".claude-plugin").mkdir()
            result = _read_generator_version(plugin_dir)
            self.assertEqual(result, "0.0.0")

    def test_defaults_to_zero_on_missing_field(self):
        """Should return 0.0.0 when field is absent."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(
                Path(tmp),
                generator_version=None,
            )
            result = _read_generator_version(plugin_dir)
            self.assertEqual(result, "0.0.0")


class TestDetectLanguage(unittest.TestCase):
    """Test _detect_language helper."""

    def test_detects_python_from_pyproject(self):
        """Should detect python from pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "py-plugin"
            plugin_dir.mkdir()
            (plugin_dir / "pyproject.toml").write_text("")
            self.assertEqual(
                _detect_language(plugin_dir), "python"
            )

    def test_detects_typescript_from_package_json(self):
        """Should detect typescript from package.json."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "ts-plugin"
            plugin_dir.mkdir()
            (plugin_dir / "package.json").write_text("{}")
            self.assertEqual(
                _detect_language(plugin_dir), "typescript"
            )

    def test_detects_python_from_scripts_dir(self):
        """Should detect python from scripts/ directory."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "scripts-plugin"
            plugin_dir.mkdir()
            (plugin_dir / "scripts").mkdir()
            self.assertEqual(
                _detect_language(plugin_dir), "python"
            )

    def test_detects_typescript_from_src_dir(self):
        """Should detect typescript from src/ directory."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "src-plugin"
            plugin_dir.mkdir()
            (plugin_dir / "src").mkdir()
            self.assertEqual(
                _detect_language(plugin_dir), "typescript"
            )

    def test_defaults_to_python(self):
        """Should default to python for empty directories."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "empty-plugin"
            plugin_dir.mkdir()
            self.assertEqual(
                _detect_language(plugin_dir), "python"
            )

    def test_metadata_overrides_inference(self):
        """`.claude-plugin/aida-scaffold.json` is preferred over
        filesystem inference (#110).

        Crucially, this lets the update flow honor `language="none"`
        on a skills-only plugin — file-presence inference can't
        distinguish "skills-only" from "Python" since both lack the
        typical TS markers. Without this, `/aida plugin update` on
        a markdown-only plugin would re-scaffold a Python toolchain
        the author explicitly didn't want (#96).
        """
        import json as _json

        # Plugin has pyproject.toml on disk (would infer "python"),
        # but the recorded metadata says "none". Metadata wins.
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "skills-plugin"
            (plugin_dir / ".claude-plugin").mkdir(parents=True)
            (plugin_dir / "pyproject.toml").write_text("")
            (
                plugin_dir / ".claude-plugin" / "aida-scaffold.json"
            ).write_text(
                _json.dumps({
                    "schema_version": 1,
                    "language": "none",
                    "license_id": "MIT",
                })
            )
            self.assertEqual(
                _detect_language(plugin_dir),
                "none",
                "Metadata-recorded language must take precedence "
                "over filesystem inference",
            )

    def test_metadata_with_invalid_language_falls_back(self):
        """If the metadata file has a language we don't recognize
        (typo, future value, etc.), fall back to filesystem
        inference rather than propagating an invalid value.
        """
        import json as _json

        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "weird-plugin"
            (plugin_dir / ".claude-plugin").mkdir(parents=True)
            (plugin_dir / "package.json").write_text("{}")
            (
                plugin_dir / ".claude-plugin" / "aida-scaffold.json"
            ).write_text(
                _json.dumps({
                    "schema_version": 1,
                    "language": "rust",  # not in our supported set
                })
            )
            self.assertEqual(
                _detect_language(plugin_dir),
                "typescript",  # falls back to package.json
            )

    def test_malformed_metadata_file_falls_back(self):
        """A corrupt aida-scaffold.json must not crash detection."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "broken-plugin"
            (plugin_dir / ".claude-plugin").mkdir(parents=True)
            (plugin_dir / "scripts").mkdir()
            (
                plugin_dir / ".claude-plugin" / "aida-scaffold.json"
            ).write_text("{not valid json")
            self.assertEqual(
                _detect_language(plugin_dir),
                "python",  # falls back to scripts/ heuristic
            )


class TestScanPluginValid(unittest.TestCase):
    """Test scan_plugin with a valid plugin directory."""

    @patch.object(
        _context_mod, "infer_git_config",
        return_value=_GIT_MOCK_RETURN,
    )
    def test_scan_reports_correct_plugin_name(
        self, _mock_git
    ):
        """Should report the correct plugin name."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(
                Path(tmp), name="my-scanner-test"
            )
            report = scan_plugin(
                plugin_dir, TEMPLATES_DIR
            )
            self.assertEqual(
                report.plugin_name, "my-scanner-test"
            )

    @patch.object(
        _context_mod, "infer_git_config",
        return_value=_GIT_MOCK_RETURN,
    )
    def test_scan_reports_correct_language(
        self, _mock_git
    ):
        """Should report the detected language."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(Path(tmp))
            report = scan_plugin(
                plugin_dir, TEMPLATES_DIR
            )
            self.assertEqual(report.language, "python")

    @patch.object(
        _context_mod, "infer_git_config",
        return_value=_GIT_MOCK_RETURN,
    )
    def test_scan_reports_generator_version(
        self, _mock_git
    ):
        """Should report the plugin generator_version."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(
                Path(tmp), generator_version="0.5.0"
            )
            report = scan_plugin(
                plugin_dir, TEMPLATES_DIR
            )
            self.assertEqual(
                report.generator_version, "0.5.0"
            )
            self.assertEqual(
                report.current_version, GENERATOR_VERSION
            )

    @patch.object(
        _context_mod, "infer_git_config",
        return_value=_GIT_MOCK_RETURN,
    )
    def test_scan_up_to_date_boilerplate(
        self, _mock_git
    ):
        """Should report files correctly across categories."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(Path(tmp))
            report = scan_plugin(
                plugin_dir, TEMPLATES_DIR
            )
            # The report should have files
            self.assertGreater(len(report.files), 0)
            # Check that summary counts are consistent
            summary = report.summary
            total = (
                summary["missing"]
                + summary["outdated"]
                + summary["up_to_date"]
                + summary["custom_skip"]
            )
            self.assertEqual(total, summary["total"])


class TestScanPluginMissingFiles(unittest.TestCase):
    """Test scan_plugin detects missing files."""

    @patch.object(
        _context_mod, "infer_git_config",
        return_value=_GIT_MOCK_RETURN,
    )
    def test_missing_markdownlint_detected(
        self, _mock_git
    ):
        """Should detect missing .markdownlint.json."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(Path(tmp))
            # Ensure .markdownlint.json does NOT exist
            ml_path = plugin_dir / ".markdownlint.json"
            if ml_path.exists():
                ml_path.unlink()

            report = scan_plugin(
                plugin_dir, TEMPLATES_DIR
            )
            ml_diffs = [
                f
                for f in report.files
                if f.path == ".markdownlint.json"
            ]
            self.assertEqual(len(ml_diffs), 1)
            self.assertEqual(
                ml_diffs[0].status, FileStatus.MISSING
            )

    @patch.object(
        _context_mod, "infer_git_config",
        return_value=_GIT_MOCK_RETURN,
    )
    def test_missing_gitignore_detected(
        self, _mock_git
    ):
        """Should detect missing .gitignore."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(Path(tmp))
            report = scan_plugin(
                plugin_dir, TEMPLATES_DIR
            )
            gi_diffs = [
                f
                for f in report.files
                if f.path == ".gitignore"
            ]
            self.assertEqual(len(gi_diffs), 1)
            self.assertEqual(
                gi_diffs[0].status, FileStatus.MISSING
            )

    @patch.object(
        _context_mod, "infer_git_config",
        return_value=_GIT_MOCK_RETURN,
    )
    def test_missing_makefile_detected(
        self, _mock_git
    ):
        """Should detect missing Makefile."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(Path(tmp))
            report = scan_plugin(
                plugin_dir, TEMPLATES_DIR
            )
            mf_diffs = [
                f
                for f in report.files
                if f.path == "Makefile"
            ]
            self.assertEqual(len(mf_diffs), 1)
            self.assertEqual(
                mf_diffs[0].status, FileStatus.MISSING
            )


class TestScanPluginCustomFiles(unittest.TestCase):
    """Test scan_plugin marks custom files correctly."""

    @patch.object(
        _context_mod, "infer_git_config",
        return_value=_GIT_MOCK_RETURN,
    )
    def test_claudemd_always_custom_skip(
        self, _mock_git
    ):
        """Should mark CLAUDE.md as CUSTOM_SKIP."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(Path(tmp))
            (plugin_dir / "CLAUDE.md").write_text(
                "# Custom content"
            )
            report = scan_plugin(
                plugin_dir, TEMPLATES_DIR
            )
            claude_diffs = [
                f
                for f in report.files
                if f.path == "CLAUDE.md"
            ]
            self.assertEqual(len(claude_diffs), 1)
            self.assertEqual(
                claude_diffs[0].status,
                FileStatus.CUSTOM_SKIP,
            )

    @patch.object(
        _context_mod, "infer_git_config",
        return_value=_GIT_MOCK_RETURN,
    )
    def test_readme_always_custom_skip(
        self, _mock_git
    ):
        """Should mark README.md as CUSTOM_SKIP."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(Path(tmp))
            (plugin_dir / "README.md").write_text(
                "# My Plugin"
            )
            report = scan_plugin(
                plugin_dir, TEMPLATES_DIR
            )
            readme_diffs = [
                f
                for f in report.files
                if f.path == "README.md"
            ]
            self.assertEqual(len(readme_diffs), 1)
            self.assertEqual(
                readme_diffs[0].status,
                FileStatus.CUSTOM_SKIP,
            )

    @patch.object(
        _context_mod, "infer_git_config",
        return_value=_GIT_MOCK_RETURN,
    )
    def test_aida_config_always_custom_skip(
        self, _mock_git
    ):
        """Should mark aida-config.json as CUSTOM_SKIP."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(Path(tmp))
            report = scan_plugin(
                plugin_dir, TEMPLATES_DIR
            )
            aida_diffs = [
                f
                for f in report.files
                if f.path
                == ".claude-plugin/aida-config.json"
            ]
            self.assertEqual(len(aida_diffs), 1)
            self.assertEqual(
                aida_diffs[0].status,
                FileStatus.CUSTOM_SKIP,
            )


class TestScanPluginOutdated(unittest.TestCase):
    """Test scan_plugin detects outdated boilerplate."""

    @patch.object(
        _context_mod, "infer_git_config",
        return_value=_GIT_MOCK_RETURN,
    )
    def test_outdated_boilerplate_detected(
        self, _mock_git
    ):
        """Should detect outdated .markdownlint.json."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(Path(tmp))
            # Write a .markdownlint.json with different
            # content from the template
            (plugin_dir / ".markdownlint.json").write_text(
                '{"old": "config"}\n'
            )
            report = scan_plugin(
                plugin_dir, TEMPLATES_DIR
            )
            ml_diffs = [
                f
                for f in report.files
                if f.path == ".markdownlint.json"
            ]
            self.assertEqual(len(ml_diffs), 1)
            self.assertEqual(
                ml_diffs[0].status, FileStatus.OUTDATED
            )
            self.assertIn(
                "differs", ml_diffs[0].diff_summary
            )


class TestScanPluginInvalid(unittest.TestCase):
    """Test scan_plugin with invalid inputs."""

    @patch.object(
        _context_mod, "infer_git_config",
        return_value=_GIT_MOCK_RETURN,
    )
    def test_raises_on_missing_plugin_json(
        self, _mock_git
    ):
        """Should raise ValueError when plugin.json absent."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp) / "no-manifest"
            plugin_dir.mkdir()
            with self.assertRaises(ValueError) as ctx:
                scan_plugin(plugin_dir, TEMPLATES_DIR)
            self.assertIn(
                "plugin.json", str(ctx.exception)
            )

    @patch.object(
        _context_mod, "infer_git_config",
        return_value=_GIT_MOCK_RETURN,
    )
    def test_raises_on_nonexistent_path(
        self, _mock_git
    ):
        """Should raise ValueError for nonexistent path."""
        bogus = Path("/tmp/does-not-exist-scanner-test")
        with self.assertRaises(ValueError):
            scan_plugin(bogus, TEMPLATES_DIR)


class TestScanPluginDependencyConfig(unittest.TestCase):
    """Test scan_plugin dependency config handling."""

    @patch.object(
        _context_mod, "infer_git_config",
        return_value=_GIT_MOCK_RETURN,
    )
    def test_pyproject_flagged_manual_review(
        self, _mock_git
    ):
        """Should flag pyproject.toml for manual review."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(Path(tmp))
            report = scan_plugin(
                plugin_dir, TEMPLATES_DIR
            )
            pyp_diffs = [
                f
                for f in report.files
                if f.path == "pyproject.toml"
            ]
            self.assertEqual(len(pyp_diffs), 1)
            self.assertEqual(
                pyp_diffs[0].strategy,
                MergeStrategy.MANUAL_REVIEW,
            )
            self.assertEqual(
                pyp_diffs[0].category,
                FileCategory.DEPENDENCY_CONFIG,
            )
            # File exists so should be UP_TO_DATE
            self.assertEqual(
                pyp_diffs[0].status,
                FileStatus.UP_TO_DATE,
            )


class TestScanPluginComposites(unittest.TestCase):
    """Test scan_plugin composite file handling."""

    @patch.object(
        _context_mod, "infer_git_config",
        return_value=_GIT_MOCK_RETURN,
    )
    def test_gitignore_missing_entries_detected(
        self, _mock_git
    ):
        """Should detect .gitignore with missing entries."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(Path(tmp))
            # Write a minimal .gitignore that's missing
            # most expected entries
            (plugin_dir / ".gitignore").write_text(
                "node_modules/\n"
            )
            report = scan_plugin(
                plugin_dir, TEMPLATES_DIR
            )
            gi_diffs = [
                f
                for f in report.files
                if f.path == ".gitignore"
            ]
            self.assertEqual(len(gi_diffs), 1)
            self.assertEqual(
                gi_diffs[0].status, FileStatus.OUTDATED
            )
            self.assertIn(
                "Missing", gi_diffs[0].diff_summary
            )
            self.assertIn(
                "entries", gi_diffs[0].diff_summary
            )

    @patch.object(
        _context_mod, "infer_git_config",
        return_value=_GIT_MOCK_RETURN,
    )
    def test_makefile_missing_targets_detected(
        self, _mock_git
    ):
        """Should detect Makefile with missing targets."""
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = _create_test_plugin(Path(tmp))
            # Write a minimal Makefile missing most targets
            (plugin_dir / "Makefile").write_text(
                "help:\n\t@echo help\n"
            )
            report = scan_plugin(
                plugin_dir, TEMPLATES_DIR
            )
            mf_diffs = [
                f
                for f in report.files
                if f.path == "Makefile"
            ]
            self.assertEqual(len(mf_diffs), 1)
            self.assertEqual(
                mf_diffs[0].status, FileStatus.OUTDATED
            )
            self.assertIn(
                "Missing", mf_diffs[0].diff_summary
            )
            self.assertIn(
                "targets", mf_diffs[0].diff_summary
            )


if __name__ == "__main__":
    unittest.main()
