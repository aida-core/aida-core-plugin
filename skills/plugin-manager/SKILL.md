---
type: skill
name: plugin-manager
title: Plugin Manager
description: >-
  Unified plugin management combining extension CRUD operations
  (create, validate, version, list) with project scaffolding
version: 0.1.0
argument_hint: "[operation] [args]"
tags:
  - core
  - management
  - plugin
  - scaffolding
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Plugin Manager

Unified plugin management skill that combines two capabilities:

1. **Extension CRUD** -- create, validate, version, and list plugin
   extensions within existing projects
2. **Project Scaffolding** -- scaffold entirely new plugin projects
   as local git repositories with language-specific tooling

## Activation

This skill activates when:

- User invokes `/aida plugin create`
- User invokes `/aida plugin validate`
- User invokes `/aida plugin version`
- User invokes `/aida plugin list`
- User invokes `/aida plugin scaffold`
- User invokes `/aida plugin update`
- User invokes `/aida plugin deps`
- Routed from `aida` skill for any plugin operation

## Operations

| Operation  | Mode        | Description                                |
| ---------- | ----------- | ------------------------------------------ |
| `create`   | Extension   | Create plugin extension dirs/files         |
| `validate` | Extension   | Validate plugin.json metadata              |
| `version`  | Extension   | Bump plugin.json version                   |
| `list`     | Extension   | List discovered plugins                    |
| `scaffold` | Scaffolding | Scaffold a full new plugin project         |
| `update`   | Migration   | Scan and patch plugin to current standards |
| `deps`     | Inspection  | Report a plugin's declared deps + status   |

## Path Resolution

**Base Directory:** Provided when skill loads via
`<command-message>` tags containing the skill base directory.

**Script Execution:**

```text
{base_directory}/scripts/manage.py
```

**Templates:**

```text
{base_directory}/templates/extension/   # Plugin extension templates
{base_directory}/templates/scaffold/    # Project scaffolding templates
```

## Two-Phase Workflow

### Extension Operations (create / validate / version / list)

#### Phase 1: Gather Context

```bash
python {base_directory}/scripts/manage.py --get-questions \
  --context='{"operation": "create", "description": "..."}'
```

Returns questions and inferred metadata. The script auto-sets
`component_type` to `"plugin"`.

#### Phase 2: Execute

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "create", ...}'
```

Creates, validates, versions, or lists plugin extensions.

### Scaffold Operation

#### Phase 1: Gather Context

```bash
python {base_directory}/scripts/manage.py --get-questions \
  --context='{"operation": "scaffold", "plugin_name": "my-plugin"}'
```

Infers git config (author name/email), checks gh availability,
and returns questions for missing fields (name, description,
license, language, target directory, stubs, keywords).

#### Phase 2: Execute Scaffolding

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "scaffold", "plugin_name": "my-plugin", "language": "python", ...}'
```

Creates a complete plugin project with:

- Directory structure (`.claude-plugin/`, agents, skills, docs)
- Metadata files (`plugin.json`, `marketplace.json`,
  `aida-config.json`)
- Documentation (`CLAUDE.md`, `README.md`, `LICENSE`)
- Language tooling (pyproject.toml or package.json, linters)
- Composite `.gitignore` and `Makefile`
- Optional agent and skill stubs
- Initialized git repository with initial commit

### Update Operation

#### Phase 1: Scan and Report

```bash
python {base_directory}/scripts/manage.py --get-questions \
  --context='{"operation": "update", "plugin_path": "/path/to/plugin"}'
```

Scans the plugin directory against current scaffold standards.
Returns a diff report with file-by-file comparison results
categorized as: missing, outdated, up-to-date, or custom-skip.

The orchestrator should present the scan report to the user
in this order:

1. Version context: scaffolded version vs current standard
2. Summary counts (missing, outdated, up-to-date, skipped)
3. Missing files (will be added)
4. Outdated files (will be updated per merge strategy)
5. Files flagged for manual review
6. Custom content files (will NOT be touched)
7. Merge strategy question (if boilerplate files need
   updating)

#### Phase 2: Apply Patches

