---
type: skill
name: knowledge-sync
description: >-
  Keep agent knowledge files current with their declared upstream
  sources. Reads agents/<name>/knowledge/sources.yml, fetches
  each source, and updates marker-delimited sections in target
  knowledge files. Local-file sources only in Phase 1.
version: 0.1.0
user-invocable: true
argument-hint: "[sync <agent>|status <agent>|status --all]"
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

| Operation | Mode      | Description                                       |
| --------- | --------- | ------------------------------------------------- |
| `sync`    | Apply     | Read sources.yml, fetch, replace targeted sections|
| `status`  | Inspect   | Dry-run the sync; report changed/unchanged/missing|

## Source declaration (`sources.yml`)

Lives at `agents/<agent>/knowledge/sources.yml`:

```yaml
sources:
  - name: project-adrs-extension-types
    type: local
    path: docs/architecture/adr/001-skills-first-architecture.md
    target:
      file: knowledge/extension-types.md
      section: extension-types-overview
```

Field reference:

- `name`: identifier for the source (logs / error messages use this)
- `type`: currently only `local` — fetches a file from disk relative
  to the project root. Future types (`web`, `command`, `api`) are on
  the roadmap (Phase 2 of #22)
- `path`: path to the upstream file (relative to project root)
- `target.file`: path to the knowledge file to update (relative to
  the agent's knowledge directory)
- `target.section`: section name. The knowledge file must already
  contain `<!-- upstream:start name="<section>" -->` ... markers

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
status: `unchanged` / `changed` / `missing-section` / `source-missing`.

## Phase 1 scope (this release)

- Local-file sources only (`type: local`)
- Marker-based section replacement
- Dry-run + apply modes
- Per-source error reporting (a missing source file doesn't crash
  the whole sync — that source just reports `source-missing` and the
  others continue)

## Out of scope (deferred)

- Web sources (`type: web`) — fetch from URL, extract content.
  Adding the dispatch hook for these is straightforward; the actual
  fetcher is a follow-up
- Command sources (`type: command`) — run a command, use stdout
- API sources (`type: api`) — query a JSON endpoint
- Interactive review UX — current sync is "show diff via status,
  then apply via sync". A keep/reject-per-change wizard is a future
  enhancement
- Cross-agent batch sync (`/aida knowledge sync --all`) — current
  per-agent invocation is enough to land the surface
