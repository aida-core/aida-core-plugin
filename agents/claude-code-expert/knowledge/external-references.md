---
type: knowledge
name: external-references
description: External URLs the claude-code-expert agent's knowledge derives from. Consult these when rebuilding or expanding the agent's knowledge files.
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# External References

URLs the `claude-code-expert` agent should consult when rebuilding or expanding its knowledge. These are upstream sources — not pinned content. When this knowledge base is refreshed, walk this list and refresh the relevant files.

Once knowledge-sync gains HTTP source support (see issue tracking the
knowledge-sync remote fetchers), these entries should migrate into
`agents/claude-code-expert/knowledge/sources.yml` so they pull
automatically.

## Skill creation

| URL | What it informs |
|-----|-----------------|
| <https://support.claude.com/en/articles/12512176-what-are-skills> | Anthropic's official "What are Skills" article. Authoritative on the skill concept, activation model, and intended use. Refresh `knowledge/skills.md` and `knowledge/extension-types.md` against this. |
| <https://agentskills.io/> | Community resource for skill creation. Covers structure, conventions, and authoring patterns. Refresh `knowledge/skills.md`, `knowledge/design-patterns.md`, and the review-skill rubric guidance against this. |
| <https://agentskills.io/skill-creation/evaluating-skills> | Methodology for behavioral evaluation of skills (`evals/evals.json`, with/without baseline, assertion grading). Source material for the Phase 3 behavioral-eval design in the review skill. |

## Claude Code platform

These aren't currently mirrored but the agent's knowledge frequently
references them. Add as the agent's coverage grows.

| URL | What it informs |
|-----|-----------------|
| <https://docs.claude.com/en/docs/claude-code> | Claude Code documentation root |
| <https://docs.claude.com/en/docs/claude-code/sdk> | Agent SDK reference |

## How to use this file

When asked to refresh or rebuild the agent's knowledge:

1. Walk this list and visit each URL
2. For each, identify which knowledge files should reflect the upstream
3. Update those files; preserve any local additions outside marker blocks
4. If a URL has materially changed since last refresh, note the date in the
   relevant knowledge file's header

Do not vendor entire pages into knowledge files. Capture concepts,
canonical phrasings, and structural conventions; keep prose tight.
