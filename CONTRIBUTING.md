---
type: documentation
title: "Contributing to AIDA Core Plugin"
description: "Development setup, coding standards, PR process, and the project's AI attribution policy."
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Contributing to AIDA Core Plugin

Thanks for your interest in contributing. This guide gets you set
up and walks through the project conventions.

Please review the [Code of Conduct](CODE_OF_CONDUCT.md) before
participating.

## Prerequisites

- **Claude Code** — latest version (this is a Claude Code plugin)
- **Python 3.9+** (CI tests against 3.9 / 3.11 / 3.12)
- **Node.js 22+** (for `markdownlint-cli` invoked by `make lint`)
- **Git** + **gh CLI** (for PR / issue workflows)

## Setting Up Your Development Environment

```bash
# Fork on GitHub, then:
git clone https://github.com/<your-username>/aida-core-plugin.git
cd aida-core-plugin

# AIDA tooling lives in a managed venv at ~/.aida/venv/
make install      # creates the venv, installs runtime + dev deps

# Verify the environment
make lint         # ruff + yamllint + markdownlint + REUSE
make test         # pytest
```

Most contributors don't need to run pre-commit locally — CI runs the
same checks `make lint` runs. But a `.pre-commit-config.yaml` is on
the roadmap (#53) if you want hooks.

## Repo Layout

```text
agents/                          # Subagent definitions (WHO)
skills/                          # Skill definitions (HOW)
  ├── aida/                      # Main dispatcher skill
  ├── agent-manager/             # Agent CRUD
  ├── claude-md-manager/         # CLAUDE.md CRUD
  ├── expert-registry/           # (deprecated — see ADR-012)
  ├── hook-manager/              # Hook CRUD in settings.json
  ├── memento/                   # Session persistence
  ├── permissions/               # Permission CRUD
  ├── plugin-manager/            # Plugin CRUD + scaffold
  └── skill-manager/             # Skill CRUD
scripts/shared/                  # Shared Python utilities
tests/                           # pytest tests
docs/                            # User-facing docs
docs/architecture/adr/           # Architecture Decision Records
.claude-plugin/                  # Plugin manifest + marketplace listing
```

See [`docs/EXTENSION_FRAMEWORK.md`](docs/EXTENSION_FRAMEWORK.md) for
the conceptual model and
[`docs/FRONTMATTER_SCHEMA.md`](docs/FRONTMATTER_SCHEMA.md) for the
reusable frontmatter contract.

## Development Workflow

1. **Branch from main**:

   ```bash
   git checkout -b feat/short-description main
   ```

2. **Make changes** — code, tests, docs. Most behavioral changes need
   a test; pure docs / refactors don't.
3. **Run the local checks**:

   ```bash
   make lint
   make test
   ```

4. **Bump the version** in `.claude-plugin/plugin.json` and add a
   corresponding entry to `CHANGELOG.md`. CI enforces both via the
   `version-check` workflow.
5. **Push and open a PR** against `main`. Fill out the PR template.

## Code Standards

### Python

- **`ruff`** for linting and formatting. Run `ruff check skills/ tests/`
  locally; CI gates on it via `make lint-py`.
- **Type hints** for public functions; `from __future__ import annotations`
  for files that use PEP-604 union syntax (`dict | None`) so they
  stay compatible with Python 3.9.
- **`if __name__ == "__main__":`** pattern for scripts in skills.

### Markdown

- Frontmatter required on every markdown file. See
  [`.frontmatter-schema.json`](.frontmatter-schema.json) and
  [`docs/FRONTMATTER_SCHEMA.md`](docs/FRONTMATTER_SCHEMA.md).
- `markdownlint` config at `.markdownlint.json` — rules are
  deliberately relaxed for tight skill / agent prose. See the
  "Lint Policy" section in
  [`skills/plugin-manager/references/scaffolding-workflow.md`](skills/plugin-manager/references/scaffolding-workflow.md)
  for why specific rules are off.
- Line length: 120 chars.

### YAML

- `yamllint` config at `.yamllint.yml` extends `default`.
- Every YAML file starts with `---` (document-start marker required).
- Sequences are indented inside their parent key (`indent-sequences: true`).

### REUSE / SPDX

- Every hand-authored source file carries SPDX headers per
  [REUSE Specification](https://reuse.software/spec/). `reuse lint`
  runs in CI; the repo must stay 100% compliant.
- See [`docs/FRONTMATTER_SCHEMA.md`](docs/FRONTMATTER_SCHEMA.md) for
  per-language header examples.

### Tests

- Tests live in `tests/unit/` (mostly) and `tests/integration/`.
- Run all: `make test`. Single file: `~/.aida/venv/bin/pytest tests/unit/test_foo.py -v`.
- Behavioral changes need a regression test; docs / annotation
  changes don't.

## Commit Messages

This project follows
[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):

```text
<type>: <short summary>

<optional body>

<optional footer(s)>
```

Common types:

| Type       | Purpose                                       |
| ---------- | --------------------------------------------- |
| `feat`     | New feature                                   |
| `fix`      | Bug fix                                       |
| `docs`     | Documentation only                            |
| `chore`    | Build, CI, tooling, repo-hygiene              |
| `refactor` | Code restructuring, no behavior change        |
| `test`     | Adding or updating tests                      |
| `style`    | Formatting, no logic change                   |

## AI Tools and Attribution

We welcome contributions made with the help of AI coding tools.
However, **do not include AI attribution in commits or pull
requests**:

- No `Co-Authored-By` trailers referencing AI tools
- No "Generated with", "Powered by", or "Assisted by" text in PR
  descriptions

CI will automatically reject PRs that contain these patterns (see
the `check-attribution` workflow).

**This is not an anti-AI policy.** It is a copyright protection
measure. This project is licensed under MPL-2.0, where clear
copyright ownership matters for license enforcement. AI
co-authorship trailers create legal ambiguity about who holds
copyright over the contributed code. By keeping attribution
exclusively with human contributors, we maintain unambiguous
ownership and protect the integrity of the license.

You are the author of your contributions, regardless of what tools
you used to write them.

## Pull Request Process

1. Fill out the PR template (Summary + Test plan).
2. Ensure **CI is green** — all jobs (lint, unit-test 3.9 / 3.11 /
   3.12, integration-test, check-attribution, version-check) must
   pass.
3. Version bump + matching CHANGELOG entry is required (enforced
   by `version-check`).
4. Keep PRs focused — prefer small, incremental changes over large
   sweeping ones. The PR title becomes the commit subject on
   squash-merge.

## Substantive Contributors

After your first merged PR, you'll be added to [`AUTHORS`](AUTHORS) —
the authoritative roster behind the collective copyright holder
"The AIDA Core Authors" referenced in SPDX headers throughout the
repo.

## Questions?

- **Bugs / features**:
  [open an issue](https://github.com/aida-core/aida-core-plugin/issues)
- **Maintainer contact**: see [`MAINTAINERS.md`](MAINTAINERS.md)
- **Security disclosures**: see [`SECURITY.md`](SECURITY.md)
