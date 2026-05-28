---
type: skill
name: knowledge-sync
description: >-
  Keep agent knowledge files current with their declared upstream
  sources. Reads agents/<name>/knowledge/sources.yml, fetches each
  source, and updates marker-delimited sections in target knowledge
  files. Supports local files and HTTP/HTTPS URLs, plus URL
  discovery via the sitemap-first spider.
version: 0.3.0
user-invocable: true
argument-hint: "[sync <agent>|status <agent>|discover <agent>]"
tags:
  - core
  - management
  - knowledge
  - agents
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Knowledge Sync

Keeps an agent's knowledge files current with their declared upstream
sources. Each agent owns a `sources.yml` that declares where its
"upstream facts" come from; the skill walks that declaration,
fetches each source, and updates marker-delimited sections of the
agent's knowledge files (#22).

Custom design decisions / agent author conventions outside the marker
blocks are preserved byte-for-byte. **Only the body between
`<!-- upstream:start name="..." -->` and `<!-- upstream:end -->`
markers is replaced.**

## Activation

This skill activates when:

- User invokes `/aida knowledge sync <agent>`
- User invokes `/aida knowledge status <agent>` or `--all`
- Routed from `aida` skill for any knowledge operation

## Operations

| Operation       | Mode    | Description                                                            |
| --------------- | ------- | ---------------------------------------------------------------------- |
| `sync`          | Apply   | Read sources.yml + in-use decisions, fetch, replace targeted sections  |
| `status`        | Inspect | Dry-run the sync; report changed/unchanged/missing/conflict-suppressed |
| `discover`      | Spider  | Walk configured roots; add new URLs to decisions.json                  |
| `audit`         | Inspect | Report pending count, stale verdicts, never-synced URLs                |
| `promote`       | Apply   | Manually mark a URL in-use (skip the LLM curator)                      |
| `regenerate-md` | Repair  | Rebuild decisions.md from decisions.json                               |

