---
type: skill
name: agent-manager
title: Agent Manager
description: >-
  Create, validate, version, and list AIDA-managed Claude Code
  subagent definition files (two-phase API). Use for CRUD on agent
  .md definitions, routed through /aida extension management. Do
  NOT use to run, dispatch, or consult a subagent — this only
  authors and maintains the definition files.
version: 0.1.0
user-invocable: false
tags:
  - core
  - management
  - agents
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Agent Manager

Focused management interface for Claude Code agent (subagent)
definitions. Handles the full lifecycle of agent `.md` files
and their `knowledge/` directories.

## Activation

This skill activates when:

- User invokes `/aida agent [create|validate|version|list]`
- Agent management is needed

## Operations

### Command Routing

Parse the command to determine:

1. **Operation**: `create`, `validate`, `version`, `list`
2. **Arguments**: name, description, options

The component type is always `agent` -- no type selection
is needed.

### Create Operations

For `create` operations, use the **three-phase orchestration
pattern**:

#### Phase 1: Gather Context (Python)

Run the script to infer metadata and get questions:

```bash
python {base_directory}/scripts/manage.py \
  --get-questions \
  --context='{"operation": "create", "description": "user description", "location": "user"}'
```

Returns:

```json
{
  "inferred": {
    "name": "inferred-name",
    "version": "0.1.0",
    "tags": ["custom"],
    "base_path": "~/.claude/agents/inferred-name"
  },
  "questions": [],
  "project_context": {
    "languages": ["python"],
    "frameworks": ["fastapi"]
  }
}
```

#### Phase 2: Generate Content (Agent)

Spawn the `claude-code-expert` agent with complete context
and output contract:

```text
Operation: CREATE
Type: agent

Requirements:
  - Name: {inferred.name}
  - Description: {user_description}
  - Location: {inferred.base_path}
  - Project Context: {project_context}
  - User Answers: {answers to questions}

Output Format:
Return a JSON object with this exact structure:

{
  "validation": {
    "passed": true|false,
    "issues": [
      {
        "severity": "error|warning",
        "message": "description",
        "suggestion": "how to fix"
      }
    ]
  },
  "files": [
    {
      "path": "agents/{name}/{name}.md",
      "content": "..."
    },
    {
      "path": "agents/{name}/knowledge/index.md",
      "content": "..."
    }
  ],
  "summary": {
    "created": ["list of relative paths"],
    "next_steps": ["actionable items for user"]
  }
}
```

**Handle agent response:**

1. Parse the JSON response
2. If `validation.passed` is false with errors:
   - Report issues to user
   - Ask if they want to proceed or provide more info
3. If validation passed (or user chose to proceed):
   - Continue to Phase 3

#### Phase 3: Write Files (Python)

Pass agent output to Python for file creation:

```bash
python {base_directory}/scripts/manage.py \
  --execute \
  --context='{"operation": "create", "agent_output": <agent_json>}'
```

The script:

1. Validates file structure (required fields, frontmatter)
2. Creates directories (including `knowledge/`)
3. Writes files
4. Returns success/failure

### Validate Operations

For `validate` operations:

1. Run validation script
2. Report results with any errors

**Script invocation:**

```bash
# Validate specific agent
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "validate", "name": "my-agent"}'

# Validate all agents
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "validate", "all": true, "location": "all"}'
```

### Version Operations

For `version` operations:

1. Find the agent
2. Bump version (major, minor, or patch)
3. Update the file
4. Report the version change

**Script invocation:**

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "version", "name": "my-agent", "bump": "patch"}'
```

### List Operations

For `list` operations:

1. Search specified locations
2. Parse agent metadata from frontmatter
3. Return formatted list

**Script invocation:**

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "list", "location": "all", "format": "table"}'
```

## Path Resolution

**Base Directory:** Provided when skill loads via
`<command-message>` tags.

**Script Execution:**

```text
{base_directory}/scripts/manage.py
```

**Reference Files:**

```text
{base_directory}/references/create-workflow.md
{base_directory}/references/validate-workflow.md
{base_directory}/references/schemas.md
```

## Location Options

| Location  | Path         | Use Case                |
| --------- | ------------ | ----------------------- |
| `user`    | `~/.claude/` | Personal agents         |
| `project` | `./.claude/` | Project-specific agents |
| `plugin`  | Custom path  | Plugin development      |

## Example Workflow

### Creating an Agent (Full Flow)

```text
User: /aida agent create "handles database migrations"

1. Parse: operation=create, description="handles database migrations"

2. Phase 1 (Python):
   python manage.py --get-questions --context='{...}'
   Returns:
   - inferred: name="database-migration", version="0.1.0"
   - questions: [location question]
   - project_context: {languages: ["python"]}

3. Ask user questions (if any):
   "Where should we create this agent?"

4. Phase 2 (Agent):
   Spawn claude-code-expert with context + output contract
   Agent returns JSON with files array

5. Phase 3 (Python):
   python manage.py --execute --context='{"operation": "create", "agent_output": {...}}'
   - Validates structure
   - Creates directories + knowledge/
   - Writes files

6. Report to user:
   "Created agent 'database-migration' with 3 files"
```

## Resources

### scripts/

- **manage.py** - Entry point for two-phase API
- **operations/** - Operation modules
  - **utils.py** - Shared utilities (re-export shim)
  - **extensions.py** - Agent operations

### references/

- **create-workflow.md** - Agent creation workflow
- **validate-workflow.md** - Agent validation rules
- **schemas.md** - Agent frontmatter schema
