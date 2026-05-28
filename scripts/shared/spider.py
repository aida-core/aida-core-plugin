# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""URL discovery spider for the knowledge curator (#144).

Walks configured ``roots`` in an agent's ``sources.yml`` and emits
candidate URLs that haven't been seen before, ready to be written into
``decisions.json`` as ``pending`` entries for the curator to verdict.

Hygiene rules (non-negotiable):

* **Sitemap-first.** If the root looks like a sitemap (XML ending in
  ``.xml`` or ``sitemap`` in the URL), parse it directly. Otherwise
  attempt the conventional ``/sitemap.xml`` at the root's origin
  before falling back to recursive HTML crawl. The recursive path
  honors ``robots.txt`` and stays within ``max_depth`` / ``max_urls``.
* **Domain allowlist.** A root configures a single origin; the spider
  never wanders off it. Cross-domain links found in HTML are dropped.
* **Per-host rate limit.** Reuses :class:`http_source.RateLimiter` so
  the same ≥0.5s gap applies as in #143.
* **Concurrency.** Different origins run in parallel via a
  ``ThreadPoolExecutor``. Within an origin, requests serialize through
  the rate limiter. Linear speedup on multi-domain crawls (e.g.,
  agentskills.io + docs.claude.com run side-by-side).

The spider is deterministic — it returns a sorted list of URLs and
writes nothing on its own. The caller (``/aida knowledge discover``)
turns those URLs into ``Decision(status="pending")`` entries and goes
through :func:`decisions_log.write_decisions`.
"""

from __future__ import annotations

import re
import socket
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from .http_source import (
    HttpFetcher,
    RateLimiter,
    _is_url_safe,
)

DEFAULT_MAX_DEPTH = 3
DEFAULT_MAX_URLS = 200
DEFAULT_CONCURRENCY = 4


@dataclass
class RootConfig:
    """One ``roots:`` entry from sources.yml, validated."""

    url: str
    name: str
    max_depth: int = DEFAULT_MAX_DEPTH
    max_urls: int = DEFAULT_MAX_URLS

    @property
    def origin(self) -> str:
        parsed = urlparse(self.url)
        return f"{parsed.scheme}://{parsed.netloc}"


@dataclass
class SpiderResult:
    """Output of a spider run.

    ``discovered`` is sorted, deduplicated across roots, and includes
    each URL's source root name (for the ``source_root`` field on
    ``Decision``).

    ``errors`` collects non-fatal per-root issues — robots.txt
    blocked, sitemap unreachable, depth/url cap reached — so the
    caller can surface them without aborting the whole walk.
    """

    discovered: List[Tuple[str, str]] = field(default_factory=list)
    """List of (url, source_root_name)."""

    errors: List[str] = field(default_factory=list)
    """Human-readable non-fatal messages."""


# ---------------------------------------------------------------------------
# Helpers (pure)
# ---------------------------------------------------------------------------


def _same_origin(a: str, b: str) -> bool:
    pa, pb = urlparse(a), urlparse(b)
    return (pa.scheme, pa.netloc) == (pb.scheme, pb.netloc)


def _looks_like_sitemap_url(url: str) -> bool:
    """Heuristic: this URL probably *is* a sitemap (not a page that
    might link to one)."""
    lower = url.lower()
    return lower.endswith(".xml") or "sitemap" in lower


def _parse_sitemap(body: str, base_url: str) -> List[str]:
    """Extract ``<loc>`` URLs from a sitemap or sitemap-index. Returns
    a flat list (sitemap-index entries are not recursively fetched
    here — they're returned and the caller decides whether to walk
    them)."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    urls: List[str] = []
    for loc in root.iter():
        tag = loc.tag.rsplit("}", 1)[-1]
        if tag == "loc" and loc.text:
            urls.append(urljoin(base_url, loc.text.strip()))
    return urls


