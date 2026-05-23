---
type: reference
title: "Validate Action"
description: "Handles /aida config validate — non-interactive health check for AIDA configuration."
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Validate Action

Handles `/aida config validate` — a **non-interactive** check that
the project's AIDA configuration is coherent. Designed for CI gates
and post-version-bump sanity checks.

## Quick start

Just run the script and surface its output:

```bash
~/.aida/venv/bin/python3 {base_directory}/scripts/validate.py
```

For machine-consumable output (CI):

```bash
~/.aida/venv/bin/python3 {base_directory}/scripts/validate.py --json
```

The script exits **0 on success, 1 on failure** — suitable for
`make`, GitHub Actions, and any other tool that checks exit codes.

## What it checks

1. **Global install marker** — `~/.claude/aida.yml` exists. Without
   it, no project-level configuration makes sense.
2. **Project marker** — `.claude/aida.yml` exists, parses as YAML,
   has `version` and a `project` mapping.
3. **Project context** — `.claude/aida-project-context.yml`
   (committed) and `.claude/aida-project-context.local.yml`
   (gitignored overlay if present) both parse. The merged context
   has the expected top-level keys (`version`, `project_name`,
   `vcs`, `files`, `languages`, `tools`, `inferred`, `preferences`)
   and the sub-mappings are dicts (not strings or lists from a bad
   edit).

The validator uses the same `load_project_context()` loader that
the rest of AIDA reads through, so it can't disagree with what
consumers actually see.

## When to use it

- **After bumping aida-core** — does the existing project config
  still validate against the (potentially updated) shape?
- **In CI** — gate PRs that touch `.claude/aida-project-context.yml`
  on it passing
- **After manual edits** — quick sanity check before committing

## What it does NOT check (yet)

- Drift between the YAML and the rendered
  `.claude/skills/project-context/SKILL.md` — that's a future
  follow-up
- Schema-version migration — tracked in #39

## Output

Human-readable (default):

```text
AIDA Configuration Validation
============================================================
Project: /path/to/project

✓ Global Install
✓ Project Marker
✓ Project Context

✓ Configuration is valid.
```

JSON (`--json`):

```json
{
  "valid": true,
  "errors": [],
  "checks": {
    "global_install": { "pass": true, "errors": [] },
    "project_marker": { "pass": true, "errors": [] },
    "project_context": { "pass": true, "errors": [] }
  },
  "project_root": "/path/to/project"
}
```

## Error handling

The script never raises — every failure mode (missing file, bad
YAML, wrong shape) becomes a string in the `errors` array. CI
should branch on the exit code, not stderr.

## Related

- #39 — schema-version migration (future work; this validator
  doesn't migrate, it only reports)
- #87 — this issue
