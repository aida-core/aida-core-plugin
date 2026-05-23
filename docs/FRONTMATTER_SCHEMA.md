---
type: reference
title: "Frontmatter Schema"
description: "Reusable JSON Schema for AIDA markdown frontmatter — types, required fields, consumption guide for downstream plugins and marketplaces."
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Frontmatter Schema

AIDA Core ships a JSON Schema at the repo root,
[`.frontmatter-schema.json`](../.frontmatter-schema.json), that
validates the YAML frontmatter of every markdown file in this plugin
and is **intended to be reused verbatim by downstream plugins and
marketplaces**.

If you maintain a plugin or a marketplace, please consume this schema
rather than writing your own. Consistency across the ecosystem makes
search, indexing, and contributor tooling work the same way
everywhere.

## What it covers

The schema is type-driven. Every frontmatter block must declare a
`type`, and the schema applies type-specific required-field rules.
Ten types are supported today:

| `type` | Required fields | Used for |
| --- | --- | --- |
| `skill` | `name`, `description`, `version`, `tags` | SKILL.md files |
| `agent` | `name`, `description`, `version`, `tags` | Agent definitions |
| `adr` | `title`, `status`, `date` | Architecture Decision Records |
| `diagram` | `title`, `diagram-type` | Diagram markdown wrappers |
| `documentation` | `title` | General documentation pages |
| `guide` | `title` | How-to guides |
| `reference` | `title` | Reference docs |
| `changelog` | `title` | Changelog files |
| `readme` | `title` | README files |
| `issue` | `title`, `issue` | Issue-style notes |

The schema also constrains shapes: `name` must be kebab-case
(`^[a-z][a-z0-9-]*$`, 2-50 chars), `version` must be semver
(`^\d+\.\d+\.\d+$`), `description` is 10-500 chars, etc. Run
[`ajv`](https://ajv.js.org/) or
[`jsonschema`](https://python-jsonschema.readthedocs.io/) against
your frontmatter to see the full validation surface.

## How to consume it

### Option 1: Vendor the schema into your repo (recommended for now)

Copy `.frontmatter-schema.json` into your repo (`schemas/`
directory works) and validate against the local copy. Pin to a
specific aida-core release so the schema can't change under you.

```bash
# Pull the schema at a specific aida-core tag
curl -L https://raw.githubusercontent.com/aida-core/aida-core-plugin/v1.5.13/.frontmatter-schema.json \
  -o schemas/frontmatter.schema.json
```

Re-pull when you upgrade aida-core; review the diff to see what types
or required fields changed.

### Option 2: Reference the raw URL directly

If your validator supports HTTP `$ref`, point at the tagged raw URL.
Don't use `main` — that moves under you:

```json
{
  "$ref": "https://raw.githubusercontent.com/aida-core/aida-core-plugin/v1.5.13/.frontmatter-schema.json"
}
```

A future release may expose a stable URL via GitHub Pages; until then
the tagged raw URL is the contract.

## Type-enum expansion policy

The `type` enum grows when AIDA Core adds a new artifact category
that needs distinct required fields. Today's set covers the existing
artifacts; new entries are added carefully because every downstream
consumer that pinned a specific version inherits the new shape on
upgrade.

If you have an artifact that doesn't fit any existing type, you have
two options:

1. **Propose a new type upstream.** Open an issue with a brief
   description of what the artifact is, what fields it needs, and
   why an existing type doesn't fit. New types land in a minor
   release.
2. **Use `documentation` or `reference` and add custom fields.**
   The schema doesn't reject unknown properties, so you can add
   `team_owner`, `audience`, etc., on top of the documented
   required set. Validation still works against the AIDA-known
   fields; your extras are just ignored.

Generally prefer (1) when the new shape is something other plugins
might also want; prefer (2) when it's truly your project's concern.

## Why this matters

Without the shared schema, every downstream plugin reinvents
frontmatter conventions. The pain pattern that motivated this
contract (see issue #88):

- A marketplace maintainer wrote their own `schemas/frontmatter.schema.json`
- It required `title` + `description` for everything
- That broke the auto-generated SKILL.md (which uses `name`, not
  `title`, per AIDA convention)
- ~2 hours of debugging before discovering that AIDA Core already
  shipped the right schema

Sharing the schema avoids re-deriving the same field set across
repos and keeps tooling that reads frontmatter (search, listings,
knowledge indexes, automated routing) predictable.

## Related

- The validator in
  [splash-ai-marketplace](https://github.com/Splash-AI/splash-ai-marketplace)
  reads this schema for marketplace-wide validation
- Issue #89 tracks recommending `description` on documentation
  types (`adr`, `documentation`, `guide`, `reference`, `readme`)
  to improve search-quality across the ecosystem
