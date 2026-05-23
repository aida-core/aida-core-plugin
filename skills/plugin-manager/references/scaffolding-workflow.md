---
type: reference
title: Plugin Scaffolding Workflow
description: "Two-phase plugin scaffolding workflow — questions, execution, template variables, language-specific files, error handling, and the gitignore + lint + bootstrap-ordering policies."
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

## Lint Policy

The scaffolded plugin ships with `markdownlint`, `yamllint`, and
language-specific linters (`ruff` for Python, `eslint`/`prettier` for
TypeScript). The defaults are pre-tuned so a fresh scaffold lands
**green on first `make lint`** — see #82 and #92 for the failure
modes that motivated each choice.

### markdownlint defaults

`.markdownlint.json` disables the rules that flag valid AIDA-skill
prose (template placeholders, tight technical text, footer patterns).
The full set:

| Rule | Setting | Why |
| --- | --- | --- |
| `MD013` | line_length 120, off for headings/code/tables | Long, descriptive prose in skill/agent files |
| `MD022` | false | Tight knowledge docs omit blanks around headings |
| `MD024` | `siblings_only: true` | Same heading text under different parents is fine |
| `MD025` | false | Conflicts with frontmatter `title:` plus `# Heading` |
| `MD032` | false | Tight technical lists without surrounding blanks |
| `MD033` | false | Skill stubs use `<PRD>`, `<ticket>`, `<figma-url>` placeholders |
| `MD034` | false | Bare URLs in references are intentional |
| `MD036` | false | `**Last updated:** …` footer is convention, not heading |
| `MD040` | false | Plain output dumps without language tags |
| `MD041` | false | First line is frontmatter, not H1 |
| `MD046` | `style: fenced` | Consistent code-block style |

If you add a rule back, add a comment in the JSON explaining what
real content it caught — `default: true` plus a small disable list
is intentional friction against re-enabling rules that flag
non-problems.

### yamllint defaults

`.yamllint.yml` extends the default ruleset with:

- `ignore:` block excluding `node_modules/`, `dist/`, `coverage/`,
  `build/`, `__pycache__/`, `.venv/`, `venv/`, `.pytest_cache/`,
  `.ruff_cache/`. Without this, `yamllint -c .yamllint.yml .` walks
  third-party YAML in `node_modules/` and emits hundreds of failures
  (#82 bug 2)
- `line-length` raised to 120
- `truthy` accepts the common explicit values; `check-keys: false`
  so GitHub Actions `on:` (parses as truthy) doesn't trip the rule
- `document-start: present: true` is **kept on** — AIDA's own
  generators (#81/#97 fix in 1.5.3) always emit a `---` marker, so
  consumers should expect one

### markdownlint invocation

The Makefile uses `npx --yes markdownlint-cli --config .markdownlint.json`:

- `npx --yes` resolves to the version in `devDependencies` for
  TypeScript scaffolds (no global install needed after
  `npm install`); on Python scaffolds, `--yes` suppresses the
  install prompt so CI doesn't hang on first run
- `--config` is passed explicitly because markdownlint-cli's
  auto-discovery can silently miss the config when invoked through
  `npx` from a non-package-root working directory

### Python scaffold CI

Python plugin CI installs Node.js via `actions/setup-node@v4` even
though there's no JavaScript in the project. This is so `make lint`
(which calls `lint-md` → `npx markdownlint-cli`) works without a
manual install step.

## Bootstrap Ordering With Branch Protection

The scaffold creates a local project and (optionally) runs
`gh repo create` to publish it. It **does not** configure branch
protection — that's left to the user / org policy. If your project
uses required status checks on `main`, the order of operations
matters (#93).

### The mistake to avoid

If you set up branch protection with required status checks
**before** CI has ever run, the first PR can never merge:

- Branch protection demands the named checks pass
- The named checks don't exist yet (no run on this repo)
- "Required status check 'lint' is expected" — perpetually expected

### Recommended flow

```text
1. /aida plugin scaffold ...                # local files + git init
2. (cd into target; review files locally)
3. gh repo create <name> --public --source=. --push
4. Wait for the first CI run (push to main triggers it)
5. Confirm CI is green
6. (Optionally) gh pr create ... → first feature PR
7. Confirm that PR's CI is green
8. NOW enable branch protection with required status checks
   pointing at the check names that just passed
```

Doing protect-then-bootstrap leaves the first PR stuck. Doing
bootstrap-then-protect lets the protection rule attach to a known
set of check names.

### Why we don't automate this

Branch protection is org-policy territory — every team's required
checks, review counts, and merge strategies differ. The scaffold
ships clean templates and an out-of-the-box-green CI workflow;
applying protection rules on top is a separate, opinionated step.

If you want a one-shot helper, the canonical `gh` recipe is:

```bash
gh api -X PUT "repos/{owner}/{repo}/branches/main/protection" \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["lint", "test"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null
}
JSON
```

Run that *after* CI has passed at least once so the check names
resolve.

### README and the `--add-readme` trap

`gh repo create --add-readme` autogenerates a README that fails
`MD022` (no blank line between title and body). The AIDA scaffold
sidesteps this by writing its own `README.md` template with proper
heading spacing — we never call `--add-readme`. If you're combining
scaffold output with other tooling that does, normalize the
generated README before pushing or expect lint failures on the
first PR.

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