_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _extract_links_from_html(body: str, base_url: str) -> List[str]:
    """Pull links out of a page body, resolved against ``base_url``.

    Extracts both HTML anchor (``<a href>``) and Markdown link
    (``[text](url)``) styles. The HttpFetcher converts HTML to
    Markdown by default, so most bodies the spider sees during a
    recursive crawl will be in markdown form; we still try HTML
    parsing in case the body slipped through as-is.
    """
    urls: List[str] = []

    soup = BeautifulSoup(body, "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if not isinstance(href, str):
            continue
        urls.append(href)

    for match in _MARKDOWN_LINK_RE.finditer(body):
        urls.append(match.group(1))

    out: List[str] = []
    seen: Set[str] = set()
    for raw in urls:
        if raw.startswith("#") or raw.startswith("mailto:"):
            continue
        resolved = urljoin(base_url, raw)
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


def _is_robots_allowed(
    robots: Optional[RobotFileParser], url: str
) -> bool:
    if robots is None:
        return True
    try:
        return robots.can_fetch("*", url)
    except Exception:
        # Defensive: if the parser blows up on a URL, default to
        # allowed. robots.txt is hygiene, not a security boundary.
        return True


def _load_robots(
    fetcher: HttpFetcher, origin: str
) -> Optional[RobotFileParser]:
    """Fetch and parse robots.txt for ``origin``. Returns None if the
    file is unreachable or unparseable (treat as no rules)."""
    robots_url = urljoin(origin + "/", "robots.txt")
    outcome = fetcher.fetch(robots_url, cache_ttl=86_400)
    # Any non-content outcome → assume no rules.
    if outcome.kind != "content" or not outcome.content:
        return None
    rp = RobotFileParser()
    rp.parse(outcome.content.splitlines())
    return rp


# ---------------------------------------------------------------------------
# Per-root walk
# ---------------------------------------------------------------------------


def _walk_root(
    fetcher: HttpFetcher, root: RootConfig
) -> SpiderResult:
    """Walk a single root and return its discoveries.

    Sitemap-first; falls back to recursive HTML crawl bounded by
    ``max_depth`` and ``max_urls``. ``robots.txt`` is consulted before
    every fetch.
    """
    result = SpiderResult()
    origin = root.origin

    if not _is_url_safe(root.url):
        result.errors.append(
            f"Root {root.name!r} ({root.url}) resolves to a blocked "
            "address; refusing to walk it."
        )
        return result

    robots = _load_robots(fetcher, origin)

    # Try sitemap-first
    sitemap_urls = _try_sitemap(fetcher, root, robots, result)
    if sitemap_urls is not None:
        for url in sitemap_urls[: root.max_urls]:
            if _same_origin(url, origin) and _is_robots_allowed(robots, url):
                result.discovered.append((url, root.name))
        if len(sitemap_urls) > root.max_urls:
            result.errors.append(
                f"Root {root.name!r} sitemap returned "
                f"{len(sitemap_urls)} URLs; truncated to "
                f"{root.max_urls} (raise `max_urls` to include more)."
            )
        return result

    # Recursive HTML crawl
    _recursive_crawl(fetcher, root, robots, result)
    return result


def _try_sitemap(
    fetcher: HttpFetcher,
    root: RootConfig,
    robots: Optional[RobotFileParser],
    result: SpiderResult,
) -> Optional[List[str]]:
    """Attempt to pull a sitemap and return URLs. Returns None if no
    sitemap is available (signaling: fall through to crawl)."""
    candidates: List[str] = []
    if _looks_like_sitemap_url(root.url):
        candidates.append(root.url)
    candidates.append(urljoin(root.origin + "/", "sitemap.xml"))

    seen: Set[str] = set()
    for sitemap_url in candidates:
        if sitemap_url in seen:
            continue
        seen.add(sitemap_url)
        if not _is_robots_allowed(robots, sitemap_url):
            continue
        outcome = fetcher.fetch(sitemap_url, cache_ttl=86_400)
        if outcome.kind != "content" or not outcome.content:
            continue
        urls = _parse_sitemap(outcome.content, sitemap_url)
        if urls:
            return urls
    return None


def _recursive_crawl(
    fetcher: HttpFetcher,
    root: RootConfig,
    robots: Optional[RobotFileParser],
    result: SpiderResult,
) -> None:
    """Fallback BFS crawl from ``root.url``, bounded by ``max_depth``
    and ``max_urls``."""
    queue: List[Tuple[str, int]] = [(root.url, 0)]
    visited: Set[str] = set()

    while queue and len(result.discovered) < root.max_urls:
        url, depth = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        if not _same_origin(url, root.origin):
            continue
        if not _is_robots_allowed(robots, url):
            continue

        result.discovered.append((url, root.name))

        if depth >= root.max_depth:
            continue

        outcome = fetcher.fetch(url, cache_ttl=86_400)
        if outcome.kind != "content" or not outcome.content:
            continue

        # Skip if the body is plain markdown — only HTML has links to
        # follow. (The fetcher already converted, but a markdown body
        # won't have anchor structure to extract.)
        for link in _extract_links_from_html(outcome.content, url):
            if link not in visited and _same_origin(link, root.origin):
                queue.append((link, depth + 1))


# ---------------------------------------------------------------------------
# Concurrent driver
# ---------------------------------------------------------------------------


def discover(
    roots: Iterable[RootConfig],
    *,
    fetcher: Optional[HttpFetcher] = None,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> SpiderResult:
    """Walk every root and return one merged :class:`SpiderResult`.

    Different roots run in parallel via a thread pool. Within a root,
    requests serialize through the shared per-host rate limiter.

    The deduplication is post-merge: a URL appearing under multiple
    roots takes its first-walked root's name as ``source_root``
    (deterministic per call because results are merged in
    completion-order then sorted).
    """
    roots_list = list(roots)
    if not roots_list:
        return SpiderResult()

    rate_limiter = RateLimiter()
    fetcher = fetcher or HttpFetcher(rate_limiter=rate_limiter)

    merged = SpiderResult()
    seen_urls: Set[str] = set()

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(_walk_root, fetcher, root): root
            for root in roots_list
        }
        for fut in as_completed(futures):
            root = futures[fut]
            try:
                sub = fut.result()
            except (OSError, socket.gaierror) as exc:
                merged.errors.append(
                    f"Root {root.name!r} ({root.url}) walk failed: {exc}"
                )
                continue
            merged.errors.extend(sub.errors)
            for url, root_name in sub.discovered:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                merged.discovered.append((url, root_name))

    merged.discovered.sort(key=lambda pair: pair[0])
    return merged


def parse_roots(raw: object) -> List[RootConfig]:
    """Parse and validate the ``roots:`` block from sources.yml.

    Accepts None / [] (no roots configured). Raises ``ValueError`` on
    structural problems so the caller can surface a clear error.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("`roots:` must be a list of objects.")
    out: List[RootConfig] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError(
                f"Each `roots` entry must be an object, got {entry!r}."
            )
        url = entry.get("url")
        name = entry.get("name")
        if not isinstance(url, str) or not url:
            raise ValueError(f"Root entry is missing `url`: {entry!r}.")
        if not isinstance(name, str) or not name:
            raise ValueError(
                f"Root entry is missing `name`: {entry!r}."
            )
        max_depth = entry.get("max_depth", DEFAULT_MAX_DEPTH)
        max_urls = entry.get("max_urls", DEFAULT_MAX_URLS)
        if not isinstance(max_depth, int) or max_depth < 0:
            raise ValueError(
                f"Root {name!r}: max_depth must be a non-negative "
                f"int, got {max_depth!r}."
            )
        if not isinstance(max_urls, int) or max_urls <= 0:
            raise ValueError(
                f"Root {name!r}: max_urls must be a positive int, "
                f"got {max_urls!r}."
            )
        out.append(
            RootConfig(
                url=url,
                name=name,
                max_depth=max_depth,
                max_urls=max_urls,
            )
        )
    return out
