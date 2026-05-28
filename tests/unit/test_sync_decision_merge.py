# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Tests for sync's decision-log merge behavior (#144 Slice 2)."""

from __future__ import annotations

import shutil
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import responses

_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root / "scripts"))
sys.path.insert(
    0,
    str(_project_root / "skills" / "knowledge-sync" / "scripts"),
)

from shared import http_source  # noqa: E402
from shared.decisions_log import (  # noqa: E402
    Decision,
    write_decisions,
)

import sync as sync_mod  # noqa: E402


def _public_getaddrinfo(host, *_a, **_kw):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.10", 0))]


def _build_project(
    tmp: Path,
    *,
    agent: str = "demo-agent",
    sources_yml: str = "sources: []\n",
):
    proj = tmp / "proj"
    knowledge = proj / "agents" / agent / "knowledge"
    knowledge.mkdir(parents=True)
    (knowledge / "sources.yml").write_text(
        sources_yml, encoding="utf-8"
    )
    return proj, knowledge


def _seed_target_file(knowledge: Path, section: str = "remote") -> Path:
    target = knowledge / "topic.md"
    target.write_text(
        "# Topic\n\n"
        f'<!-- upstream:start name="{section}" -->\n'
        "OLD body\n"
        "<!-- upstream:end -->\n",
        encoding="utf-8",
    )
    return target


class _MergeFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cache_dir = self.tmp / "cache"
        self._cache_patch = mock.patch.object(
            http_source, "KNOWLEDGE_SYNC_CACHE_DIR", self.cache_dir
        )
        self._cache_patch.start()

    def tearDown(self):
        self._cache_patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestInUseMergedIntoSync(_MergeFixture):
    @responses.activate
    def test_in_use_decision_synced_alongside_sources_yml(self):
        responses.get(
            "https://x.test/page",
            body="# Fresh body",
            content_type="text/markdown",
        )
        proj, knowledge = _build_project(self.tmp)
        _seed_target_file(knowledge, section="remote")
        write_decisions(
            knowledge,
            [
                Decision(
                    url="https://x.test/page",
                    status="in-use",
                    decided_at="2026-05-28T00:00:00+00:00",
                    decided_by="llm",
                    target_file="topic.md",
                    target_section="remote",
                )
            ],
        )
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            report = sync_mod.run(
                project_root=proj, agent="demo-agent"
            )
        self.assertTrue(report["success"])
        # Find the result for our decision-materialized source
        result = next(
            r
            for r in report["results"]
            if r["name"].startswith("decision:")
        )
        self.assertEqual(result["status"], "changed")
        new_content = (knowledge / "topic.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Fresh body", new_content)
        self.assertNotIn("OLD body", new_content)

    def test_pending_decisions_not_synced(self):
        # No HTTP mock — sync shouldn't even try to fetch a pending URL
        proj, knowledge = _build_project(self.tmp)
        _seed_target_file(knowledge, section="remote")
        write_decisions(
            knowledge,
            [
                Decision(
                    url="https://x.test/page",
                    status="pending",
                    discovered_at="2026-05-28T00:00:00+00:00",
                    target_file="topic.md",
                    target_section="remote",
                )
            ],
        )
        report = sync_mod.run(
            project_root=proj, agent="demo-agent"
        )
        self.assertTrue(report["success"])
        # No materialized result; sources.yml is empty
        self.assertNotIn(
            "decision:https://x.test/page",
            [r["name"] for r in report["results"]],
        )

    def test_rejected_decisions_not_synced(self):
        proj, knowledge = _build_project(self.tmp)
        _seed_target_file(knowledge, section="remote")
        write_decisions(
            knowledge,
            [
                Decision(
                    url="https://x.test/page",
                    status="rejected",
                    decided_at="2026-05-28T00:00:00+00:00",
                    decided_by="llm",
                    target_file="topic.md",
                    target_section="remote",
                )
            ],
        )
        report = sync_mod.run(
            project_root=proj, agent="demo-agent"
        )
        self.assertTrue(report["success"])
        self.assertEqual(report["results"], [])

    def test_in_use_without_target_metadata_falls_back_to_informs(self):
        # No target_file/target_section, but informs gives us a file —
        # falls back to informs[0]. But target_section is still
        # required, so this should report invalid-target.
        proj, knowledge = _build_project(self.tmp)
        _seed_target_file(knowledge, section="remote")
        write_decisions(
            knowledge,
            [
                Decision(
                    url="https://x.test/page",
                    status="in-use",
                    decided_at="2026-05-28T00:00:00+00:00",
                    decided_by="llm",
                    informs=["topic.md"],
                    # target_section missing
                )
            ],
        )
        report = sync_mod.run(
            project_root=proj, agent="demo-agent"
        )
        # The materialized source lacks section → invalid-target
        result = next(
            r
            for r in report["results"]
            if r["name"].startswith("decision:")
        )
        self.assertEqual(result["status"], "invalid-target")
        self.assertFalse(report["success"])


