# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Tests for the discovery spider (#144 Slice 1)."""

from __future__ import annotations

import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

import responses

_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root / "scripts"))

from shared import http_source  # noqa: E402
from shared.http_source import HttpFetcher, RateLimiter  # noqa: E402
from shared.spider import (  # noqa: E402
    RootConfig,
    _extract_links_from_html,
    _parse_sitemap,
    _same_origin,
    discover,
    parse_roots,
)


def _public_getaddrinfo(host, *_a, **_kw):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.10", 0))]


class TestPureHelpers(unittest.TestCase):
    def test_same_origin_matches(self):
        self.assertTrue(
            _same_origin(
                "https://x.test/a", "https://x.test/b/c"
            )
        )

    def test_same_origin_mismatch_scheme(self):
        self.assertFalse(
            _same_origin("http://x.test/a", "https://x.test/a")
        )

    def test_same_origin_mismatch_host(self):
        self.assertFalse(
            _same_origin(
                "https://x.test/a", "https://y.test/a"
            )
        )

    def test_parse_sitemap_extracts_locs(self):
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://x.test/a</loc></url>"
            "<url><loc>https://x.test/b</loc></url>"
            "</urlset>"
        )
        urls = _parse_sitemap(body, "https://x.test/sitemap.xml")
        self.assertEqual(
            urls, ["https://x.test/a", "https://x.test/b"]
        )

    def test_parse_sitemap_handles_malformed(self):
        self.assertEqual(
            _parse_sitemap("<not xml<", "https://x.test/sm"), []
        )

    def test_extract_links_from_html(self):
        body = (
            '<html><body>'
            '<a href="/foo">F</a>'
            '<a href="https://other.test/x">O</a>'
            '<a href="#anchor">A</a>'
            '<a href="mailto:x@x.test">M</a>'
            '</body></html>'
        )
        links = _extract_links_from_html(body, "https://x.test/")
        self.assertIn("https://x.test/foo", links)
        self.assertIn("https://other.test/x", links)
        # Anchor and mailto links are filtered
        self.assertNotIn("#anchor", links)
        self.assertNotIn("mailto:x@x.test", links)


class TestParseRoots(unittest.TestCase):
    def test_none_returns_empty(self):
        self.assertEqual(parse_roots(None), [])

    def test_well_formed_entry(self):
        roots = parse_roots(
            [
                {
                    "url": "https://x.test/sitemap.xml",
                    "name": "site",
                    "max_depth": 2,
                    "max_urls": 50,
                }
            ]
        )
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].name, "site")
        self.assertEqual(roots[0].max_depth, 2)
        self.assertEqual(roots[0].max_urls, 50)
        self.assertEqual(roots[0].origin, "https://x.test")

    def test_defaults_applied(self):
        roots = parse_roots(
            [{"url": "https://x.test/", "name": "n"}]
        )
        self.assertEqual(roots[0].max_depth, 3)
        self.assertEqual(roots[0].max_urls, 200)

    def test_missing_url_raises(self):
        with self.assertRaises(ValueError):
            parse_roots([{"name": "x"}])

    def test_missing_name_raises(self):
        with self.assertRaises(ValueError):
            parse_roots([{"url": "https://x.test/"}])

    def test_negative_max_depth_raises(self):
        with self.assertRaises(ValueError):
            parse_roots(
                [
                    {
                        "url": "https://x.test/",
                        "name": "n",
                        "max_depth": -1,
                    }
                ]
            )

    def test_zero_max_urls_raises(self):
        with self.assertRaises(ValueError):
            parse_roots(
                [
                    {
                        "url": "https://x.test/",
                        "name": "n",
                        "max_urls": 0,
                    }
                ]
            )

    def test_non_list_raises(self):
        with self.assertRaises(ValueError):
            parse_roots("not a list")


class _SpiderFixture(unittest.TestCase):
    """Fixture: temp cache, public DNS stub, fetcher with stubbed
    rate limiter."""

    def setUp(self):
        import tempfile

        self.tmp = Path(tempfile.mkdtemp())
        self._cache_patch = mock.patch.object(
            http_source, "KNOWLEDGE_SYNC_CACHE_DIR", self.tmp
        )
        self._cache_patch.start()
        rl = RateLimiter(
            min_interval=0.5,
            clock=lambda: 0.0,
            sleeper=mock.Mock(),
        )
        self.fetcher = HttpFetcher(rate_limiter=rl)

    def tearDown(self):
        self._cache_patch.stop()
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)


