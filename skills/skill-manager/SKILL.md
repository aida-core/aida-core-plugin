---
type: skill
name: skill-manager
title: Skill Manager
description: >-
  Create, validate, version, and list Claude Code skill definition
  files following the Agent Skills open standard (two-phase API).
  Use for CRUD on skill files, routed through /aida extension
  management. Do NOT use to execute a skill's behavior — this only
  authors and maintains skill definitions.
version: 0.1.0
user-invocable: false
tags:
  - core
  - management
  - skills
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Skill Manager

Focused management interface for Claude Code skill definitions.
Skills are process definitions with execution capabilities that follow
the [Agent Skills open standard](https://agentskills.io).

## Activation

This skill activates when:

- User invokes `/aida skill create [description]`
- User invokes `/aida skill validate [name|--all]`
- User invokes `/aida skill version [name] [major|minor|patch]`
- User invokes `/aida skill list`
- Skill management operations are needed

## Operations

### Create

Create a new skill definition using the three-phase orchestration
pattern.

#### Phase 1: Gather Context (Python)

Run the script to infer metadata and get questions:

```bash
python {base_directory}/scripts/manage.py --get-questions \
  --context='{"operation": "create", "description": "user description", "location": "user"}'
```

Returns:

```json
{
  "inferred": {
    "name": "inferred-name",
    "version": "0.1.0",
    "tags": ["custom"],
    "base_path": "~/.claude/skills/inferred-name"
  },
  "questions": [],
  "project_context": {
    "languages": ["python"],
    "frameworks": ["fastapi"]
  }
}
```

#### Phase 2: Generate Content (Agent)

Spawn the `claude-code-expert` agent with complete context:

```text
Operation: CREATE
Type: skill

Requirements:
  - Name: {inferred.name}
  - Description: {user_description}
  - Location: {inferred.base_path}
  - Project Context: {project_context}

Output Format:
Return a JSON object with this exact structure:

{
  "validation": {
    "passed": true|false,
    "issues": [
      {"severity": "error|warning", "message": "...", "suggestion": "..."}
    ]
  },
  "files": [
    {"path": "skills/{name}/SKILL.md", "content": "..."},
    {"path": "skills/{name}/scripts/{script}.py", "content": "..."},
    {"path": "skills/{name}/references/{doc}.md", "content": "..."},
    {"path": "skills/{name}/templates/{tmpl}.jinja2", "content": "..."}
  ],
  "summary": {
    "created": ["list of relative paths"],
    "next_steps": ["actionable items for user"]
  }
}
```

#### Phase 3: Write Files (Python)

Pass agent output to Python for file creation:

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "create", "agent_output": <agent_json>, "base_path": "~/.claude"}'
```

The script validates file structure, creates directories, writes
files, and returns success or failure.

### Validate

Validate skill frontmatter against the schema.

```bash
# Validate specific skill
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "validate", "name": "my-skill"}'

# Validate all skills
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "validate", "all": true, "location": "all"}'
```

### Version

Bump a skill's semantic version.

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "version", "name": "my-skill", "bump": "patch"}'
```

### List

List all discovered skills.

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "list", "location": "all"}'
```

## Skill Directory Structure

Skills follow the Agent Skills open standard directory layout:

```text
skills/
  my-skill/
    SKILL.md        # Skill definition (frontmatter + instructions)
    references/     # Workflow documentation
      workflow.md
    scripts/        # Executable scripts
      manage.py
    templates/      # Optional Jinja2 templates
      template.jinja2
```

## Path Resolution

**Base Directory:** Provided when skill loads via `<command-message>`
tags.

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

| Location  | Path         | Use Case                    |
| --------- | ------------ | --------------------------- |
| `user`    | `~/.claude/` | Personal skills             |
| `project` | `./.claude/` | Project-specific skills     |
| `plugin`  | Custom path  | Plugin development          |

## Example Workflow

### Creating a Skill (Full Flow)

```text
User: /aida skill create "auto-format code on save"

1. Parse: operation=create, description="auto-format code on save"

2. Phase 1 (Python):
   python manage.py --get-questions --context='{...}'
   Returns:
   - inferred: name="auto-format", version="0.1.0"
   - questions: [location question]
   - project_context: {languages: ["python"]}

3. Ask user questions (if any):
   "Where should we create this skill?"

4. Phase 2 (Agent):
   Spawn claude-code-expert with context + output contract
   Agent returns JSON with files array

5. Phase 3 (Python):
   python manage.py --execute --context='{"operation": "create", "agent_output": {...}}'
   - Validates structure
   - Creates directories + scripts/, references/, templates/
   - Writes SKILL.md and supporting files

6. Report to user:
   "Created skill 'auto-format' with 4 files"
```

## Resources

### scripts/

- **manage.py** - Two-phase API entry point
- **operations/extensions.py** - Skill CRUD operations
- **operations/utils.py** - Shared utility re-exports

### references/

- **create-workflow.md** - Skill creation workflow
- **validate-workflow.md** - Skill validation rules
- **schemas.md** - Skill frontmatter schema reference
