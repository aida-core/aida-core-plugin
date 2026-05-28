# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Tests for the knowledge-sync HTTP fetcher (#143)."""

from __future__ import annotations

import json
import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

import responses

_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root / "scripts"))

# Import after path setup so the shared package resolves.
from shared import http_source  # noqa: E402
from shared.http_source import (  # noqa: E402
    FetchOutcome,
    HttpFetcher,
    RateLimiter,
    extract_content,
)


# Stub DNS to always say "this IP is fine" so the SSRF guard doesn't
# block us during normal success-path tests. Specific SSRF tests
# patch this with private IPs.
def _public_getaddrinfo(host, *_a, **_kw):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.10", 0))]


def _private_getaddrinfo(host, *_a, **_kw):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]


def _link_local_getaddrinfo(host, *_a, **_kw):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 0))]


class TestExtractContent(unittest.TestCase):
    def test_text_markdown_passthrough(self):
        self.assertEqual(
            extract_content("# Hi", "text/markdown"), "# Hi"
        )

    def test_text_plain_passthrough(self):
        self.assertEqual(
            extract_content("plain text", "text/plain"), "plain text"
        )

    def test_html_no_selector_converts_to_markdown(self):
        html = "<h1>Title</h1><p>Body</p>"
        result = extract_content(html, "text/html")
        self.assertIn("Title", result)
        self.assertIn("Body", result)

    def test_html_with_selector_extracts_subtree(self):
        html = (
            "<html><body>"
            "<nav>Nav stuff</nav>"
            "<main><h1>Wanted</h1></main>"
            "</body></html>"
        )
        result = extract_content(html, "text/html", selector="main")
        self.assertIn("Wanted", result)
        self.assertNotIn("Nav stuff", result)

    def test_html_selector_no_match_falls_back_to_full(self):
        html = "<p>Hello</p>"
        result = extract_content(html, "text/html", selector=".missing")
        self.assertIn("Hello", result)

    def test_unsupported_content_type_returns_none(self):
        self.assertIsNone(
            extract_content("blob", "application/octet-stream")
        )

    def test_content_type_with_charset(self):
        self.assertEqual(
            extract_content(
                "raw", "text/markdown; charset=utf-8"
            ),
            "raw",
        )


class TestRateLimiter(unittest.TestCase):
    def test_first_call_does_not_wait(self):
        clock = mock.Mock(return_value=100.0)
        sleeper = mock.Mock()
        rl = RateLimiter(min_interval=0.5, clock=clock, sleeper=sleeper)
        rl.wait("example.com")
        sleeper.assert_not_called()

    def test_second_call_to_same_host_waits(self):
        times = iter([100.0, 100.2, 100.5])
        clock = mock.Mock(side_effect=lambda: next(times))
        sleeper = mock.Mock()
        rl = RateLimiter(min_interval=0.5, clock=clock, sleeper=sleeper)
        rl.wait("example.com")
        rl.wait("example.com")
        sleeper.assert_called_once()
        # Sleep for the remaining interval: 0.5 - (100.2 - 100.0) = 0.3
        self.assertAlmostEqual(sleeper.call_args[0][0], 0.3, places=5)

    def test_different_hosts_do_not_wait(self):
        clock = mock.Mock(side_effect=[100.0, 100.1])
        sleeper = mock.Mock()
        rl = RateLimiter(min_interval=0.5, clock=clock, sleeper=sleeper)
        rl.wait("a.example.com")
        rl.wait("b.example.com")
        sleeper.assert_not_called()


class _FetcherFixture(unittest.TestCase):
    """Shared setup: a temp cache dir + an HttpFetcher with stubbed
    rate limiting (so tests don't sleep)."""

    def setUp(self):
        import tempfile

        self._tmp = Path(tempfile.mkdtemp())
        # Redirect the cache dir to the temp location for the duration
        self._cache_patch = mock.patch.object(
            http_source, "KNOWLEDGE_SYNC_CACHE_DIR", self._tmp
        )
        self._cache_patch.start()
        # Stub the rate limiter so wait() never sleeps
        self.rl = RateLimiter(
            min_interval=0.5,
            clock=lambda: 0.0,
            sleeper=mock.Mock(),
        )
        self.fetcher = HttpFetcher(rate_limiter=self.rl)

    def tearDown(self):
        self._cache_patch.stop()
        import shutil

        shutil.rmtree(self._tmp, ignore_errors=True)


