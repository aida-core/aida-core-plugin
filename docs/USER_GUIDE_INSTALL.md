---
type: guide
title: "Installation Guide"
description: "How to install AIDA Core and add it to Claude Code."
audience: users
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# AIDA Installation Guide

Complete walkthrough for installing and setting up AIDA Core Plugin

This guide walks you through installing AIDA for the first time, from
prerequisites to verification.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation Steps](#installation-steps)
- [Questionnaire Deep Dive](#questionnaire-deep-dive)
- [What Gets Created](#what-gets-created)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Next Steps](#next-steps)

## Prerequisites

Before installing AIDA, ensure you have:

### 1. Claude Code

**Required**: Latest version of Claude Code

- Download from [claude.ai/code](https://claude.ai/code)
- Verify installation: Open Claude Code CLI

### 2. Python 3.8+

**Required**: Python 3.8 or higher

```bash
# Check your Python version
python3 --version

# Should output: Python 3.8.x or higher
```

**If you need to install/upgrade Python:**

- macOS: `brew install python3` or download from [python.org](https://www.python.org/downloads/)
- Linux: `sudo apt install python3 python3-venv` (Debian/Ubuntu) or `sudo yum install python3` (RHEL/CentOS)
- Windows (WSL): `sudo apt install python3 python3-venv`

> **Note:** On Debian/Ubuntu, the `python3-venv` package is required
> for AIDA to create its managed virtual environment. AIDA
> automatically manages a venv at `~/.aida/venv/` so you do not need
> to install Python packages manually.

### 3. GitHub CLI

**Required**: gh CLI for feedback system

```bash
# Check if gh is installed
gh --version

# Should output: gh version x.x.x
```

**If you need to install gh:**

- macOS: `brew install gh`
- Linux: See [cli.github.com](https://cli.github.com/)
- Windows (WSL): [cli.github.com](https://cli.github.com/)

**Authenticate gh:**

```bash
gh auth login
# Follow the prompts
```

### 4. Git (Optional but Recommended)

**Recommended**: For project detection in `/aida config`

```bash
git --version
```

## Installation Steps

### Step 1: Add AIDA Marketplace

Open Claude Code and add the AIDA marketplace (one-time setup):

```bash
/plugin marketplace add aida-core/aida-marketplace
```

**Expected output:**

```text
Adding marketplace aida-core/aida-marketplace...
✓ Fetched marketplace registry
✓ Added marketplace "aida"

Available plugins: core
```

### Step 2: Install Core Plugin

Install the core AIDA plugin:

```bash
/plugin install core@aida
```

**Expected output:**

```text
Installing plugin core@aida...
✓ Downloaded plugin files
✓ Verified plugin structure
✓ Installed aida-core
✓ Plugin enabled

Run /aida config to set up your personal preferences.
```

**Time required**: ~30 seconds

### Step 3: Run Installation Wizard

Launch the installation wizard:

```bash
/aida config
```

#### 2.1 Welcome & Requirements Check

```text
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   Welcome to AIDA - Agentic Intelligence Digital        ║
║                     Assistant                            ║
║                                                          ║
║   Your personal JARVIS for Claude Code                  ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

Checking requirements...
✓ Python 3.11.5 found
✓ gh CLI 2.40.0 found
✓ Requirements satisfied
```

**If requirements fail:**

- Python not found: See [Prerequisites - Python](#2-python-38)
- gh not found: See [Prerequisites - GitHub CLI](#3-github-cli)

#### 2.2 Existing Installation Check

If you've run `/aida config` before:

```text
⚠ Personal skills already exist at:
  ~/.claude/skills/user-context/

Do you want to reinstall? This will overwrite your existing preferences.

[y/N]: _
```

**Choices:**

- `N` (default): Exit and keep existing installation
- `y`: Overwrite with new preferences (current skills will be backed up)

**Backup location**: `~/.claude/skills/.backup-TIMESTAMP/`

#### 2.3 Interactive Questionnaire

AIDA will ask 5 questions to customize your experience:

```text
Let's learn about your coding preferences and work patterns.
This takes about 2 minutes.

Press Ctrl+C at any time to cancel.

───────────────────────────────────────────────────────────
```

See [Questionnaire Deep Dive](#questionnaire-deep-dive) below for detailed explanations of each question.

#### 2.4 Skill Creation

After the questionnaire:

```text
Creating your personal skills...

✓ Created ~/.claude/skills/user-context/SKILL.md
✓ Updated ~/.claude/settings.json

───────────────────────────────────────────────────────────
```

#### 2.5 Success Message

```text
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   ✓ AIDA Installation Complete!                         ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

Your personal skills have been created at:
  ~/.claude/skills/user-context/

These skills will be active in all your Claude conversations,
providing consistent context about your preferences.

Next Steps:
  1. Configure AIDA for a specific project:
     cd your-project/
     /aida config

  2. Check your configuration:
     /aida status

  3. Get help anytime:
     /aida help

Happy coding! 🚀
```

**Total time**: ~3-5 minutes

## Questionnaire Deep Dive

The installation questionnaire asks 5 questions that shape how AIDA works for you.

### Question 1: Coding Standards

```text
What coding standards and style guides do you follow?

Examples: PEP 8, Airbnb JavaScript, PSR-12 PHP, custom team conventions

Your answer: _
```

**Purpose**: Ensures Claude generates code matching your standards

**Good answers:**

- "PEP 8 for Python, Airbnb style for JavaScript"
- "Google style guides with custom team modifications"
- "Standard Go formatting, ESLint Recommended config"
- "PSR-12 for PHP, PHPUnit for tests"

**Bad answers:**

- "Whatever works" (too vague)
- Leaving blank (no context for AIDA)

**Impact**: High - affects all code generation across all projects

### Question 2: Work Hours and Patterns

```text
What are your typical working hours and patterns?

Choose one:
  [1] Traditional 9-5 schedule
  [2] Flexible hours with core overlap
  [3] Remote/async with no fixed schedule
  [4] Deep work blocks in morning, meetings afternoon
  [5] Evening/night work preferred

Your choice [2]: _
```

**Purpose**: Helps AIDA understand when you're focused vs. available

**Default**: Option 2 (Flexible hours with core overlap)

**Considerations:**

- **Option 1**: Traditional schedule, prefer structured days
- **Option 2**: Flexible but have team overlap times
- **Option 3**: Fully async, work whenever
- **Option 4**: Protect deep work time in mornings
- **Option 5**: Night owl, work evenings/nights

**Impact**: Low - informational for future features

### Question 3: Communication Style

```text
What communication style do you prefer from AIDA?

Choose one:
  [1] Direct and concise - just the essentials
  [2] Detailed with context and examples
  [3] Conversational and friendly
  [4] Technical and precise
  [5] Balanced - detailed when needed, concise otherwise

Your choice [5]: _
```

**Purpose**: Shapes how Claude responds to you

**Default**: Option 5 (Balanced)

**Choose based on preference:**

- **Option 1**: Busy, want quick answers
- **Option 2**: Learning, want explanations
- **Option 3**: Enjoy friendly interactions
- **Option 4**: Experienced, want precision
- **Option 5**: Situational - adapt to context

**Impact**: Medium - affects response tone and detail

### Question 4: Primary Development Tools

```text
What are your primary development tools and technologies?

Examples: Python, Git, VS Code, Docker

Your answer: _
```

**Purpose**: Ensures Claude suggests familiar tools

**Good answers:**

- "Python, Django, PostgreSQL, Docker, GitHub Actions"
- "React, TypeScript, Next.js, Tailwind, Vercel"
- "Go, gRPC, Kubernetes, Prometheus"
- "PHP, Laravel, MySQL, Redis, AWS"

**Include:**

- Languages (Python, JavaScript, Go, etc.)
- Frameworks (Django, React, Laravel, etc.)
- Editors (VS Code, Vim, IntelliJ, etc.)
- Tools (Docker, Git, Make, etc.)
- Services (AWS, GitHub, Vercel, etc.)

**Impact**: High - affects tool suggestions and examples

### Question 5: Decision Tracking Detail

```text
How detailed should AIDA's decision tracking be?

Choose one:
  [1] Minimal - only major architectural decisions
  [2] Moderate - key decisions and trade-offs
  [3] Detailed - track most technical choices
  [4] Comprehensive - document everything possible

Your choice [2]: _
```

**Purpose**: Controls decision logging verbosity

**Default**: Option 2 (Moderate)

**Choose based on needs:**

- **Option 1**: Small projects, don't need much history
- **Option 2**: Typical projects, important decisions only
- **Option 3**: Complex projects, lots of choices
- **Option 4**: Enterprise, compliance, audit trails

**Impact**: Medium - affects future decision tracking features

## What Gets Created

After installation, AIDA creates these files and directories:

### Directory Structure

```text
~/.claude/
├── skills/
│   ├── user-context/
│   │   └── SKILL.md                # Your preferences and environment
│   └── aida-core/
│       └── SKILL.md                # AIDA management knowledge
├── settings.json                   # Claude Code settings
└── plugins/
    └── aida-core/             # Plugin files
        ├── skills/                 # /aida skill definitions
        ├── scripts/                # Python utilities
        └── templates/              # Jinja2 templates
```

### User Context Skill

**Location**: `~/.claude/skills/user-context/SKILL.md`

**Content** (example):

```markdown
---
name: user-context
description: User's environment, preferences, and coding standards
---

# User Context

This skill provides Claude with your personal coding standards,
tools, and preferences that apply across all projects.

## Environment

- OS: macOS
- Git user: developer@example.com
- GitHub: @developer

## Coding Standards

I follow these coding standards and style guides:
- PEP 8 for Python
- Airbnb JavaScript Style Guide
- ESLint with recommended config

## Primary Tools

My primary development tools:
- Languages: Python, JavaScript, TypeScript
- Frameworks: Django, React, Next.js
- Editor: VS Code
- Version Control: Git, GitHub
- Infrastructure: Docker, AWS
```

**Purpose**: Global preferences and environment context applied to all projects

### Settings.json Updates

**Location**: `~/.claude/settings.json`

AIDA adds/updates:

```json
{
  "enabledPlugins": {
    "aida-core": true
  }
}
```

**Note**: Existing settings are preserved. AIDA only adds its plugin entry.

## Verification

After installation, verify everything works:

### Step 1: Check Status

```bash
/aida status
```

**Expected output:**

```text
AIDA Status

Installation: ✓ Installed
  Location: ~/.claude/skills/
  Python: 3.11.5
  gh CLI: 2.40.0

Personal Skills:
  ✓ user-context
  ✓ aida-core

Project Configuration: Not configured
  Run /aida config in a project directory

Settings: ✓ Configured
  Plugin enabled: aida-core
```

### Step 2: Verify Skill Files

```bash
# Check user context exists
ls -la ~/.claude/skills/user-context/

# Should show:
# SKILL.md
```

### Step 3: Test a Skill

```bash
/aida help
```

**Expected output:**

```text
AIDA - Agentic Intelligence Digital Assistant

Available commands:
  /aida help               Show this help message
  /aida config            Global setup (run once)
  /aida config          Project setup (per project)
  [... etc ...]

For detailed help: /aida help
```

### Step 4: Run Health Check

```bash
/aida doctor
```

**Expected output:**

```text
Running AIDA health check...

Requirements:
  ✓ Python 3.11.5 (>= 3.8 required)
  ✓ gh CLI 2.40.0

Directories:
  ✓ ~/.claude/ exists and writable
  ✓ ~/.claude/skills/ exists

Skills:
  ✓ user-context (valid syntax)
  ✓ aida-core (valid syntax)

Settings:
  ✓ ~/.claude/settings.json valid
  ✓ Plugin aida-core enabled

All checks passed! ✓
```

## Troubleshooting

### Installation Fails

#### Error: "Python version not supported"

**Cause**: Python < 3.8 installed

**Solution**:

```bash
# Check version
python3 --version

# Upgrade Python (macOS)
brew upgrade python3

# Upgrade Python (Linux)
sudo apt update && sudo apt upgrade python3

# Try again
/aida config
```

#### Error: "gh CLI not found"

**Cause**: GitHub CLI not installed

**Solution**:

```bash
# Install gh (macOS)
brew install gh

# Install gh (Linux)
# See https://cli.github.com/

# Authenticate
gh auth login

# Try again
/aida config
```

#### Error: "Permission denied: ~/.claude/"

**Cause**: Insufficient permissions on Claude directory

**Solution**:

```bash
# Check permissions
ls -la ~/.claude/

# Fix permissions
chmod -R u+w ~/.claude/

# Verify fix
/aida doctor
```

### Questionnaire Issues

#### Accidentally Canceled (Ctrl+C)

**Solution**: Just run `/aida config` again. No partial state is saved.

#### Want to Change Answers

**Solution**: Run `/aida config` again and confirm overwrite when prompted.

#### Unsure How to Answer

**Tip**: Use the defaults! You can always reinstall later to change answers.

Press Enter without typing to use the default value shown in `[brackets]`.

### Verification Fails

#### Skills Don't Appear in `/aida skill list`

**Possible causes:**

1. Installation didn't complete
2. Syntax errors in SKILL.md
3. Wrong directory permissions

**Solution**:

```bash
# Run health check
/aida doctor

# Look for errors, follow suggestions

# If needed, reinstall
/aida config
```

#### `/aida` commands not recognized

**Possible cause**: Plugin not enabled

**Solution**:

```bash
# Check plugin status
/plugin list

# Should show:
# aida-core (enabled)

# If not enabled
/plugin enable aida-core
```

### Getting More Help

If problems persist:

1. **Run diagnostics**: `/aida doctor` (shows detailed errors)
2. **Check status**: `/aida status` (shows configuration)
3. **Report bug**: `/aida bug` (opens GitHub issue with auto-filled environment)
4. **Ask for help**: `/aida feedback` (general help request)

## Next Steps

Congratulations! AIDA is now installed. Here's what to do next:

### 1. Configure for a Project

Navigate to any project and run:

```bash
cd your-project/
/aida config
```

This creates project-specific skills. See [Configuration Guide](USER_GUIDE_CONFIGURE.md).

### 2. Explore Commands

Try these commands to explore AIDA:

```bash
/aida skill list         # See all your skills
/aida agent list         # See available agents
```

### 3. Create Custom Skills

Make AIDA truly yours:

```bash
/aida skill create       # Interactive wizard
```

See [Development Guide](DEVELOPMENT.md) for creating skills.

### 4. Learn the Architecture

Understand how AIDA works:

- [Architecture Documentation](ARCHITECTURE.md)
- [API Reference](API.md)

### 5. Join the Community

- **GitHub**: [aida-core-plugin](https://github.com/aida-core/aida-core-plugin)
- **Issues**: Report bugs and request features
- **Discussions**: Share skills and get help

---

**Questions?** Run `/aida feedback` or see [Troubleshooting](#troubleshooting)

**Ready for project setup?** → [Configuration Guide](USER_GUIDE_CONFIGURE.md)
