# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for the project-context split/merge helpers (issue #65)."""

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(
    0, str(Path(__file__).parent.parent.parent / "skills" / "aida" / "scripts")
)

from utils import (  # noqa: E402
    PROJECT_CONTEXT_FILE,
    PROJECT_CONTEXT_LOCAL_FILE,
    ConfigurationError,
    ensure_gitignore_entry,
    load_project_context,
    merge_context,
    split_context,
    write_project_context,
)


def _sample_merged():
    """Return a representative merged config dict."""
    return {
        "version": "0.2.0",
        "last_updated": "2026-04-28T00:00:00+00:00",
        "config_complete": True,
        "project_name": "demo",
        "project_root": "/Users/alice/Developer/demo",
        "vcs": {
            "type": "git",
            "has_vcs": True,
            "uses_worktrees": False,
            "remote_url": "git@github.com:alice/demo.git",
            "is_github": True,
            "is_gitlab": False,
        },
        "files": {"has_readme": True, "has_license": True},
        "languages": {"primary": "Python", "all": ["Python"]},
        "preferences": {
            "branching_model": "GitHub Flow",
            "issue_tracking": "GitHub Issues",
        },
    }


class TestSplitContext(unittest.TestCase):
    """split_context separates user-specific data from project-level data."""

    def test_user_specific_top_level_keys_go_to_local(self):
        project, local = split_context(_sample_merged())
        self.assertIn("project_root", local)
        self.assertIn("last_updated", local)
        self.assertIn("config_complete", local)
        self.assertNotIn("project_root", project)
        self.assertNotIn("last_updated", project)
        self.assertNotIn("config_complete", project)

    def test_vcs_remote_url_moves_to_local(self):
        project, local = split_context(_sample_merged())
        self.assertEqual(local["vcs"], {"remote_url": "git@github.com:alice/demo.git"})
        # Project keeps the rest of vcs
        self.assertEqual(project["vcs"]["type"], "git")
        self.assertTrue(project["vcs"]["is_github"])
        self.assertNotIn("remote_url", project["vcs"])

    def test_project_level_keys_stay_in_project(self):
        project, _ = split_context(_sample_merged())
        self.assertEqual(project["project_name"], "demo")
        self.assertEqual(project["languages"]["primary"], "Python")
        self.assertEqual(project["preferences"]["branching_model"], "GitHub Flow")
        self.assertEqual(project["files"]["has_readme"], True)

    def test_split_drops_empty_vcs_in_local_when_no_remote(self):
        merged = _sample_merged()
        del merged["vcs"]["remote_url"]
        _, local = split_context(merged)
        self.assertNotIn("vcs", local)

    def test_split_handles_missing_optional_sections(self):
        merged = {"project_name": "minimal", "version": "0.2.0"}
        project, local = split_context(merged)
        self.assertEqual(project, {"project_name": "minimal", "version": "0.2.0"})
        self.assertEqual(local, {})


class TestMergeContext(unittest.TestCase):
    """merge_context recombines project + local back into a single dict."""

    def test_round_trip_split_then_merge(self):
        original = _sample_merged()
        project, local = split_context(original)
        merged = merge_context(project, local)
        self.assertEqual(merged, original)

    def test_local_overrides_project_at_leaf(self):
        project = {"project_name": "from-project"}
        local = {"project_name": "from-local"}
        merged = merge_context(project, local)
        self.assertEqual(merged["project_name"], "from-local")

    def test_nested_dict_merge_is_shallow(self):
        project = {"vcs": {"type": "git", "is_github": True}}
        local = {"vcs": {"remote_url": "git@example.com:x/y.git"}}
        merged = merge_context(project, local)
        self.assertEqual(merged["vcs"]["type"], "git")
        self.assertEqual(merged["vcs"]["is_github"], True)
        self.assertEqual(merged["vcs"]["remote_url"], "git@example.com:x/y.git")

    def test_merge_does_not_mutate_inputs(self):
        project = {"vcs": {"type": "git"}}
        local = {"vcs": {"remote_url": "x"}}
        merge_context(project, local)
        self.assertNotIn("remote_url", project["vcs"])


