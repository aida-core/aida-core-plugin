---
type: skill
name: aida
description: This skill routes /aida commands to appropriate handlers - configuration,
  diagnostics, feedback, extension management (agent-manager, skill-manager,
  plugin-manager, hook-manager, claude-md-manager, permissions), expert and
  panel configuration (expert-registry), agent knowledge management
  (knowledge-sync, knowledge-curator), and session persistence (memento). This
  is the single entry point for all AIDA operations - the sub-skills are not
  directly invocable.
version: 0.9.0
tags:
  - core
user-invocable: true
allowed-tools: "*"
argument-hint: "[command] [subcommand] [options]"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# AIDA Dispatch

Routes `/aida` commands to appropriate action handlers, managing AIDA's configuration,
diagnostics, feedback systems, and extension management (agents, skills, plugins).

## Activation

This skill activates when:

- User invokes `/aida` command with any action
- AIDA functionality is needed (configuration, status checks, diagnostics)
- Command routing and execution orchestration is required

## Command Routing

When this skill activates, check the `<command-args>` tag to determine which action to route:

### Diagnostic Commands

For `status`, `doctor`, or `upgrade` commands:

- Read `references/diagnostics.md` for execution workflow
- These are non-interactive commands that execute Python scripts directly

### Configuration Commands

For `config` command (alone):

- Read `references/config.md` for YAML-based configuration workflow
- This is an interactive command with:
  - Dynamic menu generation based on installation state
  - Auto-detection of project facts (saved to YAML)
  - Minimal questions (0-3) for unknown preferences only
  - Automatic skill generation from YAML config

For `config validate` command:

- Read `references/validate.md` for the workflow
- This is a **non-interactive** CI-friendly health check
- Run `~/.aida/venv/bin/python3 {base_directory}/scripts/validate.py`
- Exits 0 on success, 1 on failure — suitable for `make` / CI gates
- Pass `--json` for machine-consumable output

### Permissions Commands

For `config permissions` or `permissions` commands:

- **Invoke the `permissions` skill** to handle these operations
- The skill handles interactive permission setup and audit mode

**Process:**

1. Parse the command to detect:
   - `--audit` flag for audit mode
   - No flags for interactive setup

2. Invoke `permissions` skill with the parsed context

**Examples:**

```text
/aida config permissions           → permissions skill
/aida config permissions --audit   → permissions skill (audit)
```

### Feedback Commands

For `feedback`, `bug`, or `feature-request` commands:

- Read `references/feedback.md` for feedback collection workflow
- These are interactive commands that collect and submit user input

### Help Command

For `help` or no arguments:

- Display the help text inline (see Help Text section below)
- Read the plugin version from `{base_directory}/../../.claude-plugin/plugin.json`
  (the `"version"` field) and include it in the footer
- No additional reference files need to be loaded

### About Command

For `about`:

- Read `{base_directory}/../../.claude-plugin/plugin.json`
- Resolve the installed path from `{base_directory}/../..`
- Display plugin metadata:

```markdown
**AIDA Core Plugin**

- **Version:** {version from plugin.json}
- **Author:** {author.name from plugin.json}
- **Repository:** {repository from plugin.json}
- **Installed at:** {resolved path to plugin root}
```

### Agent Management Commands

For `agent` commands:

- **Invoke the `agent-manager` skill** to handle these operations
- Pass the full command arguments to the skill
- The skill handles create, validate, version, and list operations

**Process:**

1. Parse the command to extract:
   - Operation: `create`, `validate`, `version`, `list`
   - Arguments: name, description, options

2. Invoke `agent-manager` skill with the parsed context

**Examples:**

```text
/aida agent create "description"     → agent-manager skill
/aida agent validate --all           → agent-manager skill
/aida agent version my-agent patch   → agent-manager skill
/aida agent list                     → agent-manager skill
```

### Skill Management Commands

For `skill` commands:

- **Invoke the `skill-manager` skill** to handle these operations
- Pass the full command arguments to the skill
- The skill handles create, validate, version, and list operations

**Process:**

