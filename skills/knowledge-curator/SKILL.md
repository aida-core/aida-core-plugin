---
type: skill
name: knowledge-curator
description: >-
  Decide which discovered URLs are worth pulling into an agent's
  knowledge corpus. Reads pending entries from
  `agents/<agent>/knowledge/decisions.json` (written by
  `knowledge-sync`'s discover command) and either flips each to
  in-use or rejected based on the agent's purpose, or walks them
  interactively with a human for override.
version: 0.1.0
user-invocable: true
argument-hint: "[curate <agent>|review <agent>]"
tags:
  - core
  - knowledge
  - agents
  - llm-workflow
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Knowledge Curator

Decides which discovered URLs are worth syncing into an agent's
knowledge corpus. Companion to the deterministic `knowledge-sync`
skill (#144).

**The split:**

- `knowledge-sync` owns the **mechanic** — fetch, parse, write
  marker-delimited sections. Deterministic Python.
- `knowledge-curator` (this skill) owns the **policy** — judge each
  candidate URL against the agent's purpose, decide in-use vs.
  rejected, persist the verdict. LLM-orchestrated.

## Activation

This skill activates when:

- User invokes `/aida knowledge curate <agent>`
- User invokes `/aida knowledge review <agent>`
- Routed from the `aida` skill for these operations

## Operations

| Operation | Mode        | Description                                          |
| --------- | ----------- | ---------------------------------------------------- |
| `curate`  | LLM-decides | Walk pending URLs; verdict each (in-use \| rejected) |
| `review`  | Interactive | Walk recent decisions; let human confirm or override |

## Critical invariants (read before any write)

**Atomic decisions file pair.** `decisions.json` and `decisions.md`
must stay in lockstep. Both are written together by
`scripts/shared/decisions_log.py::write_decisions(...)`. There is no
other supported write path.

**This skill MUST follow these rules:**

1. **Never write `decisions.json` directly** (no Edit / Write tool
   on that file). Read with `decisions_log.read_decisions(...)`;
   write with `decisions_log.write_decisions(...)`. The atomic write
   regenerates `decisions.md` from the JSON in the same call.
2. **Never hand-edit `decisions.md`.** It carries a generated-file
   banner at line 1. Any change you want to land must go through
   `decisions.json` and re-run `write_decisions`.
3. **Never re-decide `locked: true` entries.** A human has confirmed
   them; the curator skips. Only `/aida knowledge review` can flip
   a locked decision.
4. **Never decide already-decided entries.** The curator only
   verdicts `status: pending` entries. Existing `in-use` or
   `rejected` entries stay as they are unless `review` operates on
   them.

## Curate workflow (`/aida knowledge curate <agent>`)

The user wants the LLM to judge each pending URL discovered for the
target agent. Walk this sequence carefully:

### Step 1 — Load the curator's reasoning context

You need enough information to answer:
**"does this URL add something the agent doesn't already have?"**

Read into context:

1. **The agent's purpose** — `agents/<agent>/<agent>.md`. The
   frontmatter `description` is the load-bearing signal. The
   markdown body has supporting expertise / judgment notes.
2. **The agent's knowledge index** — `agents/<agent>/knowledge/index.md`.
   Tells you what files exist and what each covers.
3. **The heading structure of every existing knowledge file** —
   walk `agents/<agent>/knowledge/*.md` (excluding `index.md` and
   `external-references.md`), reading H1/H2/H3 headings into a
   compact outline. **You do not need to load full file bodies.**
   Headings alone show coverage scope; bodies bloat context. Add a
   targeted read only if a candidate URL appears to overlap a
   knowledge file and you need to disambiguate.
4. **The existing decisions** — `agents/<agent>/knowledge/decisions.json`
   loaded via `decisions_log.read_decisions(...)`. Use the prior
   rejections and approvals for consistency: do not contradict a
   prior locked rejection, and prefer reasoning consistent with
   prior verdicts.

### Step 2 — Walk pending entries

For each `Decision(status="pending")` in the existing decisions:

1. **Skip if `locked: true`.** (Curator never re-decides locked
   entries — those are human-confirmed.)
2. **Fetch a content sample.** Use
   `http_source.HttpFetcher().fetch(url)` and take the first ~500
   chars of `outcome.content`. Don't load the whole page — sample
   is enough to judge topic + relevance. If fetch fails (`source-missing`,
   `fetch-error`, `too-large`), record that as the verdict reason
   and reject the URL.
3. **Reason about the URL.** Ask yourself:
   - Is the topic on-domain for this agent's purpose?
   - Does the agent's existing knowledge already cover this topic?
     (Check headings.)
   - Does the content sample look authoritative and stable enough
     to vendor?
4. **Decide.** Either `status="in-use"` or `status="rejected"`.
5. **Write the verdict** by constructing a new `Decision(...)` and
   calling `upsert_decision(...)` then `write_decisions(...)`.
   Required fields:
   - `decided_at`: `decisions_log.now_iso()`
   - `decided_by`: `"llm"`
   - `reason`: one to three sentences explaining the verdict
   - `informs` (only when `in-use`): list of knowledge file
     basenames this URL should refresh

Batch all updates and call `write_decisions` once at the end —
the JSON+MD regeneration is the same cost regardless of batch
size, and one atomic write is simpler to reason about than N.

### Step 3 — Report

Tell the user what you decided. Group by verdict:

```text
Curated 12 pending URLs for agent 'claude-code-expert':
  ✓ 5 in-use (informs: skills.md, design-patterns.md)
  ✗ 7 rejected (out-of-scope / redundant)

decisions.json + decisions.md updated.
Run /aida knowledge review claude-code-expert to confirm or override.
```

If any URLs failed to fetch, surface those separately so the user
can edit `sources.yml` to remove or fix the root that produced them.

## Review workflow (`/aida knowledge review <agent>`)

The user wants to confirm, override, or lock the LLM curator's
recent verdicts. Walk this sequence:

### Step 1 — Load decisions

Read `agents/<agent>/knowledge/decisions.json` via
`decisions_log.read_decisions(...)`.

### Step 2 — Show the user

Present the recent LLM verdicts (those with `decided_by: "llm"`,
`locked: false`) grouped by status. For each, show:

- URL
- Decided-at timestamp
- Reason (one to three sentences)
- The `informs:` list if `in-use`

### Step 3 — Ask the user

For each verdict, the user can:

- **Confirm** (no change; optionally set `locked: true` so the
  curator never re-decides it)
- **Override** the verdict (flip in-use ↔ rejected; capture a new
  reason from the user, set `decided_by: "human"`)
- **Edit metadata** (update `informs:` for in-use entries; update
  `reason`)
- **Skip** (move on without touching)

Prefer running this interactively — `AskUserQuestion` for each
verdict — when the count is small. If there are many decisions
(>10), offer a "review all in batch" flow that walks them in a
single pass and accepts free-text per-entry input.

### Step 4 — Persist

Construct the new decisions list, call `write_decisions(...)`.
Report a short summary:

```text
Reviewed 12 decisions:
  3 confirmed and locked
  2 overridden (now in-use)
  7 unchanged

decisions.json + decisions.md updated.
```

## Path Resolution

**Base Directory:** Provided when skill loads via
`<command-message>` tags.

**Shared module imports** (run scripts under the AIDA venv):

```text
~/.aida/venv/bin/python3 -c "
import sys; sys.path.insert(0, '{base_directory}/../../scripts')
from shared.decisions_log import (
    Decision, read_decisions, write_decisions, upsert_decision, now_iso,
)
from shared.http_source import HttpFetcher
# ... your workflow here
"
```

The skill itself has no script entry point — the LLM workflow drives
the deterministic primitives directly.

## Out of scope (deferred to Slice 2 of #144)

- Sync integration — `/aida knowledge sync` will be extended to
  merge `decisions.json` `in-use` entries with `sources.yml`
- `/aida knowledge audit` — drift report (last-reviewed dates, new
  pages found upstream since last walk)
- `/aida knowledge promote <agent> <url>` — manual in-use without
  the curator
- `/aida knowledge regenerate-md` — repair if `decisions.md` is
  hand-modified
- Rich `decisions.md` formatting (Slice 1 ships a plain dump)
- `conflict-suppressed` sync status when `sources.yml` and
  `decisions.json` disagree