class TestSpiderSitemap(_SpiderFixture):
    @responses.activate
    def test_sitemap_url_walked_directly(self):
        # robots.txt is missing — fetcher returns source-missing,
        # _load_robots treats that as "no rules"
        responses.get(
            "https://x.test/robots.txt", status=404
        )
        responses.get(
            "https://x.test/sitemap.xml",
            body=(
                '<?xml version="1.0"?>'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                "<url><loc>https://x.test/page1</loc></url>"
                "<url><loc>https://x.test/page2</loc></url>"
                "<url><loc>https://other.test/skip</loc></url>"
                "</urlset>"
            ),
            content_type="application/xml",
        )
        root = RootConfig(
            url="https://x.test/sitemap.xml", name="x"
        )
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            result = discover([root], fetcher=self.fetcher)
        urls = [u for u, _ in result.discovered]
        self.assertIn("https://x.test/page1", urls)
        self.assertIn("https://x.test/page2", urls)
        # Cross-origin entry dropped
        self.assertNotIn("https://other.test/skip", urls)

    @responses.activate
    def test_max_urls_truncates_and_reports(self):
        # Build a sitemap with more URLs than max_urls allows
        urls = "".join(
            f"<url><loc>https://x.test/p{i}</loc></url>"
            for i in range(10)
        )
        responses.get("https://x.test/robots.txt", status=404)
        responses.get(
            "https://x.test/sitemap.xml",
            body=(
                '<?xml version="1.0"?>'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                f"{urls}</urlset>"
            ),
            content_type="application/xml",
        )
        root = RootConfig(
            url="https://x.test/sitemap.xml",
            name="x",
            max_urls=3,
        )
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            result = discover([root], fetcher=self.fetcher)
        self.assertEqual(len(result.discovered), 3)
        self.assertTrue(
            any("truncated" in e for e in result.errors)
        )

    @responses.activate
    def test_implicit_sitemap_xml_tried(self):
        # Root is a regular URL — spider should try /sitemap.xml
        responses.get("https://x.test/robots.txt", status=404)
        responses.get(
            "https://x.test/sitemap.xml",
            body=(
                '<?xml version="1.0"?>'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                "<url><loc>https://x.test/p</loc></url>"
                "</urlset>"
            ),
            content_type="application/xml",
        )
        root = RootConfig(url="https://x.test/", name="x")
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            result = discover([root], fetcher=self.fetcher)
        self.assertEqual(
            [u for u, _ in result.discovered],
            ["https://x.test/p"],
        )


class TestSpiderHTMLCrawl(_SpiderFixture):
    @responses.activate
    def test_recursive_crawl_when_no_sitemap(self):
        # No sitemap available; robots permits everything
        responses.get("https://x.test/robots.txt", status=404)
        responses.get(
            "https://x.test/sitemap.xml", status=404
        )
        responses.get(
            "https://x.test/",
            body=(
                '<html><body>'
                '<a href="/a">A</a>'
                '<a href="/b">B</a>'
                '<a href="https://other.test/c">C</a>'
                '</body></html>'
            ),
            content_type="text/html",
        )
        responses.get(
            "https://x.test/a",
            body="<html><body>leaf a</body></html>",
            content_type="text/html",
        )
        responses.get(
            "https://x.test/b",
            body="<html><body>leaf b</body></html>",
            content_type="text/html",
        )
        root = RootConfig(
            url="https://x.test/",
            name="x",
            max_depth=2,
            max_urls=50,
        )
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            result = discover([root], fetcher=self.fetcher)
        urls = [u for u, _ in result.discovered]
        self.assertIn("https://x.test/", urls)
        self.assertIn("https://x.test/a", urls)
        self.assertIn("https://x.test/b", urls)
        self.assertNotIn("https://other.test/c", urls)


class TestSpiderRobots(_SpiderFixture):
    @responses.activate
    def test_robots_disallow_blocks_url(self):
        responses.get(
            "https://x.test/robots.txt",
            body="User-agent: *\nDisallow: /private/",
            content_type="text/plain",
        )
        responses.get(
            "https://x.test/sitemap.xml",
            body=(
                '<?xml version="1.0"?>'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                "<url><loc>https://x.test/ok</loc></url>"
                "<url><loc>https://x.test/private/secret</loc></url>"
                "</urlset>"
            ),
            content_type="application/xml",
        )
        root = RootConfig(
            url="https://x.test/sitemap.xml", name="x"
        )
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            result = discover([root], fetcher=self.fetcher)
        urls = [u for u, _ in result.discovered]
        self.assertIn("https://x.test/ok", urls)
        self.assertNotIn("https://x.test/private/secret", urls)


class TestSpiderConcurrency(_SpiderFixture):
    @responses.activate
    def test_multiple_roots_merge(self):
        for host in ("x.test", "y.test"):
            responses.get(
                f"https://{host}/robots.txt", status=404
            )
            responses.get(
                f"https://{host}/sitemap.xml",
                body=(
                    '<?xml version="1.0"?>'
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                    f"<url><loc>https://{host}/page</loc></url>"
                    "</urlset>"
                ),
                content_type="application/xml",
            )
        roots = [
            RootConfig(url="https://x.test/sitemap.xml", name="X"),
            RootConfig(url="https://y.test/sitemap.xml", name="Y"),
        ]
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            result = discover(
                roots, fetcher=self.fetcher, concurrency=2
            )
        urls = [u for u, _ in result.discovered]
        self.assertIn("https://x.test/page", urls)
        self.assertIn("https://y.test/page", urls)

    def test_empty_roots_returns_empty_result(self):
        result = discover([])
        self.assertEqual(result.discovered, [])
        self.assertEqual(result.errors, [])


class TestSpiderSafety(_SpiderFixture):
    def test_private_ip_root_refused(self):
        def _private(*_a, **_kw):
            return [
                (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    6,
                    "",
                    ("127.0.0.1", 0),
                )
            ]

        root = RootConfig(
            url="https://internal.test/sitemap.xml", name="bad"
        )
        with mock.patch.object(socket, "getaddrinfo", _private):
            result = discover([root], fetcher=self.fetcher)
        self.assertEqual(result.discovered, [])
        self.assertTrue(
            any("blocked address" in e for e in result.errors)
        )


if __name__ == "__main__":
    unittest.main()
