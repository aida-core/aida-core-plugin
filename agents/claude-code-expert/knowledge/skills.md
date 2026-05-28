---
type: reference
name: skills
title: Claude Code Skills Guide
description: Comprehensive reference for creating and configuring skills in Claude Code
version: "1.0.0"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Claude Code Skills

Skills are **process definitions with execution capabilities** that extend what
Claude can do. A skill is a directory containing a `SKILL.md` file with YAML
frontmatter and markdown instructions. Claude uses skills when relevant to the
conversation, or the user invokes one directly with `/skill-name`.

In the WHO/HOW/CONTEXT framework, skills are the **HOW** -- they define
processes, workflows, and repeatable actions. They complement subagents (WHO)
which provide expertise and judgment, and knowledge (CONTEXT) which provides
reference material.

## Skills and the Agent Skills Open Standard

Claude Code skills follow the [Agent Skills](https://agentskills.io) open
standard, a portable format that works across multiple AI tools including
Claude Code, Cursor, Gemini CLI, VS Code, and others.

The open standard defines the baseline format:

- A directory containing a `SKILL.md` file (required)
- YAML frontmatter with `name` and `description` (required by the standard)
- Markdown body with instructions
- Optional `scripts/`, `references/`, and `assets/` subdirectories

Claude Code **extends** the standard with additional features:

- Invocation control (`disable-model-invocation`, `user-invocable`)
- Subagent execution (`context: fork`, `agent`)
- Dynamic context injection (`!`command`` syntax)
- Tool restrictions (`allowed-tools`)
- Model override (`model`)
- Skill-scoped hooks (`hooks`)

When writing skills intended for cross-tool compatibility, stick to the
standard fields (`name`, `description`, `allowed-tools`, `metadata`). Use
Claude Code extensions when you need Claude-specific behavior.

## Skill File Structure

Each skill is a directory with `SKILL.md` as the entry point:

```text
my-skill/
├── SKILL.md           # Main instructions (required)
├── scripts/           # Executable code Claude can run
│   └── validate.sh
├── references/        # Detailed docs loaded on demand
│   └── REFERENCE.md
├── templates/         # Output templates (Claude Code/AIDA convention)
│   └── output.jinja2
├── assets/            # Static resources (schemas, data)
│   └── schema.json
└── examples/          # Example outputs
    └── sample.md
```

**Note:** The Agent Skills standard defines `scripts/`, `references/`, and
`assets/` as optional subdirectories. The `templates/` and `examples/`
directories are Claude Code/AIDA conventions, not part of the standard.

The `SKILL.md` file has two parts:

1. **YAML frontmatter** (between `---` markers) -- metadata and configuration
2. **Markdown body** -- instructions Claude follows when the skill is active

### SKILL.md Anatomy

```yaml
---
name: fix-issue
description: Fix a GitHub issue by number following team coding standards
argument-hint: "[issue-number]"
disable-model-invocation: true
context: fork
agent: general-purpose
allowed-tools: Read, Grep, Glob, Edit, Write, Bash(gh *)
---

# Fix Issue

Fix GitHub issue $ARGUMENTS following our coding standards.

## Steps

1. Read the issue description with `gh issue view $0`
2. Understand the requirements
3. Implement the fix
4. Write tests
5. Create a commit

## References

For API conventions, see [reference.md](references/reference.md).
```

## Frontmatter Reference

All fields are optional for Claude Code. However, `name` and `description`
are required by the Agent Skills open standard for cross-tool compatibility.
Only `description` is recommended so Claude knows when to use the skill.

### Core Fields

| Field | Type | Default | Description |
| ----- | ---- | ------- | ----------- |
| `name` | string | directory name | Display name and `/slash-command`. Lowercase letters, numbers, hyphens only. Max 64 characters. |
| `description` | string | first paragraph | What the skill does and when to use it. Claude uses this to decide when to load the skill automatically. |
| `argument-hint` | string | none | Hint shown during autocomplete. Example: `[issue-number]` or `[filename] [format]`. |

### Invocation Control

| Field | Type | Default | Description |
| ----- | ---- | ------- | ----------- |
| `disable-model-invocation` | boolean | `false` | When `true`, only the user can invoke this skill via `/name`. Prevents Claude from loading it automatically. Use for workflows with side effects (deploy, commit, send messages). |
| `user-invocable` | boolean | `true` | When `false`, hides the skill from the `/` menu. Only Claude can invoke it. Use for background knowledge that is not a meaningful user action. |

#### Invocation Matrix

| Frontmatter | User can invoke | Claude can invoke | Context loading |
| ----------- | --------------- | ----------------- | --------------- |
| (defaults) | Yes | Yes | Description always in context; full skill loads on invocation |
| `disable-model-invocation: true` | Yes | No | Description NOT in context; loads only when user invokes |
| `user-invocable: false` | No | Yes | Description always in context; loads when Claude invokes |

### Execution Environment

| Field | Type | Default | Description |
| ----- | ---- | ------- | ----------- |
| `allowed-tools` | string (space/comma) | all tools | Tools Claude can use without permission prompts when this skill is active. Example: `Read, Grep, Glob`. |
| `model` | string | session model | Override the model used when this skill is active. Example: `haiku`. |
| `context` | string | none | Set to `fork` to run in a forked subagent context (isolated from conversation history). |
| `agent` | string | `general-purpose` | Which subagent type to use when `context: fork` is set. Options: `Explore`, `Plan`, `general-purpose`, or any custom agent name from `.claude/agents/`. |
| `hooks` | object | none | Hooks scoped to this skill's lifecycle. Same format as hooks in settings.json. |

### Agent Skills Standard Fields

These fields are defined by the Agent Skills open standard and work across
compatible tools:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `name` | string | Required by standard. Same as Claude Code `name`. |
| `description` | string | Required by standard. Same as Claude Code `description`. |
| `license` | string | License name or reference to bundled LICENSE file. |
| `compatibility` | string | Environment requirements (max 500 chars). Example: `Requires git, docker`. |
| `metadata` | map | Arbitrary key-value pairs for additional metadata. |
| `allowed-tools` | string | Space-delimited pre-approved tools. Experimental in standard. |

## Skill Locations and Discovery

Where a skill lives determines who can use it:

### Location Precedence

| Scope | Path | Applies To |
| ----- | ---- | ---------- |
| Enterprise | Managed settings deployment | All users in the organization |
| Personal | `~/.claude/skills/<name>/SKILL.md` | All your projects |
| Project | `.claude/skills/<name>/SKILL.md` | This project only |
| Plugin | `<plugin>/skills/<name>/SKILL.md` | Where plugin is enabled |

When skills share the same name across levels, higher-priority locations win:
**enterprise > personal > project**. Plugin skills use a `plugin-name:skill-name`
namespace, so they cannot conflict with other levels.

### Backward Compatibility with Commands

Use `skills/` for new development; `commands/` is maintained for backward
compatibility. A file at `.claude/commands/review.md` and a skill at
`.claude/skills/review/SKILL.md` both create `/review`. If both exist, the
skill takes precedence. Commands support the same frontmatter fields as skills.

### Nested Directory Discovery

When working with files in subdirectories, Claude Code automatically discovers
skills from nested `.claude/skills/` directories. For example, editing a file
in `packages/frontend/` causes Claude Code to also look in
`packages/frontend/.claude/skills/`. This supports monorepo setups where
packages have their own skills.

### Additional Directories

Skills in `.claude/skills/` within directories added via `--add-dir` are loaded
automatically and support live change detection -- edit them during a session
without restarting.

### Context Budget

Skill descriptions are loaded into context so Claude knows what is available.
If you have many skills, they may exceed the character budget. The budget
scales dynamically at **2% of the context window**, with a fallback of
**16,000 characters**.

Run `/context` to check for warnings about excluded skills.

To override the budget, set the `SLASH_COMMAND_TOOL_CHAR_BUDGET` environment
variable:

```bash
export SLASH_COMMAND_TOOL_CHAR_BUDGET=32000
```

## String Substitutions

Skills support dynamic value substitution in the markdown body:

| Variable | Description |
| -------- | ----------- |
| `$ARGUMENTS` | All arguments passed when invoking the skill. If not present in content, arguments are appended as `ARGUMENTS: <value>`. |
| `$ARGUMENTS[N]` | Access a specific argument by 0-based index. `$ARGUMENTS[0]` is the first argument. |
| `$N` | Shorthand for `$ARGUMENTS[N]`. `$0` is the first argument, `$1` the second. |
| `${CLAUDE_SESSION_ID}` | The current session ID. Useful for logging or session-specific files. |

### Substitution Examples

```yaml
---
name: migrate-component
description: Migrate a component between frameworks
---

Migrate the $0 component from $1 to $2.
Preserve all existing behavior and tests.
```

Invocation: `/migrate-component SearchBar React Vue`

Result: `$0` becomes `SearchBar`, `$1` becomes `React`, `$2` becomes `Vue`.

### Argument Fallback

If a skill does not include `$ARGUMENTS` anywhere in its content but the user
passes arguments, Claude Code appends `ARGUMENTS: <value>` to the end of the
skill content so Claude still sees the input.

## Dynamic Context Injection

The `` !`command` `` syntax runs shell commands **before** the skill content is
sent to Claude. Command output replaces the placeholder inline. This is
preprocessing -- Claude only sees the final rendered result.

```yaml
---
name: pr-summary
description: Summarize changes in a pull request
context: fork
agent: Explore
allowed-tools: Bash(gh *)
---

## Pull request context
- PR diff: !`gh pr diff`
- PR comments: !`gh pr view --comments`
- Changed files: !`gh pr diff --name-only`

## Your task
Summarize this pull request focusing on architectural changes.
```

When this skill runs:

1. Each `` !`command` `` executes immediately (before Claude sees anything)
2. The output replaces the placeholder in the skill content
3. Claude receives the fully rendered prompt with actual data

This is useful for injecting live data (git status, API responses, file
contents) into skill prompts without Claude needing to fetch them.

## Running Skills in a Subagent (context: fork)

Add `context: fork` to run a skill in an isolated subagent context. The skill
content becomes the prompt that drives the subagent. The subagent does **not**
have access to your conversation history.

### When to Use Fork Mode

Use `context: fork` when:

- The skill performs a self-contained task (research, generation, analysis)
- You want to protect the main conversation context from large outputs
- The skill needs a different model or tool set
- The task benefits from a fresh context without conversation noise

Do **not** use `context: fork` for:

- Reference/guideline skills (they need conversation context to apply)
- Skills without explicit task instructions (subagent gets guidelines but
  no actionable prompt)

### Agent Types

The `agent` field specifies which subagent configuration runs the skill:

| Agent | Model | Tools | Use Case |
| ----- | ----- | ----- | -------- |
| `Explore` | Haiku (fast, cheap) | Read-only (Read, Grep, Glob) | Research, codebase exploration |
| `Plan` | Same as session | Planning tools | Architecture, design planning |
| `general-purpose` | Same as session | All tools | Full implementation tasks |
| Custom agent name | Per agent config | Per agent config | Specialized workflows |

Custom agents are defined in `.claude/agents/` or `~/.claude/agents/`. When
`agent` is omitted, defaults to `general-purpose`.

### Fork vs Subagent Preloading

Skills and subagents work together in two directions:

| Approach | System Prompt | Task | Also Loads |
| -------- | ------------- | ---- | ---------- |
| Skill with `context: fork` | From agent type | SKILL.md content | CLAUDE.md |
| Subagent with `skills` field | Subagent's markdown body | Claude's delegation message | Preloaded skills + CLAUDE.md |

With `context: fork`, you write the task in your skill and pick an agent type.
For defining a custom subagent that uses skills as reference material, see
`knowledge/subagents.md`.

## Controlling Skill Access with Permissions

Three mechanisms control which skills Claude can invoke:

### 1. Disable All Skills

Deny the `Skill` tool in `/permissions`:

```text
Skill
```

### 2. Allow or Deny Specific Skills

Use permission rule syntax:

```text
# Allow only specific skills
Skill(commit)
Skill(review-pr *)

# Deny specific skills
Skill(deploy *)
```

Syntax: `Skill(name)` for exact match, `Skill(name *)` for prefix match with
any arguments.

### 3. Frontmatter Controls

- `disable-model-invocation: true` removes the skill from Claude's context
  entirely (Claude cannot trigger it)
- `user-invocable: false` hides from the `/` menu (users cannot trigger it)

Note: `user-invocable` only controls menu visibility, not Skill tool access.
Use `disable-model-invocation: true` to block programmatic invocation.

## Skills vs Other Extension Types

| Aspect | Skills (HOW) | Subagents (WHO) | Knowledge (CONTEXT) | Hooks (AUTOMATION) |
| ------ | ------------ | --------------- | ------------------- | ------------------ |
| **Purpose** | Process definitions, workflows | Expert personas, judgment | Reference material | Lifecycle-bound execution |
| **Trigger** | User invocation or Claude auto-load | Task delegation | On-demand loading | Automatic (lifecycle events) |
| **Control** | LLM-guided | LLM-guided | Passive (read-only) | Deterministic (command type) |
| **Entry point** | `SKILL.md` | `agent-name.md` | `knowledge/*.md` | `settings.json` / `hooks.json` / frontmatter |
| **Location** | `skills/<name>/` | `agents/<name>/` | `knowledge/` subdirs | JSON configuration |
| **Invocation** | `/skill-name` | `Task(agent)` delegation | Referenced from skills/agents | Event-triggered |

### When to Use Each Type

- **Use a Skill** when you need a repeatable process with defined steps
  (commit workflow, deployment, code generation)
- **Use a Subagent** when you need domain expertise and judgment
  (code review expert, architecture advisor)
- **Use Knowledge** when you need reference material that skills and agents
  consult (API docs, style guides, conventions)
- **Use a Hook** when something MUST happen at a lifecycle event (formatting,
  logging, blocking dangerous operations)

## Types of Skill Content

### Reference Skills

Add knowledge Claude applies to current work. Conventions, patterns, style
guides. Runs inline alongside conversation context.

```yaml
---
name: api-conventions
description: API design patterns for this codebase
---

When writing API endpoints:
- Use RESTful naming conventions
- Return consistent error formats
- Include request validation
```

### Task Skills

Step-by-step instructions for a specific action. Often invoked directly with
`/skill-name`. Add `disable-model-invocation: true` for actions with side
effects.

```yaml
---
name: deploy
description: Deploy the application to production
context: fork
disable-model-invocation: true
---

Deploy the application:
1. Run the test suite
2. Build the application
3. Push to the deployment target
```

## Supporting Files

Keep `SKILL.md` under 500 lines. Move detailed reference material to separate
files that Claude loads on demand.

```text
my-skill/
├── SKILL.md           # Overview and navigation (required)
├── references/        # Detailed docs loaded when needed
│   └── api-spec.md
├── examples/          # Example outputs
│   └── sample.md
├── templates/         # Templates Claude fills in
│   └── output.jinja2
└── scripts/           # Scripts Claude can execute
    └── validate.py
```

Reference supporting files from `SKILL.md` so Claude knows what each contains
and when to load it:

```markdown
## Additional resources

- For complete API details, see [api-spec.md](references/api-spec.md)
- For usage examples, see [examples/sample.md](examples/sample.md)
```

## Progressive Disclosure Model

Skills use progressive disclosure to manage context efficiently:

1. **Discovery** (~100 tokens): The `name` and `description` are loaded at
   startup for all skills (unless `disable-model-invocation: true`)
2. **Activation** (< 5000 tokens recommended): The full `SKILL.md` body loads
   when the skill is invoked
3. **Resources** (as needed): Supporting files in `scripts/`, `references/`,
   `assets/` are loaded only when required during execution

This three-tier model keeps Claude fast while giving access to deep context
on demand.

## Common Patterns

### Read-Only Research

```yaml
---
name: deep-research
description: Research a topic thoroughly in the codebase
context: fork
agent: Explore
---

Research $ARGUMENTS thoroughly:
1. Find relevant files using Glob and Grep
2. Read and analyze the code
3. Summarize findings with specific file references
```

### Script-Backed Skill

Frontmatter:

```yaml
---
name: codebase-visualizer
description: Generate an interactive HTML tree of project structure
allowed-tools: Bash(python *)
---
```

Body instructs Claude to run a bundled script:

```text
Run the visualization script from the project root:
  python ~/.claude/skills/codebase-visualizer/scripts/visualize.py .
This generates codebase-map.html and opens it in the browser.
```

### Session Logging

```yaml
---
name: session-logger
description: Log activity for this session
---

Log the following to logs/${CLAUDE_SESSION_ID}.log:

$ARGUMENTS
```

### Restricted Tool Access

```yaml
---
name: safe-reader
description: Read files without making changes
allowed-tools: Read, Grep, Glob
---

Explore the codebase in read-only mode. Report findings without
modifying any files.
```

## Best Practices

> **See also:** `skill-authoring-patterns.md` for deeper authoring
> patterns — gotchas sections, calibrated control, defaults vs.
> menus, plan-validate-execute, output templates, validation
> loops. And `skill-iteration.md` for the iteration loop that
> takes a skill from "works once" to "works reliably".

### Naming

- Use lowercase kebab-case: `fix-issue`, `deploy-staging`
- Be specific: `react-component-gen` not `generate`
- Match the directory name to the `name` field
- Max 64 characters

### Descriptions

- Include keywords users would naturally say
- Describe both WHAT the skill does and WHEN to use it
- Be specific enough that Claude can match requests accurately
- Keep under 1024 characters

### Content

- Keep `SKILL.md` under 500 lines
- Move detailed references to supporting files
- Include step-by-step instructions for task skills
- Use string substitutions for dynamic values
- Include the word "ultrathink" in skill content to enable extended thinking,
  which gives Claude a longer internal reasoning budget for complex tasks

### Invocation Control

- Use `disable-model-invocation: true` for side-effect actions (deploy,
  commit, send messages)
- Use `user-invocable: false` for background knowledge
- Default (both true) for general-purpose skills

### Fork Mode

- Always pair `context: fork` with explicit task instructions
- Choose `agent: Explore` for read-only research (cheaper, faster)
- Choose `agent: general-purpose` for tasks needing write access
- Use custom agents for specialized tool/permission requirements

### Distribution

- **Project skills**: Commit `.claude/skills/` to version control
- **Personal skills**: Store in `~/.claude/skills/` for cross-project use
- **Plugin skills**: Package in a plugin's `skills/` directory
- **Enterprise skills**: Deploy via managed settings

## Sharing Skills

Skills can be distributed at different scopes:

| Scope | Method | Audience |
| ----- | ------ | -------- |
| Project | Commit `.claude/skills/` to repo | Project contributors |
| Plugin | Include in plugin `skills/` dir | Plugin users |
| Enterprise | Deploy via managed settings | Organization members |
| Open standard | Publish as Agent Skills package | Cross-tool users |

## Troubleshooting

### Skill Not Triggering

1. Check the description includes keywords users would naturally say
2. Verify the skill appears in `What skills are available?`
3. Try rephrasing to match the description more closely
4. Invoke directly with `/skill-name` if user-invocable

### Skill Triggers Too Often

1. Make the description more specific and narrow
2. Add `disable-model-invocation: true` for manual-only invocation

### Claude Does Not See All Skills

Skills may exceed the context budget. The budget is 2% of the context window
(fallback: 16,000 characters). Run `/context` to check for warnings.
Override with `SLASH_COMMAND_TOOL_CHAR_BUDGET` environment variable.

### Fork Mode Skill Returns Empty

The skill likely contains guidelines without an actionable task. When using
`context: fork`, the skill content becomes the subagent's prompt. Include
explicit instructions for what the subagent should do.
