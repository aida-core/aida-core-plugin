# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Tests for the decision-log primitives (#144 Slice 1)."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root / "scripts"))

from shared.decisions_log import (  # noqa: E402
    DECISIONS_JSON_FILENAME,
    DECISIONS_MD_FILENAME,
    SCHEMA_VERSION,
    Decision,
    find_by_url,
    now_iso,
    read_decisions,
    upsert_decision,
    write_decisions,
)


class TestDecisionToDict(unittest.TestCase):
    def test_omits_none_and_default_locked(self):
        d = Decision(url="https://x.test/a", status="pending")
        data = d.to_dict()
        self.assertEqual(
            data,
            {"url": "https://x.test/a", "status": "pending"},
        )

    def test_includes_metadata_when_set(self):
        d = Decision(
            url="https://x.test/a",
            status="in-use",
            decided_at="2026-05-28T00:00:00+00:00",
            decided_by="llm",
            locked=True,
            informs=["skills.md"],
            reason="Authoritative spec",
        )
        data = d.to_dict()
        self.assertEqual(data["locked"], True)
        self.assertEqual(data["informs"], ["skills.md"])
        self.assertEqual(data["reason"], "Authoritative spec")


class TestAtomicWrite(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_writes_both_files(self):
        decisions = [
            Decision(
                url="https://x.test/a",
                status="in-use",
                decided_at="2026-05-28T00:00:00+00:00",
                decided_by="llm",
                reason="Useful",
                informs=["skills.md"],
            )
        ]
        write_decisions(self.tmp, decisions)
        self.assertTrue(
            (self.tmp / DECISIONS_JSON_FILENAME).is_file()
        )
        self.assertTrue(
            (self.tmp / DECISIONS_MD_FILENAME).is_file()
        )

    def test_json_includes_schema_version(self):
        write_decisions(
            self.tmp,
            [Decision(url="https://x.test/a", status="pending")],
        )
        data = json.loads(
            (self.tmp / DECISIONS_JSON_FILENAME).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(data["version"], SCHEMA_VERSION)
        self.assertEqual(len(data["decisions"]), 1)

    def test_md_has_generated_banner(self):
        write_decisions(
            self.tmp,
            [Decision(url="https://x.test/a", status="pending")],
        )
        md = (self.tmp / DECISIONS_MD_FILENAME).read_text(
            encoding="utf-8"
        )
        self.assertTrue(
            md.startswith("<!-- GENERATED")
        )
        self.assertIn("do not edit by hand", md)

    def test_md_groups_by_status(self):
        decisions = [
            Decision(
                url="https://x.test/in",
                status="in-use",
                reason="keep",
            ),
            Decision(
                url="https://x.test/rej",
                status="rejected",
                reason="drop",
            ),
            Decision(
                url="https://x.test/pen",
                status="pending",
            ),
        ]
        write_decisions(self.tmp, decisions)
        md = (self.tmp / DECISIONS_MD_FILENAME).read_text(
            encoding="utf-8"
        )
        self.assertIn("## In-use", md)
        self.assertIn("## Rejected", md)
        self.assertIn("## Pending", md)
        # URLs land under their section
        in_pos = md.index("## In-use")
        rej_pos = md.index("## Rejected")
        pen_pos = md.index("## Pending")
        self.assertLess(in_pos, rej_pos)
        self.assertLess(rej_pos, pen_pos)
        self.assertLess(md.index("https://x.test/in"), rej_pos)
        self.assertLess(md.index("https://x.test/rej"), pen_pos)
        self.assertGreater(md.index("https://x.test/pen"), pen_pos)

    def test_round_trip(self):
        original = [
            Decision(
                url="https://x.test/a",
                status="in-use",
                decided_at=now_iso(),
                decided_by="human",
                locked=True,
                reason="confirmed",
                informs=["a.md", "b.md"],
            ),
            Decision(
                url="https://x.test/b",
                status="rejected",
                decided_at=now_iso(),
                decided_by="llm",
                reason="out of scope",
            ),
            Decision(
                url="https://x.test/c",
                status="pending",
                discovered_at=now_iso(),
                source_root="some-site",
            ),
        ]
        write_decisions(self.tmp, original)
        loaded = read_decisions(self.tmp)
        self.assertEqual(len(loaded), 3)
        # Lookup by URL since order is now sorted
        by_url = {d.url: d for d in loaded}
        self.assertEqual(by_url["https://x.test/a"].status, "in-use")
        self.assertTrue(by_url["https://x.test/a"].locked)
        self.assertEqual(
            by_url["https://x.test/a"].informs, ["a.md", "b.md"]
        )
        self.assertEqual(
            by_url["https://x.test/c"].source_root, "some-site"
        )


class TestReadDecisions(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_file_returns_empty(self):
        self.assertEqual(read_decisions(self.tmp), [])

    def test_malformed_json_raises(self):
        (self.tmp / DECISIONS_JSON_FILENAME).write_text(
            "{not valid", encoding="utf-8"
        )
        with self.assertRaises(ValueError) as ctx:
            read_decisions(self.tmp)
        self.assertIn("not valid JSON", str(ctx.exception))

    def test_wrong_schema_version_raises(self):
        (self.tmp / DECISIONS_JSON_FILENAME).write_text(
            json.dumps({"version": "9.9.9", "decisions": []}),
            encoding="utf-8",
        )
        with self.assertRaises(ValueError) as ctx:
            read_decisions(self.tmp)
        self.assertIn("version=", str(ctx.exception))

    def test_invalid_status_raises(self):
        (self.tmp / DECISIONS_JSON_FILENAME).write_text(
            json.dumps(
                {
                    "version": SCHEMA_VERSION,
                    "decisions": [
                        {"url": "https://x.test/a", "status": "weird"}
                    ],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(ValueError) as ctx:
            read_decisions(self.tmp)
        self.assertIn("invalid status", str(ctx.exception))


class TestUpsertDecision(unittest.TestCase):
    def test_appends_new_url(self):
        existing = [
            Decision(url="https://x.test/a", status="pending"),
        ]
        new = Decision(url="https://x.test/b", status="pending")
        out = upsert_decision(existing, new)
        self.assertEqual(len(out), 2)
        # Input list not mutated
        self.assertEqual(len(existing), 1)

    def test_replaces_existing_url(self):
        existing = [
            Decision(url="https://x.test/a", status="pending"),
        ]
        new = Decision(
            url="https://x.test/a",
            status="in-use",
            reason="approved",
        )
        out = upsert_decision(existing, new)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].status, "in-use")
        self.assertEqual(out[0].reason, "approved")


class TestFindByUrl(unittest.TestCase):
    def test_match(self):
        decisions = [
            Decision(url="https://x.test/a", status="pending"),
            Decision(url="https://x.test/b", status="in-use"),
        ]
        result = find_by_url(decisions, "https://x.test/b")
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "in-use")

    def test_no_match(self):
        self.assertIsNone(find_by_url([], "https://x.test/a"))


if __name__ == "__main__":
    unittest.main()
