# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""End-to-end tests for the knowledge-discover runner (#144 Slice 1)."""

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
    read_decisions,
    write_decisions,
)

import discover as discover_mod  # noqa: E402


def _public_getaddrinfo(host, *_a, **_kw):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.10", 0))]


def _build_project(
    tmp: Path,
    *,
    agent: str = "demo-agent",
    sources_yml: str = "",
):
    proj = tmp / "proj"
    knowledge = proj / "agents" / agent / "knowledge"
    knowledge.mkdir(parents=True)
    (knowledge / "sources.yml").write_text(
        sources_yml, encoding="utf-8"
    )
    return proj


class _DiscoverFixture(unittest.TestCase):
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


class TestDiscoverRunner(_DiscoverFixture):
    @responses.activate
    def test_writes_pending_decisions(self):
        responses.get(
            "https://x.test/robots.txt", status=404
        )
        responses.get(
            "https://x.test/sitemap.xml",
            body=(
                '<?xml version="1.0"?>'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                "<url><loc>https://x.test/a</loc></url>"
                "<url><loc>https://x.test/b</loc></url>"
                "</urlset>"
            ),
            content_type="application/xml",
        )
        proj = _build_project(
            self.tmp,
            sources_yml=(
                "roots:\n"
                "  - url: https://x.test/sitemap.xml\n"
                "    name: x\n"
            ),
        )
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            report = discover_mod.run(
                project_root=proj, agent="demo-agent"
            )
        self.assertTrue(report["success"])
        self.assertEqual(report["discovered"], 2)
        decisions = read_decisions(
            proj / "agents" / "demo-agent" / "knowledge"
        )
        urls = sorted(d.url for d in decisions)
        self.assertEqual(
            urls, ["https://x.test/a", "https://x.test/b"]
        )
        self.assertTrue(all(d.status == "pending" for d in decisions))

    @responses.activate
    def test_skips_already_decided_urls(self):
        responses.get(
            "https://x.test/robots.txt", status=404
        )
        responses.get(
            "https://x.test/sitemap.xml",
            body=(
                '<?xml version="1.0"?>'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                "<url><loc>https://x.test/a</loc></url>"
                "<url><loc>https://x.test/b</loc></url>"
                "</urlset>"
            ),
            content_type="application/xml",
        )
        proj = _build_project(
            self.tmp,
            sources_yml=(
                "roots:\n"
                "  - url: https://x.test/sitemap.xml\n"
                "    name: x\n"
            ),
        )
        knowledge_dir = (
            proj / "agents" / "demo-agent" / "knowledge"
        )
        # Pre-existing: /a is already decided in-use
        write_decisions(
            knowledge_dir,
            [
                Decision(
                    url="https://x.test/a",
                    status="in-use",
                    decided_at="2026-05-28T00:00:00+00:00",
                    decided_by="human",
                    reason="approved",
                )
            ],
        )
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            report = discover_mod.run(
                project_root=proj, agent="demo-agent"
            )
        self.assertTrue(report["success"])
        self.assertEqual(report["discovered"], 1)
        self.assertEqual(report["skipped_existing"], 1)
        decisions = read_decisions(knowledge_dir)
        # /a is preserved as in-use; /b is added as pending
        by_url = {d.url: d for d in decisions}
        self.assertEqual(by_url["https://x.test/a"].status, "in-use")
        self.assertEqual(by_url["https://x.test/a"].reason, "approved")
        self.assertEqual(by_url["https://x.test/b"].status, "pending")

    def test_no_roots_returns_clean_no_op(self):
        proj = _build_project(
            self.tmp, sources_yml="sources: []\n"
        )
        report = discover_mod.run(
            project_root=proj, agent="demo-agent"
        )
        self.assertTrue(report["success"])
        self.assertEqual(report["discovered"], 0)
        self.assertIn("No `roots:` declared", report["message"])
        # No decisions file written
        self.assertFalse(
            (
                proj
                / "agents"
                / "demo-agent"
                / "knowledge"
                / "decisions.json"
            ).exists()
        )

    def test_missing_sources_yml_returns_no_op(self):
        proj = self.tmp / "proj"
        (proj / "agents" / "x" / "knowledge").mkdir(parents=True)
        report = discover_mod.run(
            project_root=proj, agent="x"
        )
        self.assertTrue(report["success"])
        self.assertEqual(report["discovered"], 0)

    def test_malformed_roots_returns_error(self):
        proj = _build_project(
            self.tmp,
            sources_yml=(
                "roots:\n"
                "  - url: https://x.test/\n"
                # Missing name
            ),
        )
        report = discover_mod.run(
            project_root=proj, agent="demo-agent"
        )
        self.assertFalse(report["success"])
        self.assertIn("name", report["message"])

    @responses.activate
    def test_dedupe_across_repeated_runs(self):
        responses.get("https://x.test/robots.txt", status=404)
        responses.get(
            "https://x.test/sitemap.xml",
            body=(
                '<?xml version="1.0"?>'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                "<url><loc>https://x.test/a</loc></url>"
                "</urlset>"
            ),
            content_type="application/xml",
        )
        proj = _build_project(
            self.tmp,
            sources_yml=(
                "roots:\n"
                "  - url: https://x.test/sitemap.xml\n"
                "    name: x\n"
            ),
        )
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            first = discover_mod.run(
                project_root=proj, agent="demo-agent"
            )
            second = discover_mod.run(
                project_root=proj, agent="demo-agent"
            )
        self.assertEqual(first["discovered"], 1)
        self.assertEqual(second["discovered"], 0)
        self.assertEqual(second["skipped_existing"], 1)


if __name__ == "__main__":
    unittest.main()
