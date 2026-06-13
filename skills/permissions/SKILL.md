---
type: skill
name: permissions
description: >-
  Set up Claude Code permission rules from AIDA plugin
  recommendations. Scans installed plugins' recommendedPermissions
  and writes categorized allow/ask/deny rules to settings.json. Use
  ONLY when the user runs /aida config permissions (setup or
  --audit). Do NOT use for ad-hoc permission edits, allowing or
  denying a single tool, or the built-in /permissions command —
  those are handled natively by Claude Code, not by AIDA.
version: 0.1.0
user-invocable: false
tags:
  - core
  - permissions
  - configuration
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Permissions Skill

Manages Claude Code permissions interactively by scanning installed
plugin recommendations, presenting categorized choices, and writing
the selected configuration to `settings.json`.

## Activation

This skill activates when `/aida config permissions` is invoked
through the aida skill routing system.

## Command Routing

| Command | Description |
| --- | --- |
| `/aida config permissions` | Interactive permissions setup |
| `/aida config permissions --audit` | Audit current permissions |

## Path Resolution

Scripts are located at `skills/permissions/scripts/` relative to
the plugin root.

- Plugin cache: `~/.claude/plugins/cache/*/*/.claude-plugin/`
- User settings: `~/.claude/settings.json`
- Project settings: `.claude/settings.json`
- Local settings: `.claude/settings.local.json`

## Two-Phase API

### Phase 1: `get_questions(context)`

1. Scans installed plugins for `recommendedPermissions` in
   `aida-config.json`
2. Deduplicates and categorizes discovered rules
3. Reads current permissions from all settings scopes
4. Detects conflicts between current and proposed rules
5. Returns questions for preset selection and per-category
   allow/ask/deny choices

### Phase 2: `execute(context, responses)`

1. Applies the selected preset or custom category choices
2. Builds the final rules dictionary (allow/ask/deny lists)
3. Writes permissions to the chosen settings scope
4. Returns a summary of changes made

### Audit Mode

When `--audit` is passed, the skill skips the interactive flow
and returns a coverage/gap/conflict analysis report.

## Resources

### Scripts

| Script | Purpose |
| --- | --- |
| `scripts/permissions.py` | Two-phase API entry point |
| `scripts/scanner.py` | Plugin permission discovery |
| `scripts/aggregator.py` | Deduplication and categorization |
| `scripts/settings_manager.py` | Settings.json read/write |

### References

| Document | Purpose |
| --- | --- |
| `references/permissions-workflow.md` | End-to-end workflow guide |
| `references/rule-syntax.md` | Permission rule format docs |
| `references/presets.md` | Preset definitions and mappings |
