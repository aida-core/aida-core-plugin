---
type: adr
title: "ADR-012: Split expert-registry into a separate plugin"
description: "Move the expert-registry skill out of aida-core into a dedicated aida-expert-plugin — keeping aida-core focused on extension primitives rather than orchestration opinions."
status: proposed
date: "2026-05-23"
deciders:
  - "@oakensoul"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# ADR-012: Split expert-registry into a separate plugin

## Status

Proposed — 2026-05-23.

## Context

`aida-core-plugin` ships eight management skills today:

| Skill | What it does | Layer |
| --- | --- | --- |
| `agent-manager` | CRUD on agent definitions | Foundation |
| `skill-manager` | CRUD on skill definitions | Foundation |
| `plugin-manager` | CRUD + scaffold for plugins | Foundation |
| `claude-md-manager` | CRUD on CLAUDE.md files | Foundation |
| `hook-manager` | CRUD on hooks in settings.json | Foundation |
| `memento` | Session persistence | Foundation |
| `permissions` | Permission / settings management | Foundation |
| **`expert-registry`** | **Panel composition + activation policy on top of agents** | **Opinion** |

Seven of those are *primitives* — CRUD operations on extension types
Claude Code defines. The eighth, `expert-registry`, is an
*orchestration layer*: it tracks which agents are "active" for a
project, composes named panels (`code-review`,
`security-review`), and resolves resolution semantics (project
overrides global, with future support for mandatory experts that
can't be suppressed — see #60).

When we recently audited every closed issue for scope discipline
(closing #94's polyrepo-migration request as out-of-scope), the
expert-registry stood out as the next likely candidate. It's
already a generalization of "agent management" into "agent
*workflow* management" — a different product.

## Decision

Split `expert-registry` out of `aida-core-plugin` into a dedicated
`aida-expert-plugin` repository. `aida-core-plugin` keeps the
extension primitives; the new plugin owns panel composition,
mandatory experts, default panels (#60), token resolution, and
anything else that's orchestration-shaped.

## Rationale

**It's an opinion, not a primitive.** Panel templates + mandatory
experts + role tags is a specific philosophy. Not every plugin
author or team thinks in terms of expert panels. The other seven
skills, by contrast, are inherent to building Claude Code
extensions.

**Org-policy territory.** #60's headline use case is "security-expert
must participate in every review, period" — a compliance-driven
requirement. That's specific to organizations that have formal
review workflows, not foundational for plugin authoring.

**Independent evolution.** Tokens (`{{active}}`, `{{role:core}}`),
default panels, mandatory experts — these will keep growing. Better
as a focused plugin that can iterate quickly than as another concern
competing for `aida-core` review attention.

**Sets a clean pattern.** Once `aida-expert-plugin` exists, future
opinionated layers (`aida-review-plugin`, `aida-compliance-plugin`,
`aida-onboarding-plugin`) follow the same shape. `aida-core` is the
foundation; opinionated workflows ship as separate plugins that
depend on it.

**Honest read**: If we weren't already shipping expert-registry in
`aida-core`, we probably wouldn't add it there now.

## Migration plan

The split is a breaking change — the `/aida expert ...` command
surface moves to the new plugin. Migration in phases:

1. **This release (1.5.20+)**: file this ADR. No code change yet.
2. **Mark deprecated** (next 1.x release): add a deprecation notice
   to `skills/expert-registry/SKILL.md` linking to this ADR.
   Skill keeps working; users see a hint that it will move.
3. **Carve out `aida-expert-plugin`** (when ready): create the new
   repo using `/aida plugin scaffold "aida-expert"`, copy
   `skills/expert-registry/` over (preserving git history via
   `git filter-repo` or `git subtree split`), publish the new
   plugin.
4. **Remove from aida-core** (2.0.0, breaking): delete
   `skills/expert-registry/` from this repo. The aida dispatcher
   no longer routes `/aida expert ...` — users install
   `aida-expert-plugin` to get it back. Note in 2.0.0 release
   notes prominently. Note this issue / ADR in the migration guide.

The new plugin **depends on `aida-core`** (it walks agent metadata,
reads global config) but `aida-core` doesn't depend on it. That's
the right direction.

## Consequences

### Positive

- `aida-core` stays focused on primitives. Smaller, simpler, easier
  to review.
- Expert-panel work (#60 and beyond) ships in a focused repo that
  can iterate on its own release cadence.
- Sets a precedent: opinionated workflows live in their own plugins.
- Users who don't want expert panels don't pay for them (smaller
  install footprint, fewer skill files to load).

### Negative

- Breaking change at 2.0.0 — users currently relying on `/aida
  expert ...` must install `aida-expert-plugin` to keep it working.
  Deprecation cycle mitigates this.
- New repo to maintain (CI, releases, marketplace entry).
- Documentation churn — README, getting-started, etc. reference
  expert-registry and will need updates.

### Neutral

- The `/aida expert ...` command surface stays the same; only the
  hosting plugin changes.

## Open questions

- **Timing of 2.0.0**: don't rush. Let the deprecation notice sit
  for at least one minor release cycle so downstream users see it
  before the break.
- **Other split candidates**: `memento` is also borderline (session
  persistence is a workflow opinion). Not deciding here, but worth
  watching.
- **#60's home**: the default-panels + mandatory-experts feature
  lands in `aida-expert-plugin` once it exists, not in aida-core.
  Issue updated to reflect this.

## Related

- #60 — default panels + mandatory experts (deferred to the new
  plugin)
- #94 — closed as out-of-scope for a related reason (monorepo
  migration); this ADR is part of the same scope-discipline pass
- ADR-008 — marketplace-centric distribution (sets up the
  expectation that plugins are first-class distribution units)