`discover` is the deterministic spider half of the curator workflow
(#144). It walks `roots:` declared in `sources.yml`, finds candidate
URLs, and writes them as `status: pending` into `decisions.json` for
the `knowledge-curator` skill to verdict.

`sync` reads both `sources.yml` (hand-curated entries) and
`decisions.json` (`status: in-use` entries from the curator workflow).
A URL listed in both `sources.yml` AND marked `rejected` in
`decisions.json` produces a `conflict-suppressed` result so the user
can reconcile rather than silently sync a rejected source.

`audit` is a read-only report — pending count, stale LLM verdicts
(default: older than 90 days), in-use entries that have never been
synced, in-use entries missing `target_file` / `target_section`.

`promote` is a manual override for the LLM curator. Useful when you
already know a URL belongs in an agent's corpus — provide
`--url <X> --file <F> --section <S>` and it lands directly as
in-use with `decided_by: human`. Refuses to overwrite locked
decisions.

`regenerate-md` is a repair command. If a user has hand-edited
`decisions.md` (despite the generated-file banner), this rebuilds
it from `decisions.json` (the source of truth).

## Source declaration (`sources.yml`)

Lives at `agents/<agent>/knowledge/sources.yml`. The file may carry
two top-level blocks: `roots:` for the spider (#144) and `sources:`
for explicit sync targets.

### Schema version

`sources.yml` includes an optional `version: "1.0.0"` field. Readers
fall back to "1.0.0" if absent. Bump only on backwards-incompatible
changes.

### `roots:` (optional — for `/aida knowledge discover`)

```yaml
roots:
  - url: https://agentskills.io/sitemap.xml
    name: agentskills
    max_depth: 3       # optional, default 3 (used only on fallback HTML crawl)
    max_urls: 200      # optional, default 200 (truncates per-root)
```

Each root configures one origin for the spider to walk. The spider
prefers the URL as a sitemap if it looks like one (XML extension or
"sitemap" in the URL); otherwise it tries `/sitemap.xml` at the
origin; otherwise it falls back to a BFS HTML crawl bounded by
`max_depth` and `max_urls`. `robots.txt` is honored. Different roots
walk in parallel; same-host requests serialize through the 0.5s
per-host rate limiter.

URLs found by the spider land in `decisions.json` as
`status: pending`. The `knowledge-curator` skill turns them into
in-use or rejected verdicts.

### `sources:` — what to actively sync

A source is either a local file or a remote URL:

```yaml
sources:
  # Local file relative to the project root
  - name: project-adrs-extension-types
    type: local
    path: docs/architecture/adr/001-skills-first-architecture.md
    target:
      file: knowledge/extension-types.md
      section: extension-types-overview

  # Remote HTTP/HTTPS source
  - name: claude-skills-overview
    type: http
    url: https://support.claude.com/en/articles/12512176-what-are-skills
    selector: "main article"      # optional CSS selector
    cache_ttl: 86400              # optional, seconds
    target:
      file: knowledge/skills.md
      section: claude-skills-upstream
```

### Common fields

- `name`: identifier for the source (logs / error messages use this)
- `type`: `local`, `http`, or `https`
- `target.file`: path to the knowledge file to update (relative to
  the agent's knowledge directory)
- `target.section`: section name. The knowledge file must already
  contain `<!-- upstream:start name="<section>" -->` ... markers

### `type: local`

- `path`: path to the upstream file (relative to project root)

### `type: http` / `type: https`

- `url` (required): full URL to fetch
- `selector` (optional): CSS selector to extract a subtree before
  conversion. Defaults to the full document. If the selector matches
  nothing the fetcher falls back to the full document
- `cache_ttl` (optional): seconds before re-fetching. Default `86400`
  (24h). `0` bypasses the cache entirely (always fetches). Negative
  values are rejected at source load time

#### Content handling

- `text/markdown` and `text/plain` are passed through verbatim
- `text/html` and `application/xhtml+xml` are converted to markdown
  via BeautifulSoup + markdownify; the optional `selector` picks a
  subtree first
- Any other Content-Type is rejected as `fetch-error`

#### Networking guarantees

- **SSRF guard:** URLs that resolve to private (RFC1918), loopback,
  link-local (incl. AWS metadata at 169.254.169.254), reserved, or
  IPv6 ULA / link-local addresses are refused. The check runs at
  every redirect hop, so a public URL that 302s to a private target
  is also blocked
- **Redirects** are followed manually and capped at 5 hops; chains
  longer than that report `fetch-error`
- **Rate limiting:** silent, in-process, per-host. Minimum 0.5s
  between calls to the same hostname during a single sync run
- **Response size:** capped at 2 MiB. Larger responses (declared via
  `Content-Length` or measured during streaming) return `too-large`
- **Cache:** responses are stored at
  `~/.aida/cache/knowledge-sync/<sha256(url)>.json` with the fetched
  body, ETag, and Last-Modified header. On expiry, the next fetch
  sends conditional GET headers; a 304 refreshes the cache timestamp
  and reuses the cached body

The section markers are the single source of truth for "this content
is replaceable by sync". Knowledge file authors decide which parts
to surface for syncing; everything else they wrote stays.

## Path Resolution

**Base Directory:** Provided when skill loads via
`<command-message>` tags.

**Script execution:**

```text
~/.aida/venv/bin/python3 {base_directory}/scripts/sync.py \
  --agent <name> [--dry-run]
```

Returns a JSON report (one entry per source) with each target's
status:

| Status            | Meaning                                                     |
| ----------------- | ----------------------------------------------------------- |
| `unchanged`       | Section already matches the upstream body                   |
| `changed`         | Section updated (apply mode)                                |
| `would-change`    | Section would update (dry-run / status mode)                |
| `source-missing`  | HTTP 4xx, or a local file that no longer exists             |
| `fetch-error`     | HTTP 5xx, DNS / timeout / SSRF block, unsupported MIME type |
| `too-large`       | Response body exceeded the 2 MiB cap                        |
| `missing-section` | Knowledge file lacks the named marker block                 |
| `target-missing`  | Knowledge file does not exist                               |
| `invalid-target`  | Source declaration is malformed                             |
| `marker-error`    | Markers are unbalanced inside the knowledge file            |
| `write-error`     | Failed to write the updated knowledge file                  |

HTTP sources also include a `from_cache: true` field on the per-source
result when the body was served entirely from cache without a network
round-trip (a 304 refresh does not count as cache-only — it touched the
network to revalidate).

## Capabilities (this release)

- Local-file sources (`type: local`)
- HTTP / HTTPS sources (`type: http` / `https`) with SSRF guard,
  per-host rate limit, redirect cap, response-size cap, and
  ETag/Last-Modified caching
- Marker-based section replacement
- Dry-run + apply modes
- Per-source error reporting (one bad source doesn't fail the whole
  sync — the others continue)

## Out of scope (deferred)

- Spidering / URL discovery — tracked in #144
- LLM-driven curation (decide which discovered URLs are worth using)
  with a persisted decision log — tracked in #144
- Command sources (`type: command`) — run a command, use stdout
- API sources (`type: api`) — query a JSON endpoint
- Authentication (cookies, OAuth, API keys)
- JavaScript-rendered pages (headless browser)
- Interactive review UX — current sync is "show diff via status,
  then apply via sync". A keep/reject-per-change wizard is a future
  enhancement
- Cross-agent batch sync (`/aida knowledge sync --all`) — current
  per-agent invocation is enough to land the surface
