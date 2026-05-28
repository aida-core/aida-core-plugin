# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Tests for audit / promote / regenerate-md (#144 Slice 2)."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root / "scripts"))
sys.path.insert(
    0,
    str(_project_root / "skills" / "knowledge-sync" / "scripts"),
)

from shared.decisions_log import (  # noqa: E402
    DECISIONS_MD_FILENAME,
    Decision,
    read_decisions,
    write_decisions,
)

import audit as audit_mod  # noqa: E402
import promote as promote_mod  # noqa: E402
import regenerate_md as regen_mod  # noqa: E402


def _build_agent(tmp: Path, agent: str = "demo-agent") -> Path:
    knowledge = tmp / "proj" / "agents" / agent / "knowledge"
    knowledge.mkdir(parents=True)
    return knowledge


def _days_ago(days: float) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(days=days)
    ).isoformat(timespec="seconds")


class _Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


# ----------------------------------------------------------------------
# audit
# ----------------------------------------------------------------------


class TestAuditRunner(_Fixture):
    def test_counts_by_status(self):
        knowledge = _build_agent(self.tmp)
        write_decisions(
            knowledge,
            [
                Decision(url="https://x.test/in1", status="in-use"),
                Decision(url="https://x.test/in2", status="in-use"),
                Decision(url="https://x.test/rej", status="rejected", locked=True),
                Decision(url="https://x.test/pen", status="pending"),
            ],
        )
        report = audit_mod.run(
            project_root=self.tmp / "proj", agent="demo-agent"
        )
        self.assertTrue(report["success"])
        self.assertEqual(report["totals"]["in_use"], 2)
        self.assertEqual(report["totals"]["rejected"], 1)
        self.assertEqual(report["totals"]["rejected_locked"], 1)
        self.assertEqual(report["totals"]["pending"], 1)
        self.assertEqual(report["totals"]["all"], 4)

    def test_lists_pending_urls(self):
        knowledge = _build_agent(self.tmp)
        write_decisions(
            knowledge,
            [
                Decision(url="https://x.test/a", status="pending"),
                Decision(url="https://x.test/b", status="pending"),
                Decision(url="https://x.test/c", status="in-use"),
            ],
        )
        report = audit_mod.run(
            project_root=self.tmp / "proj", agent="demo-agent"
        )
        self.assertEqual(
            sorted(report["pending_urls"]),
            ["https://x.test/a", "https://x.test/b"],
        )

    def test_stale_llm_decisions_flagged(self):
        knowledge = _build_agent(self.tmp)
        write_decisions(
            knowledge,
            [
                Decision(
                    url="https://x.test/old",
                    status="in-use",
                    decided_at=_days_ago(120),
                    decided_by="llm",
                ),
                Decision(
                    url="https://x.test/recent",
                    status="in-use",
                    decided_at=_days_ago(10),
                    decided_by="llm",
                ),
                Decision(
                    url="https://x.test/locked-old",
                    status="rejected",
                    decided_at=_days_ago(200),
                    decided_by="llm",
                    locked=True,
                ),
            ],
        )
        report = audit_mod.run(
            project_root=self.tmp / "proj",
            agent="demo-agent",
            stale_after_days=90,
        )
        stale_urls = {
            entry["url"] for entry in report["stale_llm_decisions"]
        }
        # Old LLM decision is stale; recent isn't; locked is exempt
        self.assertIn("https://x.test/old", stale_urls)
        self.assertNotIn("https://x.test/recent", stale_urls)
        self.assertNotIn("https://x.test/locked-old", stale_urls)

    def test_never_synced_flagged(self):
        knowledge = _build_agent(self.tmp)
        write_decisions(
            knowledge,
            [
                Decision(
                    url="https://x.test/never",
                    status="in-use",
                ),
                Decision(
                    url="https://x.test/done",
                    status="in-use",
                    last_synced=_days_ago(1),
                ),
            ],
        )
        report = audit_mod.run(
            project_root=self.tmp / "proj", agent="demo-agent"
        )
        self.assertEqual(
            report["never_synced"], ["https://x.test/never"]
        )

    def test_missing_target_flagged(self):
        knowledge = _build_agent(self.tmp)
        write_decisions(
            knowledge,
            [
                Decision(
                    url="https://x.test/bad",
                    status="in-use",
                    # No target_file or informs, no target_section
                ),
                Decision(
                    url="https://x.test/ok",
                    status="in-use",
                    target_file="skills.md",
                    target_section="upstream",
                ),
            ],
        )
        report = audit_mod.run(
            project_root=self.tmp / "proj", agent="demo-agent"
        )
        self.assertIn(
            "https://x.test/bad", report["missing_target"]
        )
        self.assertNotIn(
            "https://x.test/ok", report["missing_target"]
        )

    def test_empty_state(self):
        _build_agent(self.tmp)
        report = audit_mod.run(
            project_root=self.tmp / "proj", agent="demo-agent"
        )
        self.assertTrue(report["success"])
        self.assertEqual(report["totals"]["all"], 0)


