---
type: skill
name: memento
description: >-
  Save and restore AIDA session mementos — structured context
  snapshots that persist across /clear and /compact. Use when the
  user runs /aida memento to capture or restore session state. Not
  a general note-taking tool or long-term memory store.
version: 0.1.0
user-invocable: false
tags:
  - core
  - memory
  - context
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Memento

Mementos are persistent context snapshots that help Claude resume work after
`/clear`, `/compact`, or in new conversations. Each memento captures the problem,
approach, progress, and next steps for a work session.

## Activation

This skill activates when:

- User invokes `/aida memento [create|update|read|list|remove|complete]`
- User needs to save or restore session context
- After `/clear` when active mementos exist (for suggestion)

## Command Routing

When this skill activates, parse the command to determine:

1. **Operation**: `create`, `update`, `read`, `list`, `remove`, `complete`
2. **Arguments**: slug, description, source, options

### Create Operations

For `create` operations:

1. Read `references/memento-workflow.md` for the full workflow
2. Run Phase 1 to get questions and inferred data
3. Ask user any required questions using AskUserQuestion
4. Run Phase 2 to create the memento
5. Report success and next steps

**Sources:**

- `manual` (default): User provides description
- `from-pr`: Extract context from current PR
- `from-changes`: Summarize current file changes

**Script invocation:**

```bash
# Phase 1: Get questions
python {base_directory}/scripts/memento.py --get-questions \
  --context='{"operation": "create", "description": "user description", "source": "manual"}'

# Phase 2: Execute
python {base_directory}/scripts/memento.py --execute \
  --context='{"operation": "create", "slug": "my-memento", "description": "...", ...}'
```

### Read Operations

For `read` operations:

1. Load the memento file
2. Return full content to Claude's context
3. Claude can then continue with the restored context

**Script invocation:**

```bash
python {base_directory}/scripts/memento.py --execute \
  --context='{"operation": "read", "slug": "my-memento"}'
```

### List Operations

For `list` operations:

1. Scan `~/.claude/memento/` directory
2. Parse frontmatter for metadata
3. Return formatted list with status, description, dates

**Script invocation:**

```bash
python {base_directory}/scripts/memento.py --execute \
  --context='{"operation": "list", "filter": "active"}'
```

**Filtering options:**

- `--all` - List mementos from all projects
- `--project <name>` - List mementos for a specific project

### Update Operations

For `update` operations:

1. Load current memento
2. Ask which section to update (progress, decisions, next_step)
3. Merge new content with existing
4. Update the `updated` timestamp

**Script invocation:**

```bash
# Phase 1: Get section options
python {base_directory}/scripts/memento.py --get-questions \
  --context='{"operation": "update", "slug": "my-memento"}'

# Phase 2: Execute update
python {base_directory}/scripts/memento.py --execute \
  --context='{"operation": "update", "slug": "my-memento", "section": "progress", "content": "..."}'
```

### Complete Operations

For `complete` operations:

1. Set status to `completed`
2. Move file to `~/.claude/memento/.completed/`
3. Report completion

**Script invocation:**

```bash
python {base_directory}/scripts/memento.py --execute \
  --context='{"operation": "complete", "slug": "my-memento"}'
```

### Remove Operations

For `remove` operations:

1. Confirm deletion with user
2. Delete the memento file
3. Report removal

**Script invocation:**

```bash
python {base_directory}/scripts/memento.py --execute \
  --context='{"operation": "remove", "slug": "my-memento"}'
```

## Path Resolution

**Base Directory:** Provided when skill loads via `<command-message>` tags.

**Script Execution:**

```text
{base_directory}/scripts/memento.py
```

**Reference Files:**

```text
{base_directory}/references/memento-workflow.md
```

**Templates:**

```text
{base_directory}/templates/work-session.md.jinja2
{base_directory}/templates/freeform.md.jinja2
```

**Memento Storage:**

```text
~/.claude/memento/            # Active mementos
~/.claude/memento/.completed/ # Completed mementos
```

## Two-Phase API

This skill uses a two-phase API pattern:

### Phase 1: Get Questions

Analyzes context and returns:

- Inferred metadata (slug, source, tags)
- Questions that need user input
- Validation results

### Phase 2: Execute

Performs the operation with:

- User responses (if any)
- Inferred data
- Configuration options

## Example Workflows

### Creating a Memento

```text
User: /aida memento create "fix auth token expiry"

1. Parse: operation=create, description="fix auth token expiry"
2. Run Phase 1:
   - Infer: slug="fix-auth-token-expiry", source="manual"
   - Question: "What's the core problem you're solving?"
3. User provides problem description
4. Run Phase 2:
   - Create ~/.claude/memento/fix-auth-token-expiry.md
5. Report: "Created memento. Start working, then /aida memento update to track progress"
```

### Loading After /clear

```text
User: /aida memento read fix-auth-token-expiry

1. Parse: operation=read, slug="fix-auth-token-expiry"
2. Load ~/.claude/memento/fix-auth-token-expiry.md
3. Return full content
4. Claude summarizes: "I see you were working on X. Next step was Y. Ready to continue?"
```

### Listing with Filters

```text
/aida memento list --all              # All projects
/aida memento list --project my-proj  # Specific project
```

### Creating from PR

```text
User: /aida memento create from-pr

1. Parse: operation=create, source="from-pr"
2. Detect current branch, fetch PR via `gh pr view`
3. Extract title, body, files changed
4. Pre-fill template with PR context
5. Create memento with PR-derived content
```

## Resources

### scripts/

- **memento.py** - Main management script with two-phase API

### references/

- **memento-workflow.md** - Detailed workflow documentation

### templates/

- **work-session.md.jinja2** - Primary template for task-focused mementos
- **freeform.md.jinja2** - Simple template for custom content