class TestHttpFetcherSuccess(_FetcherFixture):
    @responses.activate
    def test_200_html_converts_and_caches(self):
        responses.get(
            "https://docs.example.com/page",
            body="<h1>Hello</h1>",
            content_type="text/html",
            headers={"ETag": 'W/"abc"'},
        )
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            outcome = self.fetcher.fetch("https://docs.example.com/page")
        self.assertEqual(outcome.kind, "content")
        self.assertIn("Hello", outcome.content)
        self.assertFalse(outcome.from_cache)
        # Cache entry written
        cache_files = list(self._tmp.glob("*.json"))
        self.assertEqual(len(cache_files), 1)
        entry = json.loads(cache_files[0].read_text())
        self.assertEqual(entry["etag"], 'W/"abc"')

    @responses.activate
    def test_200_markdown_passthrough(self):
        responses.get(
            "https://docs.example.com/raw",
            body="# Title\n\nBody",
            content_type="text/markdown",
        )
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            outcome = self.fetcher.fetch("https://docs.example.com/raw")
        self.assertEqual(outcome.kind, "content")
        self.assertEqual(outcome.content, "# Title\n\nBody")

    @responses.activate
    def test_cache_hit_within_ttl_skips_network(self):
        responses.get(
            "https://docs.example.com/cached",
            body="<p>One</p>",
            content_type="text/html",
        )
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            first = self.fetcher.fetch("https://docs.example.com/cached")
            second = self.fetcher.fetch("https://docs.example.com/cached")
        self.assertEqual(first.kind, "content")
        self.assertFalse(first.from_cache)
        self.assertEqual(second.kind, "content")
        self.assertTrue(second.from_cache)
        # Only the first call hit the network
        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    def test_cache_ttl_zero_always_fetches(self):
        responses.get(
            "https://docs.example.com/no-cache",
            body="<p>One</p>",
            content_type="text/html",
        )
        responses.get(
            "https://docs.example.com/no-cache",
            body="<p>Two</p>",
            content_type="text/html",
        )
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            first = self.fetcher.fetch(
                "https://docs.example.com/no-cache", cache_ttl=0
            )
            second = self.fetcher.fetch(
                "https://docs.example.com/no-cache", cache_ttl=0
            )
        self.assertFalse(first.from_cache)
        self.assertFalse(second.from_cache)
        self.assertEqual(len(responses.calls), 2)

    @responses.activate
    def test_304_refreshes_cache_and_reuses_body(self):
        # First call: 200 with ETag
        responses.get(
            "https://docs.example.com/cond",
            body="<p>v1</p>",
            content_type="text/html",
            headers={"ETag": 'W/"v1"'},
        )
        # Second call: 304 — server says nothing changed
        responses.get(
            "https://docs.example.com/cond",
            status=304,
        )
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            first = self.fetcher.fetch(
                "https://docs.example.com/cond", cache_ttl=0
            )
            second = self.fetcher.fetch(
                "https://docs.example.com/cond", cache_ttl=0
            )
        self.assertEqual(first.kind, "content")
        self.assertEqual(second.kind, "content")
        self.assertIn("v1", second.content)
        self.assertFalse(second.from_cache)  # 304 is not a cache-fast-path
        # Both calls hit the network; second sent If-None-Match
        self.assertEqual(len(responses.calls), 2)
        self.assertEqual(
            responses.calls[1].request.headers.get("If-None-Match"),
            'W/"v1"',
        )

    @responses.activate
    def test_redirect_chain_followed(self):
        responses.get(
            "https://docs.example.com/old",
            status=301,
            headers={"Location": "https://docs.example.com/new"},
        )
        responses.get(
            "https://docs.example.com/new",
            body="<p>moved</p>",
            content_type="text/html",
        )
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            outcome = self.fetcher.fetch("https://docs.example.com/old")
        self.assertEqual(outcome.kind, "content")
        self.assertIn("moved", outcome.content)


class TestHttpFetcherFailures(_FetcherFixture):
    @responses.activate
    def test_404_is_source_missing(self):
        responses.get("https://docs.example.com/gone", status=404)
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            outcome = self.fetcher.fetch("https://docs.example.com/gone")
        self.assertEqual(outcome.kind, "source-missing")
        self.assertIn("404", outcome.message)

    @responses.activate
    def test_503_is_fetch_error(self):
        responses.get("https://docs.example.com/down", status=503)
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            outcome = self.fetcher.fetch("https://docs.example.com/down")
        self.assertEqual(outcome.kind, "fetch-error")
        self.assertIn("503", outcome.message)

    def test_dns_failure_is_fetch_error(self):
        def _gaierror(*_a, **_kw):
            raise socket.gaierror("nope")

        with mock.patch.object(socket, "getaddrinfo", _gaierror):
            outcome = self.fetcher.fetch(
                "https://nx.example.com/anything"
            )
        # Failed name resolution → _is_url_safe returns False →
        # fetch-error (we couldn't confirm the IP was safe).
        self.assertEqual(outcome.kind, "fetch-error")

    @responses.activate
    def test_timeout_is_fetch_error(self):
        import requests as _r

        responses.get(
            "https://docs.example.com/slow",
            body=_r.Timeout("read timed out"),
        )
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            outcome = self.fetcher.fetch(
                "https://docs.example.com/slow"
            )
        self.assertEqual(outcome.kind, "fetch-error")

    @responses.activate
    def test_unsupported_content_type_is_fetch_error(self):
        responses.get(
            "https://docs.example.com/binary",
            body=b"\x00\x01\x02",
            content_type="application/octet-stream",
        )
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            outcome = self.fetcher.fetch(
                "https://docs.example.com/binary"
            )
        self.assertEqual(outcome.kind, "fetch-error")
        self.assertIn("Content-Type", outcome.message)


