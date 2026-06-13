---
type: skill
name: hook-manager
title: Hook Manager
description: >-
  List, add, remove, and validate Claude Code lifecycle hook
  entries in settings.json, routed through /aida extension
  management. Use for structured CRUD on the hooks block. For
  general settings.json edits or other harness behavior changes,
  use the native settings/config flow instead.
version: 0.1.0
user-invocable: false
tags:
  - core
  - hooks
  - configuration
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Hook Manager

Manages Claude Code lifecycle hook configurations.
Hooks are shell commands that execute automatically at
specific points in the Claude Code lifecycle, providing
deterministic control over formatting, logging, blocking,
and notifications.

## Activation

This skill activates when:

- User invokes `/aida hook list`
- User invokes `/aida hook add`
- User invokes `/aida hook remove`
- User invokes `/aida hook validate`
- Hook management is needed

## Operations

### List Hooks

Show all configured hooks across settings files.

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "list", "scope": "all"}'
```

**Scopes:**

- `user` -- User-level hooks only
- `project` -- Project-level hooks only
- `local` -- Local overrides only
- `all` -- All hooks (default)

### Add Hook

Add a new hook using the two-phase API.

#### Phase 1: Gather Context

```bash
python {base_directory}/scripts/manage.py \
  --get-questions \
  --context='{"operation": "add", "description": "..."}'
```

Returns questions about event type, scope, and whether
to use a built-in template.

#### Phase 2: Execute

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "add", "event": "PostToolUse", "matcher": "Write|Edit", "command": "prettier --write", "scope": "project"}'
```

**Built-in templates:**

| Template | Event | Purpose |
| --- | --- | --- |
| `formatter` | PostToolUse | Auto-format after writes |
| `logger` | PostToolUse | Log commands for audit |
| `blocker` | PreToolUse | Block sensitive file writes |
| `notifier` | Notification | Desktop notifications |

### Remove Hook

Remove a hook by event and matcher.

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "remove", "event": "PostToolUse", "matcher": "Write|Edit", "scope": "project"}'
```

### Validate Hooks

Validate hook configurations for correctness.

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "validate", "scope": "all"}'
```

Checks:

- Hook structure (required fields)
- Event names are valid
- Commands are safe (warns about dangerous patterns)

## Two-Phase API

### Phase 1: `get_questions(context)`

Analyzes the operation context and returns:

- **questions**: List of questions needing user input
- **inferred**: Values inferred from the description

### Phase 2: `execute(context, responses)`

Executes the operation with user responses and returns:

- **success**: Whether the operation succeeded
- **message**: Human-readable result message
- Operation-specific data (hooks list, added hook, etc.)

## Hook Configuration Locations

| Scope | Path | Use Case |
| --- | --- | --- |
| `user` | `~/.claude/settings.json` | Personal hooks |
| `project` | `.claude/settings.json` | Shared team hooks |
| `local` | `.claude/settings.local.json` | Local overrides |

## Path Resolution

**Script entry point:**

```text
{base_directory}/scripts/manage.py
```

**Reference docs:**

```text
{base_directory}/references/hooks-reference.md
```

## Resources

### Scripts

| Script | Purpose |
| --- | --- |
| `scripts/manage.py` | Two-phase API entry point |
| `scripts/_paths.py` | Path setup for shared utils |
| `scripts/operations/hooks.py` | Hook operations |
