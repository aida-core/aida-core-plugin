---
type: skill
name: expert-registry
description: >-
  Manage expert agent activation and panel composition for
  project and global scopes. Provides list, configure, and
  panel operations for expert-based workflows like code review
  and plan grading.
version: 0.1.0
user-invocable: true
argument-hint: "[list|list configure|panel list|panel create|panel remove]"
tags:
  - core
  - management
  - experts
  - panels
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Expert Registry

> ⚠ **Deprecated in aida-core (1.x): moving to a dedicated
> `aida-expert-plugin`.** This skill is an orchestration layer
> (panel composition + activation policy) on top of agents,
> which doesn't fit aida-core's scope of extension primitives.
> See [ADR-012](../../docs/architecture/adr/012-split-expert-registry.md)
> for the rationale and migration plan. The skill keeps working
> in 1.x — only the *future home* is changing. At 2.0.0 it will
> be removed from aida-core; install `aida-expert-plugin` from
> the marketplace to keep `/aida expert ...` working.
>
> No action needed today. Watch the release notes for the
> migration steps when the new plugin is published.

Manages expert agent activation and named panel composition.
Experts are regular agents whose frontmatter declares
`role: expert` (plus an optional `expert-role` sub-role).
The registry tracks which experts are active and groups them
into reusable named panels for structured workflows.

## Activation

This skill activates when:

- User invokes `/aida expert list`
- User invokes `/aida expert list configure`
- User invokes `/aida expert panel list`
- User invokes `/aida expert panel create <name>`
- User invokes `/aida expert panel remove <name>`
- Expert activation or panel management is needed

## Operations

### List Experts

Show all known expert agents and their activation status.

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "list"}'
```

Returns each expert with:

- `name` -- agent name from frontmatter
- `active` -- whether the expert is currently activated
- `expert-role` -- sub-role (`core`, `domain`, or `qa`)
- `source` -- config origin (`merged`, `project`, `global`,
  or `null`)

### Configure Expert List

Interactively select which experts are active and choose
a save target (project or global scope).

Uses the two-phase API.

#### Phase 1: Gather Context

```bash
python {base_directory}/scripts/manage.py \
  --get-questions \
  --context='{"operation": "list-configure"}'
```

Returns:

```json
{
  "inferred": {
    "current_active": ["reviewer-agent"],
    "source": "project"
  },
  "questions": [
    {
      "id": "active",
      "type": "multi-select",
      "prompt": "Which experts should be active?",
      "choices": ["<dynamic list of available experts>"],
      "current": ["reviewer-agent"]
    },
    {
      "id": "config_path",
      "type": "choice",
      "prompt": "Save to project or global config?",
      "choices": ["project", "global"],
      "default": "project"
    }
  ]
}
```

#### Phase 2: Execute

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "list-configure"}' \
  --responses='{"active": ["reviewer-agent"], "config_path": "project"}'
```

Writes the `experts.active` list to the chosen config file.
Existing keys in the file are preserved.

### List Panels

Show all named panel compositions from the active config.

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "panels"}'
```

Returns each panel with:

- `name` -- panel identifier
- `members` -- list of expert names in the panel
- `stale` -- members listed but not currently active

### Panel Create

Create a new named panel or replace an existing one.

Uses the two-phase API.

#### Phase 1: Gather Context

```bash
python {base_directory}/scripts/manage.py \
  --get-questions \
  --context='{"operation": "panel-create", "panel_name": "review"}'
```

Returns the current active experts as choices plus the
current panel membership if the panel already exists.

#### Phase 2: Execute

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "panel-create", "panel_name": "review"}' \
  --responses='{"members": ["reviewer-agent", "qa-agent"]}'
```

Adds or replaces the named panel in the project config.
Panels are project-scope only (never written to global
config).

### Panel Remove

Remove a named panel from the project config.

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "panel-remove", "panel_name": "review"}'
```

Removes the key from `experts.panels` and writes the file
atomically. No-ops gracefully if the panel does not exist.

## Path Resolution

**Base Directory:** Provided when skill loads via
`<command-message>` tags.

**Script Execution:**

```text
{base_directory}/scripts/manage.py
```

**Reference Files:**

```text
{base_directory}/references/schemas.md
```

**Template Files:**

```text
{base_directory}/templates/questionnaires/configure.yml
```

## Config File Locations

| Scope     | Path                                | Panels |
| --------- | ----------------------------------- | ------ |
| `project` | `.claude/aida-project-context.yml`  | Yes    |
| `global`  | `~/.claude/aida.yml`                | No     |

Global and project configs are merged (union). Project
`active: []` is an intentional opt-out that suppresses the
global list. When only one layer has `experts.active`, that
layer is used alone.

## Example Workflow

### Activating Experts (Full Flow)

```text
User: /aida expert list configure

1. Parse: operation=list-configure

2. Phase 1 (Python):
   python manage.py --get-questions \
     --context='{"operation": "list-configure"}'
   Returns:
   - inferred: current_active=["reviewer-agent"], source="project"
   - questions: [active, config_path]

3. Present choices to user and collect answers

4. Phase 2 (Python):
   python manage.py --execute \
     --context='{"operation": "list-configure"}' \
     --responses='{"active": ["reviewer-agent", "qa-agent"],
                   "config_path": "project"}'
   - Writes experts.active to .claude/aida-project-context.yml
   - Preserves other keys in the file

5. Report to user:
   "Activated 2 experts in project config."
```

## Resources

### scripts/

- **manage.py** -- Entry point for two-phase API
- **expert_ops/**
  - **registry.py** -- Config I/O, active-expert resolution
  - **panels.py** -- Panel resolution and role filtering

### references/

- **schemas.md** -- Config file and frontmatter schemas

### templates/questionnaires/

- **configure.yml** -- Question template for configure flow
