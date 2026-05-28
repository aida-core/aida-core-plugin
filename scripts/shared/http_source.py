# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""HTTP source fetcher for knowledge-sync (#143).

The mechanic layer of knowledge-sync's remote source support. Given a
URL declared in an agent's ``sources.yml``, returns the content suitable
for placing inside a marker-delimited section of a knowledge file.

Out of scope (tracked elsewhere): URL spidering / discovery,
LLM-driven curation, authentication, JavaScript-rendered pages. This
module is the policy-free mechanic. See #144 for the policy layer.

The public surface is :class:`HttpFetcher`. It returns a
:class:`FetchOutcome` that carries either successful content or one of
three failure kinds — ``source-missing`` (definitive: HTTP 4xx),
``fetch-error`` (transient or configuration: 5xx / DNS / timeout / SSRF
block / unsupported content-type), or ``too-large`` (response exceeded
size limit).

Security:
  * Pre-flight DNS resolution rejects URLs that resolve to private,
    loopback, link-local, reserved, or other non-public addresses
    (RFC1918, AWS metadata at 169.254.169.254, IPv6 ULA / link-local).
  * Auto-redirects are disabled; each redirect target is re-checked
    before connect. Redirect chain is capped.
  * Response size is capped (Content-Length pre-check + streamed
    enforcement).

Caching:
  * Responses are cached at
    ``~/.aida/cache/knowledge-sync/<sha256-of-url>.json``.
  * Within ``cache_ttl`` the cached body is returned without any
    network call.
  * On expiry, ETag / Last-Modified are sent as conditional headers; a
    304 refreshes the cache timestamp and reuses the body.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Literal, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

from .paths import KNOWLEDGE_SYNC_CACHE_DIR

# ---------------------------------------------------------------------------
# Constants & types
# ---------------------------------------------------------------------------

DEFAULT_CACHE_TTL = 86_400  # 24h
DEFAULT_TIMEOUT = 30  # seconds
MAX_REDIRECTS = 5
MAX_BYTES = 2 * 1024 * 1024  # 2 MiB
RATE_LIMIT_SECONDS = 0.5  # ≥0.5s between calls to same host

# IP ranges blocked at every resolution + redirect hop. Anything that
# satisfies ``ipaddress.ip_address(ip).is_reserved`` is rejected too,
# which covers oddities like the v4 multicast and broadcast spaces.
_BLOCKED_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),       # loopback
    ipaddress.ip_network("10.0.0.0/8"),        # RFC1918
    ipaddress.ip_network("172.16.0.0/12"),     # RFC1918
    ipaddress.ip_network("192.168.0.0/16"),    # RFC1918
    ipaddress.ip_network("169.254.0.0/16"),    # link-local (AWS metadata)
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
)

FetchKind = Literal["content", "source-missing", "fetch-error", "too-large"]


@dataclass(frozen=True)
class FetchOutcome:
    """Unified outcome shape for any knowledge-sync source dispatch.

    Both local-file and HTTP sources return this so ``sync.py`` can map
    consistently to per-source status in its JSON report.

    ``from_cache`` is True if the HTTP outcome was served entirely from
    the local cache without a network round-trip. False for local
    sources, network fetches, and conditional 304 refreshes.
    """

    kind: FetchKind
    content: Optional[str] = None
    message: Optional[str] = None
    from_cache: bool = False


