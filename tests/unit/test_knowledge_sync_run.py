# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""End-to-end tests for the knowledge-sync runner (#22)."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root / "scripts"))
sys.path.insert(
    0,
    str(_project_root / "skills" / "knowledge-sync" / "scripts"),
)

import sync as sync_mod  # noqa: E402


def _build_project(tmp: Path, *, agent: str = "demo-agent"):
    """Lay out a minimal project: source file + agent knowledge file
    with a marker block + sources.yml that connects them.
    """
    proj = tmp / "proj"
    (proj / "docs").mkdir(parents=True)
    (proj / "agents" / agent / "knowledge").mkdir(parents=True)

    source_path = proj / "docs" / "upstream.md"
    source_path.write_text("Upstream content v1\n", encoding="utf-8")

    knowledge_path = (
        proj / "agents" / agent / "knowledge" / "topic.md"
    )
    knowledge_path.write_text(
        "# Topic\n\nIntro from the author.\n\n"
        '<!-- upstream:start name="topic-overview" -->\n'
        "OLD upstream body\n"
        "<!-- upstream:end -->\n\n"
        "Custom conclusion — never touched.\n",
        encoding="utf-8",
    )

    sources_yml = (
        proj / "agents" / agent / "knowledge" / "sources.yml"
    )
    sources_yml.write_text(
        "sources:\n"
        "  - name: upstream-md\n"
        "    type: local\n"
        "    path: docs/upstream.md\n"
        "    target:\n"
        "      file: knowledge/topic.md\n"
        "      section: topic-overview\n",
        encoding="utf-8",
    )
    return proj, source_path, knowledge_path


class TestSyncRun(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_apply_replaces_section_body(self):
        proj, src, dst = _build_project(self.tmp)
        report = sync_mod.run(
            project_root=proj, agent="demo-agent", dry_run=False
        )
        self.assertTrue(report["success"])
        self.assertEqual(len(report["results"]), 1)
        self.assertEqual(report["results"][0]["status"], "changed")

        new_content = dst.read_text(encoding="utf-8")
        self.assertIn("Upstream content v1", new_content)
        self.assertNotIn("OLD upstream body", new_content)
        # Outside-marker content preserved
        self.assertIn("Intro from the author.", new_content)
        self.assertIn(
            "Custom conclusion — never touched.", new_content
        )

    def test_dry_run_reports_would_change_without_writing(self):
        proj, src, dst = _build_project(self.tmp)
        original = dst.read_text(encoding="utf-8")
        report = sync_mod.run(
            project_root=proj, agent="demo-agent", dry_run=True
        )
        self.assertTrue(report["success"])
        self.assertEqual(
            report["results"][0]["status"], "would-change"
        )
        # File untouched
        self.assertEqual(
            dst.read_text(encoding="utf-8"), original
        )

    def test_unchanged_when_source_matches_body(self):
        proj, src, dst = _build_project(self.tmp)
        # Make the upstream body match what's already inside
        # the markers (sans trailing newline).
        src.write_text("OLD upstream body\n", encoding="utf-8")
        report = sync_mod.run(
            project_root=proj, agent="demo-agent", dry_run=False
        )
        self.assertTrue(report["success"])
        self.assertEqual(
            report["results"][0]["status"], "unchanged"
        )

    def test_missing_source_file_reports_source_missing(self):
        proj, src, dst = _build_project(self.tmp)
        src.unlink()
        report = sync_mod.run(
            project_root=proj, agent="demo-agent", dry_run=False
        )
        self.assertFalse(report["success"])
        self.assertEqual(
            report["results"][0]["status"], "source-missing"
        )

    def test_missing_target_section_reports_missing_section(self):
        proj, src, dst = _build_project(self.tmp)
        # Wipe the markers from the target file
        dst.write_text(
            "# Topic\n\nNo markers here.\n",
            encoding="utf-8",
        )
        report = sync_mod.run(
            project_root=proj, agent="demo-agent", dry_run=False
        )
        self.assertFalse(report["success"])
        self.assertEqual(
            report["results"][0]["status"], "missing-section"
        )

    def test_no_sources_yml_succeeds_with_empty_results(self):
        proj = self.tmp / "proj"
        (proj / "agents" / "x" / "knowledge").mkdir(parents=True)
        report = sync_mod.run(
            project_root=proj, agent="x", dry_run=False
        )
        self.assertTrue(report["success"])
        self.assertEqual(report["results"], [])
        self.assertIn("No sources declared", report["message"])

    def test_malformed_sources_yml_reports_error(self):
        proj = self.tmp / "proj"
        kdir = proj / "agents" / "x" / "knowledge"
        kdir.mkdir(parents=True)
        (kdir / "sources.yml").write_text(
            "[not valid yaml\n", encoding="utf-8"
        )
        report = sync_mod.run(
            project_root=proj, agent="x", dry_run=False
        )
        self.assertFalse(report["success"])
        self.assertIn("not valid YAML", report["message"])

    def test_invalid_target_reports_invalid_target(self):
        proj = self.tmp / "proj"
        kdir = proj / "agents" / "x" / "knowledge"
        kdir.mkdir(parents=True)
        (kdir / "sources.yml").write_text(
            "sources:\n"
            "  - name: bad\n"
            "    type: local\n"
            "    path: nowhere.md\n"
            # Missing target.file + section
            "    target: {}\n",
            encoding="utf-8",
        )
        report = sync_mod.run(
            project_root=proj, agent="x", dry_run=False
        )
        self.assertFalse(report["success"])
        self.assertEqual(
            report["results"][0]["status"], "invalid-target"
        )


if __name__ == "__main__":
    unittest.main()