class TestHttpFetcherSecurity(_FetcherFixture):
    def test_direct_private_ip_blocked(self):
        with mock.patch.object(
            socket, "getaddrinfo", _private_getaddrinfo
        ):
            outcome = self.fetcher.fetch(
                "https://internal.example.com/foo"
            )
        self.assertEqual(outcome.kind, "fetch-error")
        self.assertIn("blocked address", outcome.message)

    def test_aws_metadata_address_blocked(self):
        with mock.patch.object(
            socket, "getaddrinfo", _link_local_getaddrinfo
        ):
            outcome = self.fetcher.fetch(
                "http://169.254.169.254/latest/meta-data/"
            )
        self.assertEqual(outcome.kind, "fetch-error")

    @responses.activate
    def test_redirect_to_private_blocked(self):
        # Public → redirect → private. SSRF guard must re-check the
        # redirect target before connecting.
        responses.get(
            "https://docs.example.com/redirect",
            status=302,
            headers={"Location": "https://internal.example.com/secret"},
        )
        responses.get(
            "https://internal.example.com/secret",
            body="secret content",
            content_type="text/html",
        )

        # First hop resolves public; redirect target resolves private.
        host_to_ip = {
            "docs.example.com": "203.0.113.10",
            "internal.example.com": "127.0.0.1",
        }

        def fake_getaddrinfo(host, *_a, **_kw):
            ip = host_to_ip.get(host, "203.0.113.10")
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

        with mock.patch.object(socket, "getaddrinfo", fake_getaddrinfo):
            outcome = self.fetcher.fetch(
                "https://docs.example.com/redirect"
            )
        self.assertEqual(outcome.kind, "fetch-error")
        self.assertIn("blocked address", outcome.message)

    @responses.activate
    def test_redirect_chain_exceeds_cap(self):
        # 6 hops: original + 5 redirects that all redirect again
        for i in range(7):
            responses.get(
                f"https://docs.example.com/r{i}",
                status=302,
                headers={"Location": f"https://docs.example.com/r{i + 1}"},
            )
        # A short-circuit fetcher with MAX_REDIRECTS=5
        fetcher = HttpFetcher(rate_limiter=self.rl, max_redirects=5)
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            outcome = fetcher.fetch("https://docs.example.com/r0")
        self.assertEqual(outcome.kind, "fetch-error")
        self.assertIn("Redirect chain exceeded", outcome.message)

    @responses.activate
    def test_response_too_large_via_content_length(self):
        responses.get(
            "https://docs.example.com/big",
            body="<p>x</p>",
            content_type="text/html",
            headers={"Content-Length": str(10 * 1024 * 1024)},
        )
        fetcher = HttpFetcher(rate_limiter=self.rl, max_bytes=1024)
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            outcome = fetcher.fetch("https://docs.example.com/big")
        self.assertEqual(outcome.kind, "too-large")

    @responses.activate
    def test_response_too_large_streamed(self):
        # Server lies / doesn't send Content-Length; we still abort
        # mid-stream when the byte count exceeds the cap.
        big_body = "<p>" + ("x" * 5000) + "</p>"
        responses.get(
            "https://docs.example.com/sneaky",
            body=big_body,
            content_type="text/html",
        )
        fetcher = HttpFetcher(rate_limiter=self.rl, max_bytes=1024)
        with mock.patch.object(socket, "getaddrinfo", _public_getaddrinfo):
            outcome = fetcher.fetch("https://docs.example.com/sneaky")
        self.assertEqual(outcome.kind, "too-large")


class TestFetchOutcome(unittest.TestCase):
    def test_frozen_dataclass(self):
        outcome = FetchOutcome(kind="content", content="x")
        with self.assertRaises(Exception):
            outcome.kind = "fetch-error"  # type: ignore[misc]

    def test_defaults(self):
        outcome = FetchOutcome(kind="fetch-error")
        self.assertIsNone(outcome.content)
        self.assertIsNone(outcome.message)
        self.assertFalse(outcome.from_cache)


if __name__ == "__main__":
    unittest.main()