class TestLoadProjectContext(unittest.TestCase):
    """load_project_context reads and merges from disk."""

    def test_reads_both_files_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claude = root / ".claude"
            claude.mkdir()
            (claude / PROJECT_CONTEXT_FILE).write_text(
                yaml.dump({"project_name": "x", "vcs": {"type": "git"}}),
                encoding="utf-8",
            )
            (claude / PROJECT_CONTEXT_LOCAL_FILE).write_text(
                yaml.dump({"project_root": str(root), "vcs": {"remote_url": "u"}}),
                encoding="utf-8",
            )
            merged = load_project_context(root)
            self.assertEqual(merged["project_name"], "x")
            self.assertEqual(merged["project_root"], str(root))
            self.assertEqual(merged["vcs"]["type"], "git")
            self.assertEqual(merged["vcs"]["remote_url"], "u")

    def test_legacy_single_file_stamps_schema_version(self):
        """Existing projects with everything in .yml still work.

        After #39, the loader stamps `schema_version` on read so
        callers always see a current-version dict. Original keys
        (including the legacy `version` field) are preserved.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claude = root / ".claude"
            claude.mkdir()
            legacy = _sample_merged()
            (claude / PROJECT_CONTEXT_FILE).write_text(
                yaml.dump(legacy), encoding="utf-8"
            )
            merged = load_project_context(root)
            # Every original key is preserved.
            for k, v in legacy.items():
                self.assertEqual(merged[k], v)
            # Plus schema_version stamped to current.
            from utils.project_context import (
                PROJECT_CONTEXT_SCHEMA_VERSION,
            )
            self.assertEqual(
                merged["schema_version"],
                PROJECT_CONTEXT_SCHEMA_VERSION,
            )

    def test_no_files_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_project_context(Path(tmp)), {})

    def test_malformed_yaml_raises_configuration_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claude = root / ".claude"
            claude.mkdir()
            (claude / PROJECT_CONTEXT_FILE).write_text(
                "[unclosed list\n", encoding="utf-8"
            )
            with self.assertRaises(ConfigurationError):
                load_project_context(root)


class TestWriteProjectContext(unittest.TestCase):
    """write_project_context writes the split files atomically."""

    def test_writes_both_files_with_correct_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            project_path, local_path = write_project_context(root, _sample_merged())

            self.assertTrue(project_path.exists())
            self.assertTrue(local_path.exists())

            committed = yaml.safe_load(project_path.read_text())
            local = yaml.safe_load(local_path.read_text())

            self.assertNotIn("project_root", committed)
            self.assertNotIn("last_updated", committed)
            self.assertNotIn("remote_url", committed["vcs"])

            self.assertIn("project_root", local)
            self.assertEqual(local["vcs"]["remote_url"], "git@github.com:alice/demo.git")

    def test_round_trip_via_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            original = _sample_merged()
            write_project_context(root, original)
            reloaded = load_project_context(root)
            # All original keys round-trip; the loader additionally
            # stamps schema_version (#39) so we compare keys-wise
            # rather than requiring exact equality.
            for k, v in original.items():
                self.assertEqual(reloaded[k], v)
            from utils.project_context import (
                PROJECT_CONTEXT_SCHEMA_VERSION,
            )
            self.assertEqual(
                reloaded["schema_version"],
                PROJECT_CONTEXT_SCHEMA_VERSION,
            )

    def test_legacy_to_split_migration_on_write(self):
        """A single-file legacy project is split on next write."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / PROJECT_CONTEXT_FILE).write_text(
                yaml.dump(_sample_merged()), encoding="utf-8"
            )
            self.assertFalse((root / ".claude" / PROJECT_CONTEXT_LOCAL_FILE).exists())

            merged = load_project_context(root)
            write_project_context(root, merged)

            committed = yaml.safe_load(
                (root / ".claude" / PROJECT_CONTEXT_FILE).read_text()
            )
            local = yaml.safe_load(
                (root / ".claude" / PROJECT_CONTEXT_LOCAL_FILE).read_text()
            )
            self.assertNotIn("project_root", committed)
            self.assertIn("project_root", local)