class TestConflictSuppressed(_MergeFixture):
    def test_sources_yml_url_rejected_by_decision_emits_conflict(self):
        proj, knowledge = _build_project(
            self.tmp,
            sources_yml=(
                "sources:\n"
                "  - name: hand-picked\n"
                "    type: http\n"
                "    url: https://x.test/page\n"
                "    target:\n"
                "      file: knowledge/topic.md\n"
                "      section: remote\n"
            ),
        )
        _seed_target_file(knowledge, section="remote")
        write_decisions(
            knowledge,
            [
                Decision(
                    url="https://x.test/page",
                    status="rejected",
                    decided_at="2026-05-28T00:00:00+00:00",
                    decided_by="llm",
                    locked=True,
                    reason="out of scope",
                )
            ],
        )
        report = sync_mod.run(
            project_root=proj, agent="demo-agent"
        )
        self.assertFalse(report["success"])
        conflicts = [
            r
            for r in report["results"]
            if r["status"] == "conflict-suppressed"
        ]
        self.assertEqual(len(conflicts), 1)
        self.assertIn(
            "rejected (locked)", conflicts[0]["message"]
        )
        # The conflicting source was suppressed — no actual sync
        # against the rejected URL.
        non_conflict_results = [
            r
            for r in report["results"]
            if r["status"] != "conflict-suppressed"
        ]
        self.assertEqual(non_conflict_results, [])

    def test_sources_yml_url_matches_in_use_decision_no_conflict(self):
        # Same URL in both places, but decision says in-use →
        # sources.yml entry wins (explicit declaration trumps
        # materialized), no conflict.
        proj, knowledge = _build_project(
            self.tmp,
            sources_yml=(
                "sources:\n"
                "  - name: hand-picked\n"
                "    type: http\n"
                "    url: https://x.test/page\n"
                "    target:\n"
                "      file: knowledge/topic.md\n"
                "      section: remote\n"
            ),
        )
        _seed_target_file(knowledge, section="remote")
        write_decisions(
            knowledge,
            [
                Decision(
                    url="https://x.test/page",
                    status="in-use",
                    decided_at="2026-05-28T00:00:00+00:00",
                    decided_by="llm",
                    target_file="topic.md",
                    target_section="remote",
                )
            ],
        )
        # No HTTP mock → fetch fails, but that's fine for this test.
        # We're checking the absence of conflict-suppressed.
        report = sync_mod.run(
            project_root=proj, agent="demo-agent"
        )
        statuses = {r["status"] for r in report["results"]}
        self.assertNotIn("conflict-suppressed", statuses)
        # Should not double-process the URL
        url_count = sum(
            1
            for r in report["results"]
            if "x.test/page" in (r.get("name") or "")
        )
        self.assertLessEqual(url_count, 1)


class TestEmptyState(_MergeFixture):
    def test_empty_sources_and_no_decisions(self):
        proj = self.tmp / "proj"
        (proj / "agents" / "demo-agent" / "knowledge").mkdir(parents=True)
        report = sync_mod.run(
            project_root=proj, agent="demo-agent"
        )
        self.assertTrue(report["success"])
        self.assertIn("No sources declared", report["message"])

    def test_decisions_present_but_no_sources_yml(self):
        proj = self.tmp / "proj"
        knowledge = proj / "agents" / "demo-agent" / "knowledge"
        knowledge.mkdir(parents=True)
        # No sources.yml at all — sync still picks up in-use decisions
        _seed_target_file(knowledge, section="remote")
        write_decisions(
            knowledge,
            [
                Decision(
                    url="https://x.test/page",
                    status="in-use",
                    decided_at="2026-05-28T00:00:00+00:00",
                    decided_by="llm",
                    target_file="topic.md",
                    target_section="remote",
                )
            ],
        )
        # Without sources.yml, _load_sources should still succeed
        # (returns []). The decision becomes the only source.
        # No HTTP mock — fetch will fail but that's fine for this
        # test's scope.
        report = sync_mod.run(
            project_root=proj, agent="demo-agent"
        )
        # The materialized decision is the only result; status is
        # fetch-error or similar (no mock), but the IMPORTANT thing
        # is that sync didn't return "no sources" — it actually
        # processed the decision.
        self.assertTrue(
            any(
                r["name"].startswith("decision:")
                for r in report["results"]
            )
        )


if __name__ == "__main__":
    unittest.main()
