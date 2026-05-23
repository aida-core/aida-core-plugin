---
type: reference
title: Plugin Scaffolding Workflow
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Plugin Scaffolding Workflow

Detailed reference for the plugin-manager scaffolding process.

## End-to-End Flow

1. User invokes `/aida plugin scaffold`
2. Dispatch routes to `plugin-manager` skill
3. Skill runs `scaffold.py --get-questions` with any provided context
4. Script infers git config, checks gh availability, returns questions
5. Skill presents questions to user, collects answers
6. Skill runs `scaffold.py --execute` with full context
7. Script creates project, returns result with file list and next steps
8. If `create_github_repo` is true, skill runs `gh repo create`

## Template Variables

All templates receive these variables:

| Variable | Type | Description |
| --- | --- | --- |
| `plugin_name` | string | Kebab-case name |
| `plugin_display_name` | string | Title Case display name |
| `description` | string | 10-500 char description |
| `version` | string | Semver (default "0.1.0") |
| `author_name` | string | From git config or input |
| `author_email` | string | From git config or input |
| `license_id` | string | SPDX identifier |
| `license_text` | string | Full license body |
| `year` | string | Current year |
| `language` | string | "python" or "typescript" |
| `script_extension` | string | ".py" or ".ts" |
| `python_version` | string | Python version, format "X.Y" (default: "3.11") |
| `node_version` | string | Node.js major version (default: "22") |
| `keywords` | list | Marketplace tags |
| `repository_url` | string | GitHub URL or "" |
| `include_agent_stub` | bool | Include agent stub |
| `include_skill_stub` | bool | Include skill stub |
| `timestamp` | string | ISO 8601 UTC |
| `generator_version` | string | aida-core version |

## Language-Specific Differences

### Python

- `pyproject.toml` with ruff and pytest configuration
- `.python-version` file
- `tests/conftest.py` with shared fixtures
- Makefile targets: `lint-py`, `test` (pytest), `format` (ruff)
- `.gitignore` includes `__pycache__/`, `venv/`, `.pytest_cache/`

### TypeScript

- `package.json` with ESM modules
- `tsconfig.json` with strict mode
- `eslint.config.mjs` with flat config
- `.prettierrc.json` for formatting
- `.nvmrc` for Node.js version
- `vitest.config.ts` for testing
- Makefile targets: `lint-ts`, `test` (vitest), `build` (tsc), `format` (prettier)
- `.gitignore` includes `node_modules/`, `dist/`, `coverage/`

## Gitignore Policy

The scaffolded `.gitignore` is composed from **slim, flavor-specific
fragments**, not a universal kitchen-sink template. The intent is to
ignore noise without silently swallowing legitimate files.

### Fragment composition

`assemble_gitignore(target, language, …)` concatenates two fragments:

| Fragment | Path | Scope |
| --- | --- | --- |
| Shared | `shared/gitignore-shared.jinja2` | OS files, IDE/editor scratch, `.claude/settings.local.json` |
| Language | `<lang>/gitignore-<lang>.jinja2` | Patterns specific to the toolchain (Python venv, Node `dist/`, etc.) |

Each fragment is intentionally small — typically 10–16 patterns. New
patterns should be **bounded** (directory suffix `/`, file extension
`.<ext>`, anchored path), not name-based wildcards.

### Forbidden patterns

The following are banned by `test_gitignore_avoids_broad_file_name_blanket_patterns`:

| Pattern | Why it's banned |
| --- | --- |
| `lib/` | Swallows AWS CDK / Node `lib/` directories that contain real code |
| `*secrets*` | Matches legitimate filenames like `SecretsStack.ts` (manages secrets, doesn't contain them) |
| `*credentials*` | Matches legitimate filenames like `CredentialsStack.ts` |
| `*.key` | Would swallow JWT / crypto sample fixtures in tests |
| `*.pem` | Would swallow PEM fixtures in tests |
| `*.env*` | Would swallow `.env.example` / `.env.sample` which are committable |

### Size budget

The assembled `.gitignore` for any single language must stay under 50
lines (enforced by `test_gitignore_stays_slim`). If a language needs
more patterns than the budget allows, **add a new flavor fragment**
rather than appending to an existing one — that's the slim-fragment
design.

### Background

This policy exists because a kitchen-sink universal `.gitignore`
silently dropped 11 files from a CDK repo migration (see #91). The
fragments are small, predictable, and auditable: anything that lands
in `.gitignore` should be traceable to a specific fragment and
rationale.

## Error Handling

| Error | Cause | Resolution |
| --- | --- | --- |
| "Target directory is not empty" | Existing files at path | Choose a different path |
| "Parent directory does not exist" | Invalid path | Create parent or choose another |
| "Invalid plugin name" | Fails validation | Use kebab-case, 2-50 chars |
| "Invalid description" | Too short/long | Use 10-500 characters |
| "Unsupported license" | Unknown SPDX ID | Choose from supported list |

## Post-Scaffold Steps

After scaffolding completes:

1. `cd` into the new project directory
2. Install dependencies (`pip install -e ".[dev]"` or `npm install`)
3. Run `make lint` to verify the project structure
4. Run `make test` to verify test setup
5. Optionally create GitHub repo with `gh repo create`
6. Start building agents and skills