# ---------------------------------------------------------------------------
# Per-host rate limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """In-process, per-host sliding-window rate limiter.

    Enforces a minimum gap between calls to the same hostname. Waits
    are silent — they don't surface as errors; the caller just spends a
    little wall-clock time on the second call.

    Single-process scope is intentional. We're not protecting upstream
    services from a cluster; we're being polite when a knowledge sync
    fetches several pages from the same docs site in one run.
    """

    def __init__(
        self,
        min_interval: float = RATE_LIMIT_SECONDS,
        clock: Optional[callable] = None,
        sleeper: Optional[callable] = None,
    ) -> None:
        self._min_interval = min_interval
        self._last_call: Dict[str, float] = {}
        self._clock = clock or time.monotonic
        self._sleep = sleeper or time.sleep

    def wait(self, host: str) -> None:
        """Block until at least ``min_interval`` has passed since the
        last call to ``host``. Records the call time on return.
        """
        now = self._clock()
        last = self._last_call.get(host)
        if last is not None:
            elapsed = now - last
            if elapsed < self._min_interval:
                self._sleep(self._min_interval - elapsed)
                now = self._clock()
        self._last_call[host] = now


# ---------------------------------------------------------------------------
# SSRF guard
# ---------------------------------------------------------------------------


def _is_url_safe(url: str) -> bool:
    """Resolve ``url``'s host and return False if any resolved IP is in
    a blocked range.

    NB: a small TOCTOU window exists between this DNS lookup and the
    subsequent TCP connect. Mitigation: the same check runs at every
    redirect hop, and the blocklists cover the high-value targets
    (cloud metadata, RFC1918, loopback). Closing the window fully would
    require a custom transport adapter that pins the resolved IP — out
    of scope for this slice.
    """
    host = urlparse(url).hostname
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for _, _, _, _, sockaddr in infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            return False
        if ip.is_reserved:
            return False
        if any(ip in net for net in _BLOCKED_NETWORKS):
            return False
    return True


# ---------------------------------------------------------------------------
# Content extraction (HTML → markdown)
# ---------------------------------------------------------------------------


def extract_content(
    body: str,
    content_type: str,
    selector: Optional[str] = None,
) -> Optional[str]:
    """Convert a fetched response body into markdown ready for a
    knowledge file.

    Returns None if the content type is not supported. Caller maps
    that to ``fetch-error``.

    * ``text/markdown`` and ``text/plain`` are passed through.
    * ``text/html`` is processed: optional CSS selector picks a
      subtree, then ``markdownify`` converts it. If the selector
      yields no match, the full document is converted.
    * Any other content type returns None.
    """
    ct = (content_type or "").split(";", 1)[0].strip().lower()
    if ct in (
        "text/markdown",
        "text/plain",
        "text/x-markdown",
        # XML-family content types are passed through verbatim so
        # downstream consumers (the #144 spider parsing sitemap.xml,
        # for instance) can parse the structure themselves.
        "application/xml",
        "text/xml",
        "application/atom+xml",
        "application/rss+xml",
    ):
        return body
    if ct in ("text/html", "application/xhtml+xml"):
        soup = BeautifulSoup(body, "html.parser")
        if selector:
            chosen = soup.select_one(selector)
            if chosen is not None:
                return markdownify(str(chosen)).strip()
        return markdownify(str(soup)).strip()
    return None


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def _cache_path_for(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return KNOWLEDGE_SYNC_CACHE_DIR / f"{digest}.json"


def _load_cache(url: str) -> Optional[Dict]:
    path = _cache_path_for(url)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _save_cache(url: str, entry: Dict) -> None:
    KNOWLEDGE_SYNC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path_for(url)
    path.write_text(
        json.dumps(entry, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_iso(stamp: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------


class HttpFetcher:
    """Synchronous HTTP fetcher with SSRF guard, caching, and rate limit.

    Constructed once per sync run so the rate limiter and any shared
    session state span all sources fetched in that run.
    """

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        session: Optional[requests.Session] = None,
        max_redirects: int = MAX_REDIRECTS,
        max_bytes: int = MAX_BYTES,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._rate_limiter = rate_limiter or RateLimiter()
        self._session = session or requests.Session()
        self._max_redirects = max_redirects
        self._max_bytes = max_bytes
        self._timeout = timeout

    def fetch(
        self,
        url: str,
        *,
        selector: Optional[str] = None,
        cache_ttl: int = DEFAULT_CACHE_TTL,
    ) -> FetchOutcome:
        """Fetch ``url`` and return a :class:`FetchOutcome`.

        ``cache_ttl`` of ``0`` bypasses the cache entirely. Negative
        values are rejected up-stream; this method assumes the value
        has been validated.

        Cache flow:
          * cache_ttl > 0 and a cached entry is within TTL → return
            cached content (``from_cache=True``)
          * cached entry expired → conditional GET with ETag /
            Last-Modified; 304 refreshes timestamp and reuses content
          * no cache or 200 OK → write/replace cache entry
        """
        # Cache fast path
        if cache_ttl > 0:
            entry = _load_cache(url)
            if entry and self._cache_is_fresh(entry, cache_ttl):
                return FetchOutcome(
                    kind="content",
                    content=entry.get("content"),
                    from_cache=True,
                )

        return self._fetch_network(url, selector, cache_ttl)

    # -- internal helpers --------------------------------------------------

    def _cache_is_fresh(self, entry: Dict, cache_ttl: int) -> bool:
        fetched = _parse_iso(entry.get("fetched_at", ""))
        if fetched is None:
            return False
        age = (datetime.now(timezone.utc) - fetched).total_seconds()
        return age < cache_ttl

    def _fetch_network(
        self,
        url: str,
        selector: Optional[str],
        cache_ttl: int,
    ) -> FetchOutcome:
        cached = _load_cache(url)
        current_url = url
        for hop in range(self._max_redirects + 1):
            if not _is_url_safe(current_url):
                return FetchOutcome(
                    kind="fetch-error",
                    message=(
                        f"Refusing to fetch {current_url!r}: resolves to "
                        "a blocked address (private / loopback / link-local "
                        "/ reserved)."
                    ),
                )
            host = urlparse(current_url).hostname or ""
            self._rate_limiter.wait(host)

            headers = self._conditional_headers(cached, current_url == url)

            try:
                response = self._session.get(
                    current_url,
                    headers=headers,
                    timeout=self._timeout,
                    stream=True,
                    allow_redirects=False,
                )
            except requests.Timeout as exc:
                return FetchOutcome(
                    kind="fetch-error",
                    message=f"Timeout fetching {current_url!r}: {exc}",
                )
            except requests.ConnectionError as exc:
                return FetchOutcome(
                    kind="fetch-error",
                    message=(
                        f"Connection error fetching {current_url!r}: {exc}"
                    ),
                )
            except requests.RequestException as exc:
                return FetchOutcome(
                    kind="fetch-error",
                    message=f"Request error fetching {current_url!r}: {exc}",
                )

            status = response.status_code

            if status in (301, 302, 303, 307, 308):
                next_url = response.headers.get("Location")
                response.close()
                if not next_url:
                    return FetchOutcome(
                        kind="fetch-error",
                        message=(
                            f"{status} redirect from {current_url!r} with "
                            "no Location header."
                        ),
                    )
                current_url = requests.compat.urljoin(current_url, next_url)
                continue

            if status == 304:
                if cached is None:
                    response.close()
                    return FetchOutcome(
                        kind="fetch-error",
                        message=(
                            f"304 from {current_url!r} but no cached body "
                            "to reuse."
                        ),
                    )
                response.close()
                cached["fetched_at"] = _now_iso()
                _save_cache(url, cached)
                return FetchOutcome(
                    kind="content",
                    content=cached.get("content"),
                    from_cache=False,
                )

            if 400 <= status < 500:
                response.close()
                return FetchOutcome(
                    kind="source-missing",
                    message=(
                        f"HTTP {status} for {current_url!r}: the upstream "
                        "URL is no longer available. Edit sources.yml."
                    ),
                )

            if status >= 500:
                response.close()
                return FetchOutcome(
                    kind="fetch-error",
                    message=(
                        f"HTTP {status} for {current_url!r}: transient "
                        "upstream failure."
                    ),
                )

            # 2xx — stream body with size enforcement
            return self._consume_response(
                url=url,
                response=response,
                selector=selector,
            )

        return FetchOutcome(
            kind="fetch-error",
            message=(
                f"Redirect chain exceeded {self._max_redirects} hops "
                f"starting from {url!r}."
            ),
        )

    def _conditional_headers(
        self,
        cached: Optional[Dict],
        first_hop: bool,
    ) -> Dict[str, str]:
        """Conditional GET headers from the cached entry (if any).

        Only applied on the first hop — after a redirect, the upstream
        URL is different so cached validators don't apply.
        """
        if not cached or not first_hop:
            return {}
        headers: Dict[str, str] = {}
        if cached.get("etag"):
            headers["If-None-Match"] = cached["etag"]
        if cached.get("last_modified"):
            headers["If-Modified-Since"] = cached["last_modified"]
        return headers

    def _consume_response(
        self,
        url: str,
        response: requests.Response,
        selector: Optional[str],
    ) -> FetchOutcome:
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                declared = int(content_length)
                if declared > self._max_bytes:
                    response.close()
                    return FetchOutcome(
                        kind="too-large",
                        message=(
                            f"Content-Length {declared} exceeds limit "
                            f"{self._max_bytes} for {url!r}."
                        ),
                    )
            except ValueError:
                pass  # malformed header — fall through to streamed check

        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=8192, decode_unicode=False):
            if not chunk:
                continue
            total += len(chunk)
            if total > self._max_bytes:
                response.close()
                return FetchOutcome(
                    kind="too-large",
                    message=(
                        f"Response body exceeded {self._max_bytes} bytes "
                        f"for {url!r}."
                    ),
                )
            chunks.append(chunk)
        response.close()

        body_bytes = b"".join(chunks)
        # NB: don't use response.apparent_encoding here — it triggers a
        # second read of response.content, which raises because we
        # already consumed the body via iter_content().
        encoding = response.encoding or "utf-8"
        try:
            body = body_bytes.decode(encoding, errors="replace")
        except LookupError:
            body = body_bytes.decode("utf-8", errors="replace")

        content_type = response.headers.get("Content-Type", "")
        content = extract_content(body, content_type, selector)
        if content is None:
            return FetchOutcome(
                kind="fetch-error",
                message=(
                    f"Unsupported Content-Type {content_type!r} for {url!r}."
                ),
            )

        entry = {
            "url": url,
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "fetched_at": _now_iso(),
            "content": content,
        }
        _save_cache(url, entry)

        return FetchOutcome(kind="content", content=content, from_cache=False)