# ----------------------------------------------------------------------
# promote
# ----------------------------------------------------------------------


class TestPromoteRunner(_Fixture):
    def test_promote_new_url(self):
        _build_agent(self.tmp)
        report = promote_mod.run(
            project_root=self.tmp / "proj",
            agent="demo-agent",
            url="https://x.test/page",
            target_file="skills.md",
            target_section="upstream",
            reason="needed by skills.md upstream block",
        )
        self.assertTrue(report["success"])
        self.assertIsNone(report["previous_status"])
        self.assertEqual(report["new_status"], "in-use")
        decisions = read_decisions(
            self.tmp / "proj" / "agents" / "demo-agent" / "knowledge"
        )
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].status, "in-use")
        self.assertEqual(decisions[0].decided_by, "human")
        self.assertEqual(decisions[0].target_file, "skills.md")
        self.assertEqual(decisions[0].target_section, "upstream")

    def test_promote_pending_url(self):
        knowledge = _build_agent(self.tmp)
        write_decisions(
            knowledge,
            [
                Decision(
                    url="https://x.test/page",
                    status="pending",
                    discovered_at="2026-05-28T00:00:00+00:00",
                    source_root="agentskills",
                ),
            ],
        )
        report = promote_mod.run(
            project_root=self.tmp / "proj",
            agent="demo-agent",
            url="https://x.test/page",
            target_file="skills.md",
            target_section="upstream",
        )
        self.assertTrue(report["success"])
        self.assertEqual(report["previous_status"], "pending")
        decisions = read_decisions(knowledge)
        self.assertEqual(decisions[0].status, "in-use")
        # Discovery metadata preserved
        self.assertEqual(
            decisions[0].discovered_at,
            "2026-05-28T00:00:00+00:00",
        )
        self.assertEqual(decisions[0].source_root, "agentskills")

    def test_promote_locked_refused(self):
        knowledge = _build_agent(self.tmp)
        write_decisions(
            knowledge,
            [
                Decision(
                    url="https://x.test/page",
                    status="rejected",
                    locked=True,
                    decided_at="2026-05-28T00:00:00+00:00",
                    decided_by="human",
                ),
            ],
        )
        report = promote_mod.run(
            project_root=self.tmp / "proj",
            agent="demo-agent",
            url="https://x.test/page",
            target_file="skills.md",
            target_section="upstream",
        )
        self.assertFalse(report["success"])
        self.assertIn("locked", report["message"])
        # Decision unchanged
        decisions = read_decisions(knowledge)
        self.assertEqual(decisions[0].status, "rejected")

    def test_promote_unlocked_rejected_flips_to_in_use(self):
        knowledge = _build_agent(self.tmp)
        write_decisions(
            knowledge,
            [
                Decision(
                    url="https://x.test/page",
                    status="rejected",
                    locked=False,
                    decided_at="2026-05-28T00:00:00+00:00",
                    decided_by="llm",
                ),
            ],
        )
        report = promote_mod.run(
            project_root=self.tmp / "proj",
            agent="demo-agent",
            url="https://x.test/page",
            target_file="skills.md",
            target_section="upstream",
        )
        self.assertTrue(report["success"])
        self.assertEqual(report["previous_status"], "rejected")
        decisions = read_decisions(knowledge)
        self.assertEqual(decisions[0].status, "in-use")
        self.assertEqual(decisions[0].decided_by, "human")


# ----------------------------------------------------------------------
# regenerate-md
# ----------------------------------------------------------------------


class TestRegenerateMd(_Fixture):
    def test_rebuilds_md_from_json(self):
        knowledge = _build_agent(self.tmp)
        write_decisions(
            knowledge,
            [
                Decision(
                    url="https://x.test/page",
                    status="in-use",
                    decided_at="2026-05-28T00:00:00+00:00",
                    decided_by="llm",
                    reason="useful",
                ),
            ],
        )
        # Corrupt the markdown by hand
        md_path = knowledge / DECISIONS_MD_FILENAME
        md_path.write_text("# Garbage\n", encoding="utf-8")

        report = regen_mod.run(
            project_root=self.tmp / "proj", agent="demo-agent"
        )
        self.assertTrue(report["success"])
        self.assertEqual(report["decisions_count"], 1)
        rebuilt = md_path.read_text(encoding="utf-8")
        self.assertTrue(rebuilt.startswith("<!-- GENERATED"))
        self.assertIn("https://x.test/page", rebuilt)
        # Garbage gone
        self.assertNotIn("# Garbage", rebuilt)

    def test_no_decisions_still_rewrites_md(self):
        _build_agent(self.tmp)
        report = regen_mod.run(
            project_root=self.tmp / "proj", agent="demo-agent"
        )
        self.assertTrue(report["success"])
        self.assertEqual(report["decisions_count"], 0)


if __name__ == "__main__":
    unittest.main()