```bash
python {base_directory}/scripts/manage.py --execute \
  --context='{"operation": "update", "plugin_path": "/path/to/plugin"}' \
  --responses='{"boilerplate_strategy": "overwrite"}'
```

Applies approved patches to the plugin:

- Creates backup at `.aida-backup/{timestamp}/`
- Adds missing files from templates
- Overwrites or skips outdated boilerplate per strategy
- Merges composite files (`.gitignore`, `Makefile`)
  append-only
- Skips custom content files (`CLAUDE.md`, `README.md`)
- Flags dependency configs for manual review
- Updates `generator_version` in `aida-config.json`

#### Present Results

After Phase 2 completes, present the results in this order:

1. Success message with old and new generator version
2. Files created (from `files_created`)
3. Files updated (from `files_updated`)
4. Files skipped (from `files_skipped`, brief)
5. Backup location (`backup_path`) if any files were
   modified
6. Manual steps required (`manual_steps`) -- present as
   a numbered checklist

#### File Categories

| Category         | Strategy        | Files                     |
| ---------------- | --------------- | ------------------------- |
| Custom content   | `skip`          | CLAUDE.md, README.md,     |
|                  |                 | LICENSE                   |
| AIDA metadata    | `skip`          | aida-config.json          |
| Plugin metadata  | `skip`          | plugin.json,              |
|                  |                 | marketplace.json          |
| Boilerplate      | `overwrite`     | Linting configs, version  |
|                  |                 | files                     |
| Composite        | `merge`         | .gitignore, Makefile      |
| CI workflows     | `add`           | .github/workflows/ci.yml  |
| Test scaffold    | `add`           | tests/conftest.py         |
| Dependencies     | `manual_review` | pyproject.toml,           |
|                  |                 | package.json              |

### Post-Scaffold: GitHub Repository (Optional)

If the user requested `create_github_repo: true`, the result
includes this flag. Use the GitHub CLI to create the remote:

```bash
cd /path/to/my-plugin
gh repo create my-plugin --public --source=. --push
```

## Plugin Validation Notes

Plugin validation is **JSON-based** (plugin.json), not
frontmatter-based like agents and skills. The validation checks:

- `name` -- required, kebab-case, 2-50 chars
- `version` -- required, semver X.Y.Z
- `description` -- required, 10-500 chars

## Error Handling

If Phase 2 returns `{"success": false, ...}`, report the
`message` field to the user and offer to retry. The response
includes `path` and `files_created` for any partial output.

## Resources

### scripts/

- **manage.py** -- Two-phase API entry point (routes between
  extension and scaffold operations)
- **operations/extensions.py** -- Plugin extension CRUD
- **operations/scaffold.py** -- Plugin project scaffolding
- **operations/scaffold_ops/** -- Scaffolding submodules
  - **context.py** -- Git config inference, directory validation
  - **generators.py** -- Directory creation, template rendering
  - **licenses.py** -- License text templates
- **operations/constants.py** -- Shared constants
  (GENERATOR_VERSION, SUPPORTED_LANGUAGES)
- **operations/shared.py** -- Shared template variable
  builder used by both scaffold and update
- **operations/update.py** -- Plugin update entry point
  (scan and patch operations)
- **operations/update_ops/** -- Update submodules
  - **scanner.py** -- Plugin scanning and comparison
  - **patcher.py** -- File patching with backup
  - **models.py** -- Data structures (DiffReport, etc.)
  - **strategies.py** -- File classification registry
  - **parsers.py** -- Shared gitignore/Makefile parsing
- **operations/utils.py** -- Re-export shim for shared utilities

### templates/

- **extension/** -- Plugin extension templates (plugin.json,
  README.md, .gitignore)
- **scaffold/** -- Project scaffolding templates
  - **shared/** -- Language-independent files
  - **python/** -- Python toolchain templates
  - **typescript/** -- TypeScript toolchain templates

### references/

- **scaffolding-workflow.md** -- Scaffolding workflow reference
- **validate-workflow.md** -- Plugin validation reference
- **update-workflow.md** -- Update workflow reference
- **schemas.md** -- Plugin JSON schema reference