1. Parse the command to extract:
   - Operation: `create`, `validate`, `version`, `list`
   - Arguments: name, description, options

2. Invoke `skill-manager` skill with the parsed context

**Examples:**

```text
/aida skill create "description"     → skill-manager skill
/aida skill validate --all           → skill-manager skill
/aida skill version my-skill patch   → skill-manager skill
/aida skill list                     → skill-manager skill
```

### Plugin Management Commands

For `plugin` commands (including `plugin scaffold`):

- **Invoke the `plugin-manager` skill** to handle these operations
- Pass the full command arguments to the skill
- The skill handles create, validate, version, list, scaffold, update,
  deps, and agents operations
- Scaffold creates a NEW plugin project (not an extension inside an existing
  project)
- Update scans an existing plugin and patches it to current standards
- Deps reports declared plugin dependencies + their satisfied / missing /
  wrong-version status (#20)

**Process:**

1. Parse the command to extract:
   - Operation: `create`, `validate`, `version`, `list`, `scaffold`,
     `update`, `deps`
   - Arguments: name, description, options

2. Invoke `plugin-manager` skill with the parsed context

**Examples:**

```text
/aida plugin create "description"        → plugin-manager skill
/aida plugin validate --all              → plugin-manager skill
/aida plugin list                        → plugin-manager skill
/aida plugin scaffold "my-new-plugin"    → plugin-manager skill
/aida plugin scaffold                    → plugin-manager skill (will ask)
/aida plugin update "/path/to/plugin"   → plugin-manager skill
/aida plugin deps                        → plugin-manager skill (cwd)
/aida plugin deps "/path/to/plugin"     → plugin-manager skill
/aida plugin agents                      → plugin-manager skill (cwd)
/aida plugin agents "/path/to/project"  → plugin-manager skill
```

### Hook Management Commands

For `hook` commands:

- **Invoke the `hook-manager` skill** to handle these operations
- Pass the full command arguments to the skill
- Hooks are settings.json config, not files
- The skill handles list, add, remove, and validate operations

**Process:**

1. Parse the command to extract:
   - Operation: `list`, `add`, `remove`, `validate`
   - Arguments: event, matcher, command, scope

2. Invoke `hook-manager` skill with the parsed context

**Examples:**

```text
/aida hook list                      → hook-manager skill
/aida hook add "auto-format"         → hook-manager skill
/aida hook remove my-hook            → hook-manager skill
/aida hook validate                  → hook-manager skill
```

### Expert Registry Commands

For `expert` commands:

- **Invoke the `expert-registry` skill** to handle operations
- Pass the full command arguments to the skill
- The skill handles list, configure, panels, and panel operations

**Process:**

1. Parse the command to extract:
   - Operation: `list`, `list configure`, `panel list`,
     `panel create`, `panel remove`
   - Arguments: panel name (for create/remove)

2. Invoke `expert-registry` skill with the parsed context

**Examples:**

```text
/aida expert list                   → expert-registry skill
/aida expert list configure        → expert-registry skill
/aida expert panel list            → expert-registry skill
/aida expert panel create review   → expert-registry skill
/aida expert panel remove review   → expert-registry skill
```

### Knowledge Commands

`/aida knowledge` commands split across two skills:

- **`knowledge-sync` skill** owns the mechanic — `sync`, `status`,
  `discover`. Deterministic: reads source declarations, fetches
  content, walks spider roots.
- **`knowledge-curator` skill** owns the policy workflow — `curate`,
  `review`. LLM-orchestrated: reasons about which discovered URLs are
  worth using and persists decisions.

**Process:**

1. Parse the command to extract:
   - Operation: `sync`, `status`, `discover`, `curate`, `review`
   - Argument: agent name (and any flags)

2. Route to the appropriate skill:

| Command | Skill | Script |
| ------- | ----- | ------ |
| `sync <agent>` | knowledge-sync | `sync.py --agent <name>` |
| `status <agent>` | knowledge-sync | `sync.py --agent <name> --dry-run` |
| `discover <agent>` | knowledge-sync | `discover.py --agent <name>` |
| `audit <agent>` | knowledge-sync | `audit.py --agent <name>` |
| `promote <agent> --url X --file F --section S` | knowledge-sync | `promote.py --agent <name> --url X --file F --section S` |
| `regenerate-md <agent>` | knowledge-sync | `regenerate_md.py --agent <name>` |
| `curate <agent>` | knowledge-curator | follow SKILL.md workflow |
| `review <agent>` | knowledge-curator | follow SKILL.md workflow |

Script paths are resolved as
`~/.aida/venv/bin/python3 {base_directory}/../<skill>/scripts/<file>.py`.

**Examples:**

```text
/aida knowledge sync <agent>           → knowledge-sync (sync.py)
/aida knowledge status <agent>         → knowledge-sync (--dry-run)
/aida knowledge discover <agent>       → knowledge-sync (discover.py)
/aida knowledge audit <agent>          → knowledge-sync (audit.py)
/aida knowledge promote <agent> ...    → knowledge-sync (promote.py)
/aida knowledge regenerate-md <agent>  → knowledge-sync (regenerate_md.py)
/aida knowledge curate <agent>         → knowledge-curator (workflow)
/aida knowledge review <agent>         → knowledge-curator (workflow)
```

### Memento Commands

For `memento` commands:

- **Invoke the `memento` skill** to handle these operations
- Pass the full command arguments to the skill
- The skill handles create, read, list, update, complete, and remove operations

**Process:**

1. Parse the command to extract:
   - Operation: `create`, `read`, `list`, `update`, `complete`, `remove`
   - Arguments: description, slug, source, filter options

2. Invoke `memento` skill with the parsed context

**Examples:**

```text
/aida memento create "description"   → memento skill
/aida memento create from-pr         → memento skill (source=from-pr)
/aida memento create from-changes    → memento skill (source=from-changes)
/aida memento read my-memento        → memento skill
/aida memento list                   → memento skill
/aida memento list --filter active   → memento skill
/aida memento list --all             → memento skill (all_projects=true)
/aida memento list --project foo     → memento skill (project_filter=foo)
/aida memento update my-memento      → memento skill
/aida memento complete my-memento    → memento skill
/aida memento remove my-memento      → memento skill
```

### CLAUDE.md Management Commands

For `claude` commands:

- **Invoke the `claude-md-manager` skill** to handle these operations
- Pass the full command arguments to the skill
- The skill handles create, optimize, validate, and list operations

**Process:**

1. Parse the command to extract:
   - Operation: `create`, `optimize`, `validate`, `list`
   - Arguments: scope (project/user/plugin), path, options

2. Invoke `claude-md-manager` skill with the parsed context

**Examples:**

```text
/aida claude create                  → claude-md-manager skill (auto-detect scope)
/aida claude create --scope project  → claude-md-manager skill (scope=project)
/aida claude create --scope user     → claude-md-manager skill (scope=user)
/aida claude optimize                → claude-md-manager skill (audit current)
/aida claude optimize ./CLAUDE.md    → claude-md-manager skill (audit specific)
/aida claude validate                → claude-md-manager skill
/aida claude list                    → claude-md-manager skill
```

## Path Resolution

**Base Directory:** Provided when skill loads via `<command-message>` tags containing the skill base directory.

**Script Execution:** Construct full paths from base directory:

```text
{base_directory}/scripts/status.py
{base_directory}/scripts/doctor.py
{base_directory}/scripts/upgrade.py
{base_directory}/scripts/detect.py
{base_directory}/scripts/configure.py
{base_directory}/scripts/install.py
{base_directory}/scripts/feedback.py
```

**Reference Loading:** Reference files are located in `references/` subdirectory:

```text
{base_directory}/references/diagnostics.md
{base_directory}/references/config.md
{base_directory}/references/feedback.md
```

## Help Text

When displaying help (for `help` command or no arguments), show:

```markdown
## Available AIDA Commands

### Configuration & Setup
- `/aida config` - Configure AIDA settings (global or project-level)
- `/aida config validate` - Non-interactive CI-friendly health check
- `/aida config permissions` - Configure Claude Code permissions from plugin recommendations
- `/aida status` - Check AIDA installation and configuration status
- `/aida doctor` - Run diagnostics to troubleshoot AIDA issues

### Maintenance
- `/aida upgrade` - Check for and install AIDA updates

### Feedback & Support
- `/aida feedback` - Submit feedback about AIDA
- `/aida bug` - Report a bug in AIDA
- `/aida feature-request` - Request a new AIDA feature

### Extension Management
- `/aida agent [create|validate|version|list]` - Manage agents
- `/aida skill [create|validate|version|list]` - Manage skills
- `/aida plugin [scaffold|create|validate|version|list|update]` - Manage plugins
- `/aida hook [list|add|remove|validate]` - Manage hooks (settings.json)

### Expert Registry
- `/aida expert list` - List available experts and activation status
- `/aida expert list configure` - Select active experts (project or global)
- `/aida expert panel list` - Show named panel compositions
- `/aida expert panel create <name>` - Create a named expert panel
- `/aida expert panel remove <name>` - Remove a named panel

### Knowledge
- `/aida knowledge sync <agent>` - Sync an agent's knowledge from declared sources + in-use decisions
- `/aida knowledge status <agent>` - Dry-run; report what would change
- `/aida knowledge discover <agent>` - Spider configured roots; record new URLs as pending decisions
- `/aida knowledge audit <agent>` - Drift report (pending count, stale verdicts, never-synced URLs)
- `/aida knowledge promote <agent> --url X --file F --section S` - Manually mark a URL in-use (skip the LLM curator)
- `/aida knowledge regenerate-md <agent>` - Repair: rebuild decisions.md from decisions.json
- `/aida knowledge curate <agent>` - LLM workflow: decide pending URLs into in-use or rejected
- `/aida knowledge review <agent>` - Interactive: human confirms or overrides curator decisions

### Session Persistence
- `/aida memento create "description"` - Save current work context
- `/aida memento create from-pr` - Create from current PR
- `/aida memento create from-changes` - Create from file changes
- `/aida memento read <slug>` - Load memento into context
- `/aida memento list` - List active mementos
- `/aida memento list --all` - List mementos from all projects
- `/aida memento list --project <name>` - List mementos for specific project
- `/aida memento update <slug>` - Update memento sections
- `/aida memento complete <slug>` - Archive completed memento

### CLAUDE.md Management
- `/aida claude create` - Create CLAUDE.md with auto-detection
- `/aida claude create --scope user` - Create user-level CLAUDE.md
- `/aida claude optimize` - Full audit with scoring and findings
- `/aida claude validate` - Validate CLAUDE.md structure
- `/aida claude list` - List all CLAUDE.md files in hierarchy

### Info
- `/aida help` or `/aida` - Show this help message
- `/aida about` - Show plugin version and metadata
- `/aida status` - Show installation status and version

## Getting Started

If you haven't configured AIDA yet: `/aida config`
To check if AIDA is working: `/aida status`
If you encounter issues: `/aida doctor`
To create an agent: `/aida agent create "description"`
To save work context: `/aida memento create "description"`
To optimize your CLAUDE.md: `/aida claude optimize`
To list hooks: `/aida hook list`
To add a hook: `/aida hook add "auto-format on write"`

---
aida-core v{version from plugin.json}
```

## Resources

### scripts/

Executable Python scripts for AIDA operations:

- **status.py** - Display current installation and configuration state
- **doctor.py** - Run health checks and diagnostics
- **upgrade.py** - Check for and install updates
- **detect.py** - Detect current installation state (used by config)
- **configure.py** - Interactive project configuration
- **install.py** - Global installation setup
- **feedback.py** - Submit feedback, bugs, and feature requests
- **utils/** - Shared utilities (paths, files, version, questionnaire, etc.)

### references/

Detailed workflow guides loaded as needed:

- **diagnostics.md** - Workflow for status/doctor/upgrade commands
- **config.md** - YAML-based configuration flow with auto-detection
- **feedback.md** - Feedback collection and submission workflow
- **config-driven-approach.md** - Architecture documentation for config system
- **project-facts.md** - Comprehensive taxonomy of detectable project facts
