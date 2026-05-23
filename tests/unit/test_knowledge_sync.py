# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for knowledge-file section sync primitives (#22)."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root / "scripts"))

from shared.knowledge_sync import (  # noqa: E402
    KnowledgeSyncError,
    diff_summary,
    fence_section,
    find_sections,
    get_section_bodies,
    read_local_source,
    update_section,
)


def _doc(sections: list[tuple[str, str]]) -> str:
    """Build a markdown doc with the given (name, body) sections."""
    parts = ["# Doc\n\nSome intro.\n"]
    for name, body in sections:
        parts.append(
            f'\n<!-- upstream:start name="{name}" -->\n'
            f"{body}\n"
            f"<!-- upstream:end -->\n"
        )
    parts.append("\nSome outro.\n")
    return "".join(parts)


class TestFindSections(unittest.TestCase):
    def test_no_sections(self):
        self.assertEqual(find_sections("just markdown\n"), [])

    def test_single_section(self):
        content = _doc([("alpha", "alpha body")])
        sections = find_sections(content)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].name, "alpha")
        self.assertEqual(
            content[
                sections[0].body_start:sections[0].body_end
            ],
            "alpha body",
        )

    def test_multiple_sections_ordered(self):
        content = _doc(
            [("alpha", "a body"), ("beta", "b body")]
        )
        sections = find_sections(content)
        self.assertEqual(
            [s.name for s in sections], ["alpha", "beta"]
        )

    def test_unbalanced_raises(self):
        content = '<!-- upstream:start name="x" -->\nbody\n'
        with self.assertRaises(KnowledgeSyncError):
            find_sections(content)

    def test_nested_raises(self):
        content = (
            '<!-- upstream:start name="outer" -->\n'
            '<!-- upstream:start name="inner" -->\n'
            "body\n"
            "<!-- upstream:end -->\n"
            "<!-- upstream:end -->\n"
        )
        with self.assertRaises(KnowledgeSyncError):
            find_sections(content)

    def test_duplicate_names_raise(self):
        content = (
            '<!-- upstream:start name="x" -->\na\n'
            "<!-- upstream:end -->\n"
            '<!-- upstream:start name="x" -->\nb\n'
            "<!-- upstream:end -->\n"
        )
        with self.assertRaises(KnowledgeSyncError):
            find_sections(content)


class TestGetSectionBodies(unittest.TestCase):
    def test_returns_named_bodies(self):
        content = _doc(
            [("alpha", "a body"), ("beta", "b body")]
        )
        self.assertEqual(
            get_section_bodies(content),
            {"alpha": "a body", "beta": "b body"},
        )

    def test_empty_when_no_sections(self):
        self.assertEqual(get_section_bodies("nothing"), {})


class TestUpdateSection(unittest.TestCase):
    def test_replaces_body(self):
        content = _doc([("x", "old")])
        new_content, changed = update_section(
            content, "x", "new content"
        )
        self.assertTrue(changed)
        self.assertIn("new content", new_content)
        self.assertNotIn("old\n<!-- upstream:end -->", new_content)
        # Outside content untouched
        self.assertIn("Some intro.", new_content)
        self.assertIn("Some outro.", new_content)

    def test_no_change_on_identical_body(self):
        content = _doc([("x", "same")])
        new_content, changed = update_section(
            content, "x", "same"
        )
        self.assertFalse(changed)
        self.assertEqual(new_content, content)

    def test_missing_section_raises(self):
        content = _doc([("x", "old")])
        with self.assertRaises(KnowledgeSyncError) as cm:
            update_section(content, "y", "anything")
        self.assertIn("No upstream section named 'y'", str(cm.exception))

    def test_markers_preserved_byte_for_byte(self):
        """Updating a section body must not touch the markers
        themselves (other tooling may rely on the exact marker
        whitespace)."""
        content = (
            "intro\n"
            '<!-- upstream:start name="keep" -->\n'
            "old body\n"
            "<!-- upstream:end -->\n"
            "outro\n"
        )
        new_content, changed = update_section(
            content, "keep", "new body"
        )
        self.assertTrue(changed)
        self.assertEqual(
            new_content,
            "intro\n"
            '<!-- upstream:start name="keep" -->\n'
            "new body\n"
            "<!-- upstream:end -->\n"
            "outro\n",
        )


class TestDiffSummary(unittest.TestCase):
    def test_reports_changed_unchanged_missing(self):
        content = _doc(
            [("alpha", "a old"), ("beta", "b same")]
        )
        updates = {
            "alpha": "a new",
            "beta": "b same",
            "gamma": "g new",
        }
        result = diff_summary(content, updates)
        # Sorted by name
        self.assertEqual(
            [r["name"] for r in result], ["alpha", "beta", "gamma"]
        )
        statuses = {r["name"]: r["status"] for r in result}
        self.assertEqual(statuses["alpha"], "changed")
        self.assertEqual(statuses["beta"], "unchanged")
        self.assertEqual(statuses["gamma"], "missing")


class TestFenceSection(unittest.TestCase):
    def test_renders_block(self):
        out = fence_section("foo", "body line")
        self.assertEqual(
            out,
            '<!-- upstream:start name="foo" -->\n'
            "body line\n"
            "<!-- upstream:end -->",
        )

    def test_strips_extra_newlines(self):
        out = fence_section("foo", "\n\nbody\n\n")
        self.assertEqual(
            out,
            '<!-- upstream:start name="foo" -->\n'
            "body\n"
            "<!-- upstream:end -->",
        )

    def test_rejects_bad_names(self):
        for bad in ("", "has space", "has/slash", "weird!"):
            with self.assertRaises(KnowledgeSyncError):
                fence_section(bad, "body")


class TestReadLocalSource(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_reads_existing_file(self):
        p = Path(self.tmp) / "src.md"
        p.write_text("hello\n", encoding="utf-8")
        self.assertEqual(read_local_source(str(p)), "hello\n")

    def test_missing_file_returns_none(self):
        self.assertIsNone(
            read_local_source(str(Path(self.tmp) / "nope.md"))
        )

    def test_directory_returns_none(self):
        # is_file() is False for directories
        self.assertIsNone(read_local_source(self.tmp))


if __name__ == "__main__":
    unittest.main()
