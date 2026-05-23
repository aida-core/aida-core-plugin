---
type: readme
title: AIDA Core Plugin
description: "AIDA Core plugin manifest for Claude Code — project layout, conventions, and development setup."
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# AIDA Core Plugin

Claude Code plugin providing smart configuration, GitHub integration, and context
management capabilities.

## Project Structure

```text
aida-core-plugin/
├── .claude-plugin/       # Plugin metadata
│   ├── plugin.json       # Required plugin manifest
│   └── marketplace.json  # Marketplace listing
├── agents/               # Subagent definitions
│   ├── aida/             # AIDA assistant subagent
│   └── claude-code-expert/  # Extension design expert
├── skills/               # Process definitions + execution capabilities
│   ├── aida/             # /aida skill - routing, scripts, references
│   ├── agent-manager/    # Agent CRUD operations
│   ├── claude-md-manager/  # CLAUDE.md management
│   ├── hook-manager/     # Hook configuration management
│   ├── memento/          # Session persistence
│   ├── permissions/      # Permission management
│   ├── plugin-manager/   # Plugin CRUD + scaffolding
│   └── skill-manager/    # Skill CRUD operations
├── tests/                # Python tests
└── docs/                 # Documentation
```

## Development

### Setup

All Python tools (pytest, ruff, yamllint) live in `~/.aida/venv/`.
The Makefile targets reference this venv automatically.

```bash
make install       # Install runtime + dev deps into ~/.aida/venv
```

### Commands

```bash
make lint          # Run all linters (ruff, yamllint, markdownlint)
make test          # Run pytest
make clean         # Remove build artifacts
```

### Testing

```bash
make test                                          # Run all tests
~/.aida/venv/bin/pytest tests/test_manage.py -v    # Run specific test file
```

## Conventions

### Extension Types (see agents/claude-code-expert/knowledge/)

- **Subagents**: WHO - expertise definitions in `agents/`
- **Skills**: HOW - process definitions + execution capabilities in `skills/`
- **Knowledge**: CONTEXT - reference material in `knowledge/` subdirs

### File Naming

- Subagents: `agents/{name}/{name}.md` with `knowledge/` subdir
- Skills: `skills/{name}/SKILL.md` with `scripts/`, `templates/`, `references/`

### Python Style

- Use ruff for linting and formatting
- Type hints required for public functions
- Scripts in skills use `if __name__ == "__main__":` pattern

### Markdown

- YAML frontmatter required (type, name, description, version)
- Use markdownlint (config in `.markdownlint.json`)
- Line length: 88 characters (matches ruff)

## Key Files

- `agents/claude-code-expert/knowledge/framework-design-principles.md` - Extension architecture reference
- `skills/aida/SKILL.md` - Main skill entry point and command routing
- `skills/agent-manager/SKILL.md` - Agent CRUD operations
- `skills/skill-manager/SKILL.md` - Skill CRUD operations
- `skills/plugin-manager/SKILL.md` - Plugin CRUD + scaffolding
- `skills/hook-manager/SKILL.md` - Hook configuration management
- `skills/claude-md-manager/SKILL.md` - CLAUDE.md management
