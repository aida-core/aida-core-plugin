---
type: readme
title: "AIDA Core Plugin"
description: "Foundation plugin for AIDA"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# AIDA Core Plugin

> The foundation for building your custom Claude Code experience.

**Requires:** Claude Code (latest) and Python 3.8+ (on Debian/Ubuntu, also `python3-venv`)

## Why AIDA?

Claude Code is extensible — but there's no scaffolding. Building agents and skills
from scratch means reinventing structure, conventions, and patterns every time. AIDA gives you
the foundation to build on.

**A bootstrap, not a box.** AIDA provides the base layer — configuration management, extension
scaffolding, session persistence — so you can focus on building the tools that matter to your
workflow.

**Standardized extension creation.** Create agents, skills, and plugins with guided
templates that follow consistent conventions. Run `/aida agent create` and get properly
structured extensions without guessing at the format.

**Configuration at every level.** User-level defaults, project-level overrides, auto-detected
environment settings. Your setup stays consistent across projects and portable across machines.

**Structured session context.** Mementos capture rich project state — not just facts, but the
full context of what you're working on. Save mid-task, restore tomorrow, scoped to the project
or your user profile.

## Features

- **Session Memory** - Save and restore context across sessions with mementos
- **Smart Configuration** - Auto-detects your environment, tools, and project setup
- **Extension Creation** - Build agents and skills with guided templates
- **Project Context** - Claude understands your codebase patterns and conventions
- **Health Diagnostics** - Built-in troubleshooting with `/aida doctor`
- **Expert Registry** - Manage expert agents and panel compositions
- **GitHub Integration** - Easy bug reports and feature requests

## Quick Start

### Step 1: Add Marketplace

```bash
/plugin marketplace add aida-core/aida-marketplace
```

### Step 2: Install

```bash
/plugin install core@aida
```

### Step 3: Configure

```bash
/aida config
```

### Step 4: Verify

```bash
/aida status
```

For detailed walkthrough, see the [Getting Started Guide](docs/GETTING_STARTED.md).

## Commands

| Command                       | Description                          |
| ----------------------------- | ------------------------------------ |
| `/aida config`                | Configure AIDA (global or project)   |
| `/aida status`                | Check installation and configuration |
| `/aida doctor`                | Run health diagnostics               |
| `/aida memento`               | Save/restore session context         |
| `/aida agent create`          | Create a custom agent                |
| `/aida skill create`          | Create a custom skill                |
| `/aida expert list`           | List available experts and status    |
| `/aida expert list configure` | Select active experts for a project  |
| `/aida expert panel list`     | Show named panel compositions        |
| `/aida feedback`              | Submit feedback via GitHub           |
| `/aida bug`                   | Report a bug                         |
| `/aida feature-request`       | Request a feature                    |

## Documentation

### Getting Started

- **[Getting Started](docs/GETTING_STARTED.md)** - Quick onboarding guide
- **[Installation Guide](docs/USER_GUIDE_INSTALL.md)** - Detailed setup walkthrough
- **[Configuration Guide](docs/USER_GUIDE_CONFIGURE.md)** - Project configuration

### How-To Guides

- **[Using Mementos](docs/HOWTO_MEMENTO.md)** - Save and restore session context
- **[Creating Agents](docs/HOWTO_CREATE_AGENT.md)** - Build custom expert personas
- **[Creating Skills](docs/HOWTO_CREATE_SKILL.md)** - Add execution capabilities
- **[Using Hooks](docs/HOWTO_HOOKS.md)** - Automate with lifecycle events

### Reference

- **[Examples](docs/EXAMPLES.md)** - Real-world usage scenarios
- **[Extension Framework](docs/EXTENSION_FRAMEWORK.md)** - Architecture and design
- **[Frontmatter Schema](docs/FRONTMATTER_SCHEMA.md)** - Reusable JSON Schema downstream plugins and marketplaces should adopt verbatim

## Requirements

- **Claude Code** - Latest version
- **Python 3.8+** - For script execution (on Debian/Ubuntu, also `python3-venv`)
- **gh CLI** (optional) - For feedback features

> Python dependencies are managed automatically. AIDA creates a
> virtual environment at `~/.aida/venv/` on first use -- no manual
> `pip install` required.

## Architecture

AIDA extends Claude Code with a layered extension system:

```text
agents/          # WHO - Expert personas
skills/          # HOW - Process definitions + execution capabilities
```

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design.

## Roadmap

### Current: v1.3.x

- Expert registry for panel activation and composition
- Session persistence (mementos)
- Smart configuration with auto-detection
- Agent-based orchestration
- Extension creation (`/aida agent|skill|plugin create`)
- Hook management (`/aida hook`)
- Marketplace integration
- Security hardening and test coverage

### Next: Sharing & Collaboration

- Export/import extensions for sharing
- Team collaboration features
- Advanced extension marketplace

## Contributing

We welcome contributions!

```bash
/aida bug              # Report bugs
/aida feature-request  # Request features
/aida feedback         # General feedback
```

See [DEVELOPMENT.md](docs/DEVELOPMENT.md) for contributor guidelines.

## Support

- **Issues**: [GitHub Issues](https://github.com/aida-core/aida-core-plugin/issues)
- **Discussions**: [GitHub Discussions](https://github.com/aida-core/aida-core-plugin/discussions)
- **Diagnostics**: `/aida doctor`

## License

MPL-2.0 - See [LICENSE](LICENSE)

---

**Ready to get started?** Run `/aida config` to begin.