class TestEnsureGitignoreEntry(unittest.TestCase):
    """ensure_gitignore_entry adds the .local file to .gitignore idempotently."""

    def test_appends_entry_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
            modified = ensure_gitignore_entry(root)
            self.assertTrue(modified)
            content = (root / ".gitignore").read_text()
            self.assertIn(".claude/aida-project-context.local.yml", content)

    def test_idempotent_when_entry_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".gitignore").write_text(
                "*.pyc\n.claude/aida-project-context.local.yml\n",
                encoding="utf-8",
            )
            modified = ensure_gitignore_entry(root)
            self.assertFalse(modified)

    def test_no_op_when_no_gitignore(self):
        """Don't create a .gitignore — that's the project's call."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            modified = ensure_gitignore_entry(root)
            self.assertFalse(modified)
            self.assertFalse((root / ".gitignore").exists())

    def test_appends_with_newline_when_file_lacks_trailing_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".gitignore").write_text("*.pyc", encoding="utf-8")
            ensure_gitignore_entry(root)
            content = (root / ".gitignore").read_text()
            self.assertTrue(content.startswith("*.pyc\n"))
            self.assertIn(".claude/aida-project-context.local.yml", content)


class TestSchemaVersioning(unittest.TestCase):
    """Test the schema versioning + migration framework (#39)."""

    def test_current_version_is_a_string(self):
        from utils.project_context import (
            PROJECT_CONTEXT_SCHEMA_VERSION,
        )
        self.assertIsInstance(PROJECT_CONTEXT_SCHEMA_VERSION, str)
        # Loose semver shape so callers can string-compare.
        parts = PROJECT_CONTEXT_SCHEMA_VERSION.split(".")
        self.assertEqual(len(parts), 3)
        for p in parts:
            int(p)  # must parse as integer

    def test_migrate_stamps_current_on_empty_legacy_dict(self):
        """A config with no schema_version gets stamped to current."""
        from utils.project_context import (
            PROJECT_CONTEXT_SCHEMA_VERSION,
            migrate_to_current,
        )
        out = migrate_to_current({"project_name": "demo"})
        self.assertEqual(
            out["schema_version"], PROJECT_CONTEXT_SCHEMA_VERSION
        )
        self.assertEqual(out["project_name"], "demo")

    def test_migrate_preserves_existing_schema_version(self):
        """A config already at the current version is unchanged."""
        from utils.project_context import (
            PROJECT_CONTEXT_SCHEMA_VERSION,
            migrate_to_current,
        )
        data = {
            "schema_version": PROJECT_CONTEXT_SCHEMA_VERSION,
            "project_name": "x",
        }
        out = migrate_to_current(data)
        self.assertEqual(out, data)

    def test_migrate_warns_on_newer_schema(self):
        """Reading a config from a future AIDA version logs a
        warning but returns the dict as-is (best-effort
        forward-compat)."""
        import logging
        from utils.project_context import migrate_to_current

        future = {
            "schema_version": "99.0.0",
            "project_name": "x",
            "future_only_field": "stuff",
        }
        with self.assertLogs(
            "utils.project_context", level=logging.WARNING
        ) as cm:
            out = migrate_to_current(future)
        # Original fields preserved
        self.assertEqual(out["project_name"], "x")
        self.assertEqual(out["future_only_field"], "stuff")
        # Warning logged
        self.assertTrue(
            any("newer than" in m for m in cm.output)
        )

    def test_migrate_empty_dict_returns_empty(self):
        """Empty config (no .yml files) skips migration cleanly."""
        from utils.project_context import migrate_to_current
        self.assertEqual(migrate_to_current({}), {})

    def test_legacy_version_field_treated_as_one_dot_zero(self):
        """Pre-#39 files stamped `version: <app-version>` are
        treated as schema 1.0.0 (the shape is identical)."""
        from utils.project_context import (
            PROJECT_CONTEXT_SCHEMA_VERSION,
            migrate_to_current,
        )
        legacy = {
            "version": "0.7.0",  # was app version, not schema
            "project_name": "demo",
        }
        out = migrate_to_current(legacy)
        # schema_version stamped to current
        self.assertEqual(
            out["schema_version"], PROJECT_CONTEXT_SCHEMA_VERSION
        )
        # Original `version` field preserved (it's a legacy app
        # version stamp, harmless to keep around)
        self.assertEqual(out["version"], "0.7.0")
        self.assertEqual(out["project_name"], "demo")

    def test_write_reads_back_with_schema_version(self):
        """end-to-end: write a config, read it back, schema_version
        is present even if the source dict didn't have it."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            # Source dict has NO schema_version (typical for a
            # caller that just built a fresh context)
            source = {
                "project_name": "demo",
                "vcs": {"type": "git"},
            }
            write_project_context(root, source)
            reloaded = load_project_context(root)
            from utils.project_context import (
                PROJECT_CONTEXT_SCHEMA_VERSION,
            )
            self.assertEqual(
                reloaded["schema_version"],
                PROJECT_CONTEXT_SCHEMA_VERSION,
            )


if __name__ == "__main__":
    unittest.main()
