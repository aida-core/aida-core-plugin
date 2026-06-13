---
type: skill
name: claude-md-manager
title: CLAUDE.md Manager
description: >-
  Create, optimize, validate, and list CLAUDE.md memory files
  across project, user, and plugin scopes (two-phase API), routed
  through /aida. Use for structured CLAUDE.md management. Do NOT
  use for a one-off manual edit to a single CLAUDE.md — edit that
  file directly.
version: 0.1.0
user-invocable: false
tags:
  - core
  - configuration
  - claude-md
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# CLAUDE.md Manager

Manages CLAUDE.md configuration files that provide
project-specific guidance to Claude Code. Supports the full
CLAUDE.md hierarchy: project, user, and plugin scopes.

## Activation

This skill activates when:

- User invokes `/aida claude create`
- User invokes `/aida claude optimize`
- User invokes `/aida claude validate`
- User invokes `/aida claude list`
- CLAUDE.md management is needed

## Operations

### Create

Generate a new CLAUDE.md file at the specified scope. Detects
project context (languages, tools, commands) and renders from
templates.

### Optimize

Audit an existing CLAUDE.md against best practices, generate
findings with fix suggestions, and optionally apply fixes.
Reports a quality score (0-100).

### Validate

Run validation checks on existing CLAUDE.md files: structure,
consistency, best practices, and alignment with detected project
facts. Returns results without modifications.

### List

Find all CLAUDE.md files in the hierarchy and report their
validation status.

## Two-Phase API

All operations follow the two-phase pattern:

### Phase 1: Get Questions

Analyze context and return questions that need user input.

```bash
python {base_directory}/scripts/manage.py --get-questions \
  --context='{"operation": "create", "scope": "project"}'
```

Returns:

```json
{
  "questions": [],
  "inferred": {
    "name": "my-project",
    "languages": ["Python"],
    "tools": ["Git", "pytest"],
    "commands": [{"command": "make test", "description": "Run tests"}]
  },
  "existing": null
}
```

### Phase 2: Execute

Execute the operation with provided context and responses.

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "create", "scope": "project"}' \
  --responses='{"name": "my-project"}'
```

Returns:

```json
{
  "success": true,
  "message": "Created CLAUDE.md at ./CLAUDE.md",
  "path": "./CLAUDE.md"
}
```

## CLAUDE.md Scopes

| Scope | Path | Use Case |
| --- | --- | --- |
| `project` | `./CLAUDE.md` | Project documentation |
| `user` | `~/.claude/CLAUDE.md` | Global user preferences |
| `plugin` | `.claude-plugin/CLAUDE.md` | Plugin documentation |

## Path Resolution

**Base Directory:** Provided when skill loads via
`<command-message>` tags.

**Script Execution:**

```text
{base_directory}/scripts/manage.py
```

## Resources

### Scripts

| Script | Purpose |
| --- | --- |
| `scripts/manage.py` | Two-phase API entry point |
| `scripts/operations/claude_md.py` | Core CLAUDE.md operations |
| `scripts/operations/utils.py` | Shared utility re-exports |

### References

| Document | Purpose |
| --- | --- |
| `references/claude-md-workflow.md` | End-to-end workflow guide |
| `references/best-practices.md` | Best practices and scoring |

### Templates

| Template | Purpose |
| --- | --- |
| `templates/claude-md/project.md.jinja2` | Project-scope template |
| `templates/claude-md/user.md.jinja2` | User-scope template |
| `templates/claude-md/plugin.md.jinja2` | Plugin-scope template |
