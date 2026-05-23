---
type: changelog
title: "AIDA Core Plugin Changelog"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Changelog

All notable changes to AIDA Core Plugin.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.20] - 2026-05-23

### Added

- **`MAINTAINERS.md`** at the repo root (ADR-0015, #90). Lists
  the current active maintainer roster, distinct from the broader
  contributor list in `AUTHORS`. Includes a "how to reach us"
  section and a brief note on becoming a maintainer.
- **`.github/dependabot.yml`** (ADR-0017, #90). Weekly updates
  for both Python (`pip`) and `github-actions`, anchored to
  Monday 09:00 America/New_York with a 5-PR-at-once cap and
  `dependencies` / `python` / `github-actions` labels for easy
  triage.

### Notes

- Closes the Splash marketplace compliance audit (ADR-0015 +
  ADR-0017) — once this lands, the plugin can be removed from
  the grandfather lists in `splash-ai-marketplace`'s validator
- Pure repo-hygiene addition; no runtime behavior changes
- Pairs naturally with #53 if/when that broader hardening
  checklist gets picked up (`SECURITY.md`, `CONTRIBUTING.md`,
  pre-commit, etc.)

---

## [1.5.19] - 2026-05-23

### Added

- **Project-context schema versioning + migration framework**
  (#39). The project-context YAML now carries a `schema_version`
  field (currently `1.0.0`), separate from the AIDA app version:
  - `PROJECT_CONTEXT_SCHEMA_VERSION = "1.0.0"` constant in
    `utils/project_context.py`. Bump major for breaking changes,
    minor for additive fields, patch for clarifications
  - `_MIGRATIONS` registry — `Dict[str, Callable]` mapping
    from-version to a migrator function. Empty today (schema is
    fresh at 1.0.0), but the framework is in place so future
    schema bumps can register migrators and the loader walks
    them in order
  - `migrate_to_current(data)` — public entry point. At current
    version: stamps `schema_version`. Older: walks migrations
    forward. Newer: logs a warning and returns as-is (best-effort
    forward compat). Missing migration in chain: warns and stops
    rather than crashing
  - `load_project_context()` now calls `migrate_to_current()`
    automatically, so consumers always see a current-version
    dict. The next `write_project_context()` persists the
    upgrade

### Changed

- **Project context now stamps `schema_version`, not `version`**.
  The previous `version: AIDA_VERSION` stamp conflated app
  version with schema version (#39's core bug — docs said one
  thing, code stamped another). New configs get
  `schema_version: "1.0.0"`. Legacy files with a `version` field
  are treated as schema 1.0.0 (the shape didn't actually
  change), and the original `version` field is preserved
  in-memory + on disk for backward compat
- `validate.py`'s expected top-level keys now require
  `schema_version` instead of `version`. Since
  `load_project_context()` stamps `schema_version` on read, this
  passes for all existing configs after one round-trip

### Notes

- This is foundational work — no immediate user-facing behavior
  change. Sets up safe future schema evolution
- 7 new tests in `tests/unit/test_project_context_split.py::TestSchemaVersioning`
  cover the migration framework: stamping current, preserving
  current, warning on newer, empty-dict skip, legacy-version
  treatment, and the end-to-end write-then-read round-trip
- Two existing tests
  (`test_legacy_single_file_returns_as_is` renamed to
  `test_legacy_single_file_stamps_schema_version`,
  `test_round_trip_via_disk`) updated to assert the new
  schema-stamping contract rather than strict equality
- Closes **Config & Schema Quality** milestone (6/6)
- Milestone: `Config & Schema Quality`

---

## [1.5.18] - 2026-05-23

### Added

- **`/aida config validate` command** (#87) — non-interactive
  health check for an AIDA-configured project. Three checks:
  - `global_install`: `~/.claude/aida.yml` exists
  - `project_marker`: `.claude/aida.yml` exists, parses as YAML,
    has `version` + `project` mapping
  - `project_context`: `.claude/aida-project-context.yml` (+
    optional `.local` overlay) parses, has the expected
    top-level keys, and sub-sections (`vcs`, `files`,
    `preferences`) are mappings

  Exits **0 on success, 1 on failure** — CI-gateable. Pass
  `--json` for a machine-consumable report (suitable for piping
  into a workflow step that posts a PR comment).
- **`skills/aida/scripts/validate.py`** — the validator
  implementation. Uses the same `load_project_context()` loader
  as the rest of AIDA so the validator can never disagree with
  what consumers actually read
- **`skills/aida/references/validate.md`** — workflow docs for
  the new command (loaded by SKILL.md when `/aida config validate`
  is invoked)
- **`tests/unit/test_validate.py`** — 7 cases covering happy
  path, each missing-file failure, malformed YAML, missing
  expected keys, and wrong section types

### Changed

- `skills/aida/SKILL.md` routes `config validate` to the new
  script, distinct from interactive `config`. The help text
  surfaces `/aida config validate` as a separate command

### Notes

- Does not yet check for drift between
  `.claude/aida-project-context.yml` and the rendered
  `project-context/SKILL.md`. Schema-version migration also still
  belongs to #39. Both are noted as out-of-scope follow-ups in
  the new docs
- Milestone: `Config & Schema Quality` (5/6 closed after merge)

---

## [1.5.17] - 2026-05-23

### Added

- **Project-context SKILL.md references existing CLAUDE.md /
  knowledge files** (#84). Previously, running `/aida config` on a
  project with a rich hand-written `CLAUDE.md` and a `knowledge/`
  directory still generated a SKILL.md that re-claimed "no specific
  conventions documented" — confusing on projects where the
  conventions were obviously written down somewhere else. Now the
  generator detects existing context files and points at them:
  - **CLAUDE.md callout** near the top of the rendered SKILL.md:
    "Authoritative rules live in `<path>`. When that file and this
    auto-generated skill conflict, follow the CLAUDE.md."
  - **Project Conventions section** points at the CLAUDE.md when
    `project_conventions` is otherwise empty, instead of the
    generic fallback text
  - **Knowledge Index / Knowledge Directory** section appears
    when `knowledge/index.md`, `knowledge/README.md`, or
    `docs/index.md` is detected
- **`_detect_existing_context`** helper in `configure.py` returns
  six new template variables (`has_claude_md`, `claude_md_path`,
  `has_knowledge_dir`, `knowledge_dir`, `has_knowledge_index`,
  `knowledge_index_path`). Search order: project-root CLAUDE.md
  takes precedence over `.claude/CLAUDE.md`; knowledge/index.md
  beats knowledge/README.md beats docs/index.md
- Regression tests:
  - `TestDetectExistingContext` (7 cases) in
    `tests/unit/test_utils.py` — covers the detection precedence
    and fallbacks
  - `TestProjectContextReferencesExistingFiles` (6 cases) in
    `tests/unit/test_project_context_template.py` — covers the
    template's rendering of references and the no-CLAUDE.md
    fallback (no regression on existing behavior)

### Notes

- Pairs with #86 (1.5.16) — together they make the auto-generated
  SKILL.md actually useful instead of a noisy "Unknown / not
  documented" stub
- Milestone: `Config & Schema Quality` (4/6 closed after merge)

---

## [1.5.16] - 2026-05-23

### Added

- **Language-family fallback for `detect_project_type`** (#86).
  When a project doesn't match any of the framework-specific
  signatures (React / Next / Express / Django / Flask / FastAPI /
  console_scripts / library), the inference now scans for
  canonical manifest files and returns a useful language string:
  - `package.json` + `tsconfig.json` → `Node/TypeScript`
  - `package.json` (no tsconfig) → `Node/JavaScript`
  - `pyproject.toml` → `Python` (pyproject takes precedence over
    `setup.py` / `requirements.txt` — no double-counting)
  - `setup.py` or `requirements.txt` (no pyproject) → `Python`
  - `Cargo.toml` → `Rust`
  - `go.mod` → `Go`
  - `Gemfile` → `Ruby`
  - `composer.json` → `PHP`

  Multi-language projects return a sorted `+`-joined string (e.g.,
  `"Node/TypeScript + Python"`), deterministic for testing.
  Framework-specific detection still wins over language-family
  fallback — a React project returns `"Web application
  (frontend)"`, not `"Node/TypeScript"`. Previously these
  multi-language repos returned `None`, which surfaced as
  `"Unknown"` in the auto-generated SKILL.md and led to confusing
  "Project Type: Unknown" claims on projects the author clearly
  knew the type of

### Notes

- New `TestDetectProjectType` (8 cases) covers each ecosystem,
  the multi-language repro case from #86, the empty-project None
  return, and the framework-detection precedence
- Milestone: `Config & Schema Quality`

---

## [1.5.15] - 2026-05-23

### Added

- **`description` is now flagged "recommended"** on
  documentation-flavored frontmatter types (`adr`, `documentation`,
  `guide`, `reference`, `readme`) via per-branch JSON Schema
  `description` annotations in `.frontmatter-schema.json`. Not
  enforced by validation — JSON Schema has no native "recommended"
  keyword — so existing files without `description` still pass,
  but knowledge indexes and search tooling can now read the
  schema's intent (#89)
- **"Recommended fields" section** in
  `docs/FRONTMATTER_SCHEMA.md` explains the
  required-vs-recommended split, shows the well-formed shape, and
  gives marketplace-validator guidance ("warn, don't fail")
- **Description fields added to 15 doc-flavored files we own**
  (lead-by-example dogfood pass): 11 ADRs, 2 user guides,
  `scaffolding-workflow.md`, and `CLAUDE.md`. Each gets a
  one-sentence summary suitable for indexing

### Notes

- The 5 remaining files without `description` are historical
  artifacts in `.issues/completed/` and `docs/superpowers/` —
  left as frozen snapshots intentionally
- Pure docs + schema-annotation change; no runtime behavior
  changes
- Milestone: `Config & Schema Quality`

---

## [1.5.14] - 2026-05-23

### Added

- **`docs/FRONTMATTER_SCHEMA.md`** documenting `.frontmatter-schema.json`
  as a reusable contract for downstream plugins and marketplaces
  (#88). Covers: the 10 supported `type` values and their
  required fields, two consumption patterns (vendor + pin via
  `curl`, or `$ref` the tagged raw URL), the type-enum expansion
  policy (how to propose a new type vs add custom fields), and
  the pain pattern that motivated the docs (a downstream wrote a
  duplicate schema and spent ~2h discovering AIDA Core already
  shipped the right one)
- **README link** to the new docs page from the Reference section

### Notes

- The new docs page self-validates: its own frontmatter (`type:
  reference`, `title`, `description`) passes the AIDA schema
- Downstream consumers can pin against `v1.5.14` immediately;
  earlier tagged URLs also work, just with the older type set
- Milestone: `Config & Schema Quality`

---

## [1.5.13] - 2026-05-23

### Added

- **Scaffold detects existing AIDA plugins and offers to upgrade.**
  Previously, pointing `/aida plugin scaffold` at a directory that
  already contained `.claude-plugin/plugin.json` failed with
  "Target directory is not empty" — a confusing dead-end (#110).
  Now `get_questions` short-circuits to a single confirmation
  prompt:
  - **Yes, upgrade in place** → routes to the standards-migration
    (`update`) flow, returning its result with
    `upgrade_routed: True` and `operation: "scaffold"` so the
    orchestrator surfaces the right context
  - **No, cancel** → returns a clean "Upgrade declined" message;
    no files touched
  Behaviour for unrelated non-empty directories is unchanged —
  they still surface "Target directory is not empty"
- **`.claude-plugin/aida-scaffold.json` metadata.** Every
  successful scaffold writes a small metadata file recording what
  was scaffolded: `schema_version`, `plugin_name`,
  `generator_version` (read from this plugin's `plugin.json`),
  `language`, `license_id`, `include_agent_stub`,
  `include_skill_stub`, `created_at`, `last_upgraded_at`. This
  pairs with the upgrade-routing flow so re-runs can be precise
- **`is_existing_aida_plugin(target)`** helper in
  `scaffold_ops/context.py` — single source of truth for the
  "this is an AIDA plugin" check (presence of
  `.claude-plugin/plugin.json`)
- **`read_scaffold_metadata(target)`** in `scaffold.py` — reads
  the new metadata file, returns `None` on missing/malformed
  input so callers can fall back to inference

### Changed

- **`/aida plugin update` honors the recorded language** via
  `.claude-plugin/aida-scaffold.json`. Previously
  `_detect_language` inferred from file presence (`pyproject.toml`
  → python, `package.json` → typescript, default python) and
  couldn't distinguish a `language="none"` (skills-only) plugin
  from a Python one. Now metadata wins; filesystem inference is
  the fallback for plugins scaffolded before this metadata
  existed. Closes the #96 reporter's "/aida plugin update
  auto-inferred Python on a markdown-only plugin" experience
  end-to-end
- `_detect_language` now returns `"none"` as a valid value (was
  `"python"` or `"typescript"` only). Invalid metadata values
  (e.g., `"rust"`) fall back to inference rather than propagating

### Notes

- The recorded `generator_version` is read at scaffold time from
  this plugin's own `.claude-plugin/plugin.json` — so it always
  reflects the actual aida-core version that produced the
  scaffold, not a hardcoded constant that can drift
- The metadata file uses `schema_version: 1` so future shape
  changes can be detected
- End-to-end verified four-step flow: scaffold a plugin →
  metadata written → scaffold again at same path → confirmation
  question surfaces → user picks "No" → clean cancel; user picks
  "Yes" → routes to update
- New tests (8) split across `test_scaffold.py` (existing-plugin
  detection + routing + metadata write) and `test_update_scanner.py`
  (metadata-driven `_detect_language` with fallback for invalid /
  malformed metadata)
- Milestone: `Scaffold v2 — usable out of the box` (7/7 closed
  after merge)

---

## [1.5.12] - 2026-05-22

### Added

- **"Bootstrap Ordering With Branch Protection" section** in
  `skills/plugin-manager/references/scaffolding-workflow.md`
  documenting the recommended `scaffold → push → CI green →
  enable protection` flow. The protect-then-bootstrap mistake
  leaves the first PR stuck on a required-status-check that has
  never run. The section explains why we don't automate
  protection (org-policy territory), shows the canonical `gh api`
  recipe, and notes that we never call
  `gh repo create --add-readme` (which produces an MD022-failing
  README). Closes the documentation portion of #93
- **`test_readme_has_blank_line_after_h1`** regression test —
  pins the scaffolded README's MD022-compliant shape so a future
  template tweak can't collapse the spacing between H1 and body.
  Even though MD022 is disabled in the scaffold's markdownlint
  config (since 1.5.8), our own boilerplate should still look
  right. Closes the README-shape portion of #93

### Notes

- Audit found the scaffold's README has been MD022-compliant all
  along — the issue was about `gh repo create --add-readme`'s
  *autogenerated* README, which we don't use
- Branch-protection automation is **not** in this PR. Per the
  audit, that's an opinionated org-policy step better left as a
  documented manual recipe than scaffold-driven default
- Milestone: `Scaffold v2 — usable out of the box`

---

## [1.5.11] - 2026-05-22

### Fixed

- **Scaffold license prompt no longer exceeds the AskUserQuestion
  4-option cap.** The scaffold previously offered all 6 entries in
  `SUPPORTED_LICENSES` (MIT, Apache-2.0, ISC, GPL-3.0, AGPL-3.0,
  UNLICENSED). AskUserQuestion caps `options` at 4 plus the
  always-supplied "Other", so the scaffold prompt was
  undeliverable. New curated `PROMPT_LICENSE_OPTIONS` lists the 4
  most-common values; ISC and AGPL-3.0 remain accepted for
  non-interactive callers. Fixes #111

### Added

- **"Other" SPDX id support in the scaffold.** Picking "Other" in
  the license prompt and typing any well-formed SPDX id
  (`MPL-2.0`, `BSD-3-Clause`, `LGPL-3.0-or-later`, `0BSD`,
  `Unlicense`, …) now works end-to-end. The scaffold writes:
  - A placeholder `LICENSE` at the repo root that names the SPDX id
    and points the author at
    `https://spdx.org/licenses/<id>.html` to paste the canonical
    text
  - `LICENSES/<id>.txt` (REUSE-required) with the same placeholder
  - SPDX-License-Identifier headers in every generated file
    referencing the chosen id
  End-to-end verified on a `MPL-2.0` scaffold: 16/16 files clean
  under `reuse lint`
- `is_valid_license_id(license_id)` validator in
  `skills/plugin-manager/scripts/operations/scaffold_ops/licenses.py`.
  Accepts known LICENSES dict ids, NON_SPDX_PLACEHOLDERS, and any
  string matching the loose SPDX shape `^[A-Za-z0-9.+\-]+$`.
  Rejects empty / whitespace / shell-metacharacter ids
- Regression tests:
  - `tests/unit/test_scaffold_licenses.py::TestIsValidLicenseId`
    (5 cases, including shell-metacharacter defense-in-depth)
  - `tests/unit/test_scaffold_licenses.py::TestGetLicenseTextOther`
    (3 cases pinning the placeholder LICENSE behavior)
  - `tests/unit/test_scaffold.py::TestExecuteCustomLicense`
    (end-to-end `MPL-2.0` scaffold + malformed-id rejection)
  - `tests/unit/test_scaffold_licenses.py::test_prompt_option_cap`
    (asserts `PROMPT_LICENSE_OPTIONS` <= 4)

### Changed

- `tests/unit/test_utils.py::TestConfigureQuestionOptions` now
  scans both `configure.py` and `scaffold.py` for choice questions
  with literal `options: [...]` lists exceeding 4 entries.
  Single source of truth for the #85-family guard

### Notes

- `get_license_text` now raises `ValueError` only for *invalid*
  ids (empty, whitespace, shell metacharacters). Previously it
  raised for any id not in the `LICENSES` dict, which was the bug
  this PR fixes
- The placeholder LICENSE explicitly tells the author where to
  fetch canonical text — better than silently writing nothing
  (the path UNLICENSED takes is different: it gets the
  proprietary all-rights-reserved attribution block)
- Milestone: `Scaffold v2 — usable out of the box`

---

## [1.5.10] - 2026-05-22

### Added

- **`language=none` (skills-only / markdown-only) scaffold flavor.**
  Previously the scaffold defaulted to Python without asking, so
  authors of markdown-only plugins (pure agents + skills + CLAUDE.md)
  got a full Python toolchain that had to be manually ripped out.
  Now an explicit choice — Python / TypeScript / **None** — surfaces
  in the wizard, and picking `none` skips every Python and
  TypeScript toolchain artifact:
  - No `pyproject.toml`, no `.python-version`, no `tests/conftest.py`
  - No `package.json`, no `tsconfig.json`, no `eslint.config.mjs`,
    no `.prettierrc.json`, no `.nvmrc`, no `vitest.config.ts`
  - No language-specific directories (`scripts/`, `tests/`, `src/`)
  - A minimal `Makefile` whose `lint:` aggregate covers only the
    shared markdown / YAML / frontmatter / REUSE targets
  - A minimal `.github/workflows/ci.yml` that installs Python +
    Node just enough to run `reuse lint` and `markdownlint-cli`,
    then runs `make lint`
  - Slim `.gitignore` (shared fragment only — OS / IDE /
    `.claude/settings.local.json`); no language patterns
- New template directory `skills/plugin-manager/templates/scaffold/none/`
  holding `ci.yml.jinja2` and `makefile-none.jinja2`
- `render_none_files` generator in
  `skills/plugin-manager/scripts/operations/scaffold_ops/generators.py`
- Language question prompt reworded so the choice is explicit:
  `"Which language toolchain? ('none' = skills-only, no Python or TypeScript)"`
- `_build_next_steps` skips the `pip install` / `npm install` step
  and the `make test` step for `none` scaffolds

### Changed

- `assemble_gitignore` and `assemble_makefile` switched from
  `if/else` to `if/elif/else` so `language="none"` doesn't fall
  through to the TypeScript fragment

### Notes

- End-to-end verified: scaffolded a fresh `language=none` MIT
  plugin → 16 files created, REUSE 3.3 compliant (13/13 files);
  none of `pyproject.toml`, `package.json`, `tsconfig.json`, or
  the language-specific test directories are present
- Pairs naturally with `/aida plugin update`'s skills-only path —
  once update flows respect the recorded `language=none`
  (tracked separately in #110's design note), the silent-Python
  default is closed end-to-end
- License-prompt option cap exceeded by `SUPPORTED_LICENSES`
  (6 options vs AskUserQuestion's cap of 4) is the same #85
  family bug in a new file — tracked in **#111**
- Fixes #96 (language portion). The license-prompt half is split
  out into #111 because the fix involves a separate design
  decision (how to handle "Other" SPDX ids)
- Milestone: `Scaffold v2 — usable out of the box`

---

## [1.5.9] - 2026-05-22

### Added

- **Scaffolded `CONTRIBUTING.md`** — every newly-scaffolded plugin
  now ships a `CONTRIBUTING.md` that documents the SPDX/REUSE
  convention for downstream plugin authors. The template adapts to
  the plugin's `license_id`:
  - For real SPDX licenses (MIT / MPL-2.0 / Apache-2.0 / …): includes
    a "REUSE compliance" section explaining `LICENSES/<id>.txt`,
    `REUSE.toml`, and `make lint-reuse`
  - For UNLICENSED: skips the REUSE section, explains why
    `SPDX-License-Identifier` lines are suppressed, but still covers
    the `SPDX-FileCopyrightText` convention so authorship stays
    unambiguous
- Header examples for the three styles a contributor needs
  (Markdown, hash-style, slash-style) — wrapped in
  `<!-- REUSE-IgnoreStart --> / <!-- REUSE-IgnoreEnd -->` so the
  example blocks don't trip `reuse lint` in downstream CI
- **`lint-reuse` Makefile target** in the shared makefile header,
  running `reuse lint`. Python scaffold's `lint:` aggregate now
  depends on `lint-reuse`; TypeScript scaffolds leave it as an
  opt-in target (REUSE is a Python tool — the CONTRIBUTING doc
  points TS authors at `fsfe/reuse-action` for CI)
- **`reuse>=4.0`** in Python scaffold's `pyproject.toml` dev
  dependencies — `pip install -e .[dev]` now brings in the CLI so
  `make lint-reuse` works without a separate install
- Regression tests in `tests/unit/test_scaffold_generators.py` and
  `tests/unit/test_scaffold.py`:
  - `test_contributing_md_documents_spdx_convention` — pins the
    required content for non-UNLICENSED scaffolds
  - `test_contributing_md_omits_reuse_for_unlicensed` — pins the
    proprietary-friendly variant
  - `test_python_pyproject_includes_reuse_dev_dep` — pins the dev
    dep
  - `test_python_makefile_runs_lint_reuse` — pins the aggregate
    target dep

### Notes

- End-to-end verified: a freshly-scaffolded MIT plugin is REUSE 3.3
  compliant out of the box (16/16 files, including the new
  `CONTRIBUTING.md`)
- Closes the last checkbox from #73's umbrella ("Plugin scaffolding
  documents the convention for plugin authors") — fixes #100
- Milestone: `Scaffold v2 — usable out of the box`

---

## [1.5.8] - 2026-05-22

### Fixed

- **Scaffolded `lint-md` works on fresh installs** — Makefile now
  invokes `npx --yes markdownlint-cli --config .markdownlint.json`
  instead of bare `markdownlint`. TypeScript scaffolds get
  `markdownlint-cli` in `devDependencies` so `npm install` brings
  it in; Python scaffolds' CI now sets up Node via
  `actions/setup-node@v4` so `npx` can resolve the tool. Previously
  a fresh `make lint` on either flavor failed with
  `markdownlint: No such file or directory`. Fixes #82 (bug 1)
- **`yamllint` no longer scans vendored / generated directories** —
  the scaffolded `.yamllint.yml` now has a top-level `ignore:`
  block excluding `node_modules/`, `dist/`, `coverage/`, `build/`,
  `__pycache__/`, `.venv/`, `venv/`, `.pytest_cache/`,
  `.ruff_cache/`. Previously `yamllint -c .yamllint.yml .` walked
  `node_modules/` and emitted hundreds of failures from
  third-party YAML. Fixes #82 (bug 2)
- **Markdownlint default rules tuned for AIDA prose** — the
  scaffolded `.markdownlint.json` now disables rules that conflict
  with valid skill / agent content: `MD022` (blanks around
  headings), `MD032` (blanks around lists), `MD033` (inline HTML —
  skill stubs use `<PRD>` / `<ticket>` placeholders), `MD034`
  (bare URLs), `MD036` (`**Last updated:** …` footer pattern), and
  `MD040` (fenced code language tags on plain output dumps).
  Previously every scaffolded plugin failed lint on the very first
  push from these rules firing on real prose. Fixes #82 (bug 3)
  and #92

### Added

- **"Lint Policy" section** in
  `skills/plugin-manager/references/scaffolding-workflow.md`
  documenting the markdownlint rule table (with the *why* for each
  disable), the yamllint config choices (including why
  `document-start` stays on — the #81/#97 work in 1.5.3 makes our
  generators emit `---`), and the Python-CI Node setup rationale
- Regression tests in
  `tests/unit/test_scaffold_generators.py::TestRenderSharedFiles`
  and `tests/unit/test_scaffold.py::TestScaffoldedLintBaseline`
  pinning all four fixes at the rendered-output level:
  - yamllint config carries the required `ignore:` paths
  - markdownlint config disables the required rules (`MD022`,
    `MD025`, `MD032`, `MD033`, `MD034`, `MD036`, `MD040`, `MD041`)
  - TypeScript `package.json` includes `markdownlint-cli` devDep
  - Makefile uses `npx --yes markdownlint-cli` + explicit
    `--config`, never bare `markdownlint`
  - Python `ci.yml` includes `actions/setup-node@v4`

### Notes

- Verified end-to-end: scaffolded a Python plugin, added bogus YAML
  inside a simulated `node_modules/`, ran `yamllint -c
  .yamllint.yml .` — exit 0 (the ignore block successfully prunes
  the noise)
- Milestone: `Scaffold v2 — usable out of the box`

---

## [1.5.7] - 2026-05-22

### Added

- **Gitignore policy documentation** — new "Gitignore Policy" section
  in `skills/plugin-manager/references/scaffolding-workflow.md`
  describing the slim-fragment composition (shared + per-language),
  the forbidden patterns list, the 50-line size budget, and the
  background that motivates it (#91)
- **Slimness regression tests** in
  `tests/unit/test_scaffold_generators.py::TestAssembleGitignore`:
  - `test_gitignore_avoids_broad_file_name_blanket_patterns` —
    asserts the assembled `.gitignore` does not contain `lib/`,
    `*secrets*`, `*credentials*`, `*.key`, `*.pem`, or `*.env*` (the
    specific patterns that caused the reporter's 11-file data loss
    in the original #91 incident)
  - `test_gitignore_stays_slim` — caps any language's assembled
    `.gitignore` at 50 lines. If a language needs more, add a new
    fragment rather than expanding an existing one

### Notes

- Audit finding: the AIDA plugin scaffold already met #91's literal
  criteria — `assemble_gitignore` composes slim shared +
  per-language fragments, and the fragments don't contain the broad
  name-based wildcards the issue called out. The reporter's
  incident came from a separate monorepo's universal `.gitignore`,
  not AIDA scaffold output. This release pins the slim design with
  tests and docs so future contributions can't drift toward the
  kitchen-sink shape that caused the original failure
- Adding new flavors beyond `python` / `typescript` (e.g., `cdk`,
  `dbt`, `metabase`, `docs-only`) is out of scope for AIDA's plugin
  scaffold and would belong in a broader scaffolding tool
- Closes the **1.6.0 — Bug fixes** milestone (9/9 issues resolved)

---

## [1.5.6] - 2026-05-22

### Added

- `tests/unit/test_scaffold_generators.py::TestAssembleGitignore::test_gitignore_does_not_blanket_ignore_claude_dir`
  — regression guard for #95. Asserts that the scaffolded
  `.gitignore` contains the narrow exclusion
  `.claude/settings.local.json` and does **not** contain a bare
  `.claude/` line that would shadow `/aida config` outputs (which
  are committable team-shared state). The bug was fixed in PR #62
  (commit `48a882c`) by switching the template from `.claude/` to
  `.claude/settings.local.json`; this test pins the fix.

### Notes

- No behavior change in this release; the underlying bug has been
  fixed since PR #62
- Milestone: `1.6.0 — Bug fixes`

---

## [1.5.5] - 2026-05-22

### Added

- `tests/unit/test_scaffold.py::TestScaffoldedCiYamlParses` —
  regression test that scaffolds a full Python plugin and a full
  TypeScript plugin, then asserts the generated
  `.github/workflows/ci.yml` parses as YAML and that the
  `Set up Python` / `Set up Node` step doesn't mash `name:` and
  `uses:` onto a single line. Closes #74 (the underlying parse error
  was fixed in 1.5.0 by switching the templates from
  `{% raw %}…{% endraw %}` to Jinja-literal `${{ '{{' }}…{{ '}}' }}`,
  but no test pinned the fix — so any future template change in the
  same shape could silently reintroduce it).

### Notes

- No behavior change in this release; the underlying bug has been
  fixed since 1.5.0
- Milestone: `1.6.0 — Bug fixes`

---

## [1.5.4] - 2026-05-22

### Fixed

- `configure.py` `render_aida_project_marker` previously hardcoded
  `plugins = ["aida-workflow-commands"]`, planting a dead reference
  in every generated `.claude/aida.yml` — `aida-workflow-commands`
  isn't a real plugin. The default is now an empty list; projects
  add entries via `/aida config` or by editing the file. Fixes #83
- `configure.py` `get_questions` defined two choice questions with
  more options than `AskUserQuestion` accepts (cap is 4 plus the
  always-supplied "Other"): `branching_model` had 6 options,
  `issue_tracking` had 5. Both are trimmed to 4 mutually-exclusive
  named choices; the reserved "Custom workflow" / "No specific
  model" / unsupported-tracker cases fall through to the built-in
  "Other". Help text updated to point users at "Other" for those
  edge cases. Fixes #85

### Added

- `tests/unit/test_utils.py::TestConfigureQuestionOptions` — scans
  `configure.py` and asserts every choice question has ≤ 4 options.
  Guards against the #85 family regressing when new questions are
  added (since AskUserQuestion's option-cap isn't enforced at
  question-definition time)
- `test_render_aida_project_marker_omits_dead_plugin_reference` —
  regression guard for #83

### Notes

- The reporter on #85 only mentioned `branching_model`; the same
  latent bug was present on `issue_tracking` and is included
- Milestone: `1.6.0 — Bug fixes`

---

## [1.5.3] - 2026-05-22

### Fixed

- `write_yaml` (`skills/aida/scripts/utils/files.py`) now emits a
  `---` document-start marker and indents sequence items inside their
  parent key (the expected yamllint-default shape). Affects
  `.claude/aida-project-context.yml` and `.claude/aida-project-context.local.yml`,
  which previously failed yamllint with `missing document start "---"`
  and `wrong indentation: expected 4 but found 2` on nested sequences
  like `tools.detected`. Implementation: new `_IndentedDumper`
  (subclass of `yaml.SafeDumper`) overrides `increase_indent` to never
  go indentless; `yaml.dump` is invoked with `explicit_start=True` and
  this custom dumper. Fixes #81
- The two string-concat YAML renderers — `render_aida_marker`
  (`skills/aida/scripts/install.py`, writes `~/.claude/aida.yml`) and
  `render_aida_project_marker` (`skills/aida/scripts/configure.py`,
  writes `.claude/aida.yml`) — now prepend `---` to their output. The
  comment header still sits at the top of the file, just after the
  document marker. Fixes #97

### Notes

- All three generated files (`~/.claude/aida.yml`,
  `.claude/aida.yml`, `.claude/aida-project-context.yml`) are now
  clean against both the repo's own `.yamllint.yml` and the strict
  yamllint defaults that scaffolded plugins enforce
- New tests in `tests/unit/test_utils.py`:
  `TestFiles.test_write_yaml_emits_document_start`,
  `test_write_yaml_indents_nested_sequences`,
  `test_write_yaml_roundtrip`,
  `test_write_yaml_top_level_sequence`; plus four
  `TestAidaYmlRenderers` cases for the install / configure renderers
- Milestone: `1.6.0 — Bug fixes`

---

## [1.5.2] - 2026-05-22

### Fixed

- `claude-md-manager` `create --scope user`: the `--responses` payload
  was silently dropped because `execute_create` built `template_vars`
  from project-scope keys only. The user template at
  `templates/claude-md/user.md.jinja2` references `default_behaviors`,
  `patterns`, `tool_config`, `preferred_languages`, and
  `preferred_tools` — none were threaded in, so the file rendered with
  the template's `default()` placeholder text while the operation
  still returned `success:true`. `execute_create` now selects the
  variable set that matches `scope`. Plugin-scope had the same latent
  bug (`plugin_type`, `provides`, `usage`, `config_options`,
  `extension_points` were all unwired) and is fixed in the same
  change. Fixes #98
- `claude-md-manager validate`: project-scope required sections
  (`overview`, `commands`) were applied to every file regardless of
  scope, so a well-formed user-scope or plugin-scope file would fail
  validation with `Missing required sections: overview, commands`.
  Required sections are now keyed by scope — project keeps
  `["overview", "commands"]`, user and plugin have no required
  sections (free-form). `validate_claude_md`, `calculate_audit_score`,
  and `generate_audit_findings` now accept an optional `scope`
  parameter (defaulting to `project` for callers that don't know it).
  `execute_validate`, `execute_optimize`, and `execute_list` thread
  the per-file scope through from `file_info["scope"]`. Fixes #99

### Notes

- Both bugs were originally reported against 1.1.5 but reproduced on
  1.5.1 — the relevant code paths were unchanged between those
  versions
- New tests in `tests/unit/test_claude_md.py` cover all three scopes:
  user-scope create persists `default_behaviors` / `patterns` /
  `tool_config`; plugin-scope create persists `plugin_type` /
  `provides` / `usage` / etc.; user-scope and plugin-scope validate
  succeed without project-style required sections; project-scope
  validate still requires `overview` + `commands`
- Milestone: `1.6.0 — Bug fixes`

---

## [1.5.1] - 2026-04-30

### Added

- `skill-manager`'s `SKILL.md` template now emits an SPDX header
  after the YAML frontmatter, using the same `{{ spdx_md }}`
  variable as `agent-manager`. New skills are reuse-compliant
  by default
- `claude-md-manager`'s project / user / plugin CLAUDE.md
  templates now emit an SPDX header. `execute_create` plumbs
  SPDX context through `spdx_template_variables` so callers can
  override `copyright_holder` / `license_id` / `year`
- `plugin-manager`'s `render_stub_skill` accepts an
  `spdx_context` argument and seeds the skill stub variables
  with it — so `aida plugin scaffold --include-skill-stub` now
  produces a fully reuse-compliant plugin (skill stub included).
  End-to-end smoke test: `reuse lint` is green on a Python
  scaffold with both agent and skill stubs (18/18 files)

### Fixed

- Test helper `_create_skill` in `test_extension_spdx.py` now
  saves and restores `sys.path` plus the cached `operations.*` /
  `_paths` modules around the skill-manager import dance. Without
  this, the helper silently propagated the swapped sys.path[0] to
  every later test in the same session — passing today only because
  no later test cared
- (Folded in from the prior 1.5.0 entry, made explicit here)
  `## [1.4.8]` heading was missing from the CHANGELOG when 1.5.0
  was added, conflating the two versions and tripping markdownlint
  MD024. The split is now in place

### Notes

- `hook-manager` doesn't render hand-authored files (it edits
  `settings.json`), so it has no template to update — closes the
  scaffolding portion of #73
- Refs #73

---

## [1.5.0] - 2026-04-30

### Added

- `scripts/shared/spdx.py` — shared helpers (`resolve_spdx_context`,
  `render_spdx_blocks`, `spdx_template_variables`) used by all
  scaffolding paths to compute the year, copyright holder, license
  id, and pre-formatted comment blocks for Markdown / hash-style /
  slash-style files. Single source of truth so scaffolded artifacts
  carry consistent SPDX headers
- `agent-manager` agent.md template and `plugin-manager`
  scaffolding now emit SPDX `SPDX-FileCopyrightText` and
  `SPDX-License-Identifier` headers in every generated artifact:
  README, CLAUDE.md, AUTHORS, pyproject.toml / package.json
  configs, ci.yml, vitest/eslint/index TS configs, conftest.py,
  Makefile header, yamllint config, agent stubs, and knowledge
  index. Plugins scaffolded after this change are REUSE compliant
  out of the box. Refs #73
- `plugin-manager` scaffolding additionally emits `AUTHORS`,
  `REUSE.toml` (skip categories for JSON / lockfiles / dotfiles),
  and `LICENSES/<id>.txt` (REUSE-required canonical license text)
  for new plugins. Default copyright holder is
  `The {Plugin Display Name} Authors` so file headers stay stable
  as the AUTHORS roster changes
- For UNLICENSED scaffolds, copyright text is still attributed but
  the `SPDX-License-Identifier` line is suppressed (UNLICENSED is
  not a valid SPDX identifier) and `REUSE.toml` is skipped — REUSE
  compliance is not applicable to proprietary projects

### Changed

- `shared/extension_utils.execute_extension_create` seeds Jinja2
  template variables with SPDX context (`year`, `copyright_holder`,
  `license_id`, `spdx_md`, `spdx_hash`, `spdx_slash`). When a
  caller targets a plugin (`location="plugin"` with `plugin_path`),
  the helper auto-detects the holder from
  `<plugin_path>/.claude-plugin/plugin.json` (`name` -> `"The
  {Display Name} Authors"`, `license` -> `license_id`), so an agent
  added to a downstream plugin gets that plugin's attribution, not
  aida-core's. `extra_vars` from the caller still wins
- `plugin-manager`'s `build_template_variables` exposes SPDX
  helpers as template variables so scaffold templates splice in
  `{{ spdx_md }}` / `{{ spdx_hash }}` / `{{ spdx_slash }}`
  rather than building lines themselves
- `shared.spdx` accepts any non-placeholder string as a valid
  SPDX-License-Identifier (deny-list rather than allowlist), so
  obscure-but-real ids like `GPL-3.0-only`, `Unlicense`, `0BSD`,
  `LGPL-3.0-or-later` flow through. Placeholders that suppress
  the License-Identifier line: `UNLICENSED`, `Proprietary`,
  `PROPRIETARY`, `None`, `TBD`, `TODO`, empty string
- `current_year()` honors `SOURCE_DATE_EPOCH` for reproducible
  builds (Nix, Reproducible Builds project)
- Knowledge index (`agents/<name>/knowledge/index.md`) is now
  rendered from `agent/knowledge-index.md.jinja2` instead of an
  inline f-string, so its SPDX header format stays in lock-step
  with everything else
- Scaffolded `ci.yml` (Python + TypeScript) emits the YAML
  document-start `---` marker after the SPDX header, and uses
  Jinja-literal `${{ '{{' }}…{{ '}}' }}` for GitHub Actions
  expressions instead of `{% raw %}…{% endraw %}` (which got
  eaten by `trim_blocks` and concatenated lines)

### Out of scope

- `skill-manager`, `claude-md-manager`, and `hook-manager` create
  flows are unchanged in this PR — that's the next PR on #73.
  Plugins scaffolded with `include_skill_stub=True` will not yet
  have an SPDX-headered `SKILL.md`

---

## [1.4.8] - 2026-04-30

### Added

- SPDX copyright/license headers on every hand-authored source file
  (markdown, Python, YAML, shell, Makefiles, Dockerfiles,
  requirements files): copyright "The AIDA Core Authors" / license
  MPL-2.0. Inserted via the new `scripts/add_spdx_headers.py`
  (idempotent, dry-run by default), which respects skip categories
  from
  [.github/CONTRIBUTING.md#licensing](https://github.com/aida-core/.github/blob/main/CONTRIBUTING.md#licensing):
  JSON, lockfiles, fixtures, scaffolding templates, and `LICENSE`
  itself. Refs #72, #73
- `REUSE.toml` at the repo root licensing the skip categories that
  cannot carry inline headers (JSON, dotfiles, scaffolding templates,
  integration test fixtures). Copyright is attributed to "The AIDA
  Core Authors" with the contributor roster in `AUTHORS`
- `LICENSES/MPL-2.0.txt` (REUSE-required canonical license text;
  `LICENSE` at repo root remains for GitHub display)
- `lint-reuse` Makefile target running `reuse lint`; wired into
  `make lint` so the existing CI lint job becomes the blocking gate
  for REUSE compliance. Project is REUSE 3.3 compliant
- `reuse>=4.0` dev dependency

### Notes

- Scaffolding tools (`plugin-manager`, `agent-manager`,
  `skill-manager`, `claude-md-manager`, `hook-manager`) do **not**
  emit SPDX headers in generated artifacts yet — that's the next PR
  on #73. Templates themselves are intentionally header-free
  (`REUSE.toml` covers them) so the renderer controls the year and
  copyright holder per generated artifact

---

## [1.4.7] - 2026-04-30

### Added

- `AUTHORS` file at repo root listing substantive contributors. Per
  the org-wide convention in
  [.github/CONTRIBUTING.md](https://github.com/aida-core/.github/blob/main/CONTRIBUTING.md#licensing),
  SPDX `SPDX-FileCopyrightText` headers attribute copyright to "The
  AIDA Core Authors" — this file is the authoritative roster of who
  that collective is. Substantive contributors are added on first
  merged PR. Unblocks #72 and the org `.github-private` AUTHORS audit

---

## [1.4.6] - 2026-04-28

### Added

- CI workflow `check-attribution` that scans PR commit messages for
  `Co-Authored-By` trailers referencing AI tools (Claude, Anthropic,
  OpenAI, ChatGPT, Copilot, Gemini, generic `ai`) and fails the build
  if any are found. Copyright clarity concern: AI co-authorship trailers
  create copyright ownership ambiguity. Closes #54

### Changed

- Rewrote commit `4c80c92` (the v1.4.2 backfill commit) to remove a
  pre-existing `Co-Authored-By: Claude` trailer; force-updated `main`
  and re-pointed tags v1.4.2/v1.4.3/v1.4.4/v1.4.5 at their new SHAs.
  GitHub releases follow the moved tags. Old SHAs remain reachable as
  orphans for anyone with stale clones — `git fetch && git reset --hard
  origin/main` will catch them up

---

## [1.4.5] - 2026-04-28

### Changed

- `/aida config` now writes the project context as **two files**: the
  committable `.claude/aida-project-context.yml` (project-level facts:
  vcs.type, languages, tools, preferences, etc.) and the gitignored
  `.claude/aida-project-context.local.yml` (user/environment overlay:
  `project_root`, `vcs.remote_url`, `last_updated`, `config_complete`).
  Fixes #65 — previously the single file mixed both, making it
  impractical to commit
- Phase 2 of `/aida config` appends `.claude/aida-project-context.local.yml`
  to the project's `.gitignore` (if one exists and the entry is missing).
  No `.gitignore` is created — that decision stays with the project
- New `utils.project_context` module (`load_project_context`,
  `write_project_context`, `split_context`, `merge_context`,
  `ensure_gitignore_entry`) for consumers that need to read the merged
  view

### Migration

- Legacy single-file projects continue to read correctly via
  `load_project_context()`. The split happens automatically on the next
  `/aida config` run; no manual migration is required
- Existing committed `aida-project-context.yml` files with stale paths
  from another contributor will be cleaned up on next config run

---

## [1.4.4] - 2026-04-28

### Changed

- User-facing docs updated to reflect the org rename from `oakensoul/`
  to `aida-core/`: `README.md`, `docs/GETTING_STARTED.md`,
  `docs/USER_GUIDE_INSTALL.md`, `docs/DEVELOPMENT.md`,
  `docs/EXAMPLES.md`, ADRs 006 and 008,
  `docs/architecture/c4/container-diagram.md`, and the `feedback.md`
  skill reference. Also normalizes a stale `/Users/oakensoul/...` path
  example in `config-driven-approach.md`
- Historical CHANGELOG link footnotes and `.issues/`/`.github/issues/`
  archives intentionally left untouched (covered by GitHub redirects;
  preserves accurate historical record)

---

## [1.4.3] - 2026-04-28

### Changed

- Updated internal references from `oakensoul/` to `aida-core/` after
  the GitHub org transfer on 2026-04-28: `plugin.json` `repository`
  field, `gh api` calls in `upgrade.py`, `FEEDBACK_REPO` and
  user-visible prompts in `feedback.py`, the scaffolded plugin README
  template, and corresponding test assertions
- User-facing docs and historical changelog/issue archives are
  unchanged (covered by GitHub redirects); a separate docs PR will
  follow

---

## [1.4.2] - 2026-04-24

### Changed

- Backfilled missing release tags and GitHub releases so the published
  release history matches the changelog: tagged `v1.2.1` at the PR #58
  merge commit and `v1.4.1` at the PR #62 merge commit, and published
  GitHub releases for `v1.2.1`, `v1.4.0`, and `v1.4.1`
- Added missing CHANGELOG reference links for 1.1.2–1.1.5, 1.4.1, and
  1.4.2

---

## [1.4.1] - 2026-04-24

### Changed

- Scaffold default license is now `UNLICENSED` instead of `MIT`
- Scaffolded `.gitignore` no longer auto-ignores the entire
  `.claude/` directory; only `.claude/settings.local.json` (the
  one file Claude Code designates as local-only) is ignored

## [1.4.0] - 2026-04-16

### Added

#### Expert Registry Skill

- New `/aida expert` command family for managing expert agents
- Expert activation at project and global scopes with layered
  resolution (project overrides global)
- Named panel compositions for grouped expert workflows
  (code review, plan grading)
- `expert-role` frontmatter field on agents (`core`, `domain`, `qa`)
  for role-based filtering
- Commands: `list`, `configure`, `panels`, `panel create`,
  `panel remove`
- Two-phase API following ADR-010 pattern
- Project config schema bumped to v0.3.0 with `experts` section
- Post-configuration nudge when expert agents are detected
- 19 new unit tests (11 registry, 8 panels)

#### Version & Changelog CI check

- Added `.github/workflows/version-check.yml` that runs on every PR to
  `main` and fails the build if `.claude-plugin/plugin.json` version
  was not bumped or if `CHANGELOG.md` lacks a matching
  `## [<version>] - YYYY-MM-DD` entry
- Enforces semver bump direction (head version must be greater than base)
- Intent: every change — including typo fixes — updates the version so
  the release history stays aligned with the code, even when a version
  is not separately tagged

---

## [1.2.1] - 2026-04-16

### Fixed

#### Replace pinned model versions with family aliases (#56)

- Replaced version-pinned model identifiers (`claude-opus-4-6`,
  `claude-sonnet-4-6`, `claude-haiku-4-5`) with family aliases (`opus`,
  `sonnet`, `haiku`) across knowledge docs, reference schemas, and tests
- Ensures model references stay valid as new Claude versions ship without
  requiring downstream doc updates

---

## [1.2.0] - 2026-03-18

### Added

#### `/aida about` command and version in help text (#51)

- Added `/aida about` command to display plugin version, author, and
  repository from `plugin.json`
- Updated `/aida help` to include version footer
- Reorganized help text "Info" section with `help`, `about`, `status`

---

## [1.1.5] - 2026-03-18

### Fixed

#### Generated SKILL.md has multiple consecutive blank lines (#49)

- Added `trim_blocks`, `lstrip_blocks`, and `keep_trailing_newline`
  to `template_renderer.py` SandboxedEnvironment — this was the
  actual production renderer used by `configure.py`, which lacked
  the whitespace settings present in `shared/utils.py`
- Added post-processing safety net in `render_skill_directory()` to
  collapse 3+ consecutive newlines to a single blank line
- Added 5 tests using the production SandboxedEnvironment renderer
  covering all-true, all-false, and mixed (marketplace-like) inputs

---

## [1.1.4] - 2026-03-18

### Fixed

#### Scripts invoked with bare python3 instead of AIDA venv (#47)

- Updated all reference docs to invoke scripts via
  `~/.aida/venv/bin/python3` instead of bare `python3`
- Fixed Makefile `lint-frontmatter` target to use `$(VENV_BIN)/python3`
- Updated troubleshooting docs to reference venv Python path
- Affected files: `config.md`, `diagnostics.md`, `feedback.md`,
  `permissions-workflow.md`, `troubleshooting.md`, `Makefile`

---

## [1.1.3] - 2026-03-18

### Fixed

#### Config bugs: hardcoded version and missing project marker (#45)

- Replaced hardcoded `AIDA_VERSION = "0.7.0"` with dynamic version
  read from `plugin.json`, so `aida-project-context.yml` reflects
  the actual plugin version
- Added call to `render_aida_project_marker()` at the end of the
  configure flow, writing `.claude/aida.yml` so `detect.py` correctly
  reports `project_configured: true` after configuration

---

## [1.1.2] - 2026-03-18

### Fixed

#### Generated project-context SKILL.md fails markdown linting (#41)

- Changed 9 `'None'` string fallbacks to `''` in `configure.py` so
  Jinja2 conditionals correctly skip missing values
- Fixed all `{% if has_xxx %}` boolean checks to use
  `{% if has_xxx == 'true' %}` since values are strings
- Removed `| join()` and `[0]` indexing on string values that were
  incorrectly treated as lists
- Restructured template whitespace control to eliminate MD012
  (multiple blank lines) and MD032 (blanks around lists)
- Changed footer emphasis lines to HTML comments (fixes MD036)
- Fixed `tools` default to handle empty strings
- Added 19 unit tests for template rendering

---

## [1.1.1] - 2026-03-18

### Fixed

#### Missing `_paths` import in install.py (#42)

- Added `import _paths` to `install.py` before `from utils import`
  block, fixing `ModuleNotFoundError` when invoked via `/aida config`
  → "Update global preferences"

### Changed

#### Dev tooling uses AIDA-managed venv (#42)

- Added `requirements-dev.txt` for dev dependencies (pytest, ruff,
  yamllint)
- Makefile targets now use `~/.aida/venv/bin/` for all Python tools
- `make install` installs both runtime and dev deps into the venv
- Updated CLAUDE.md with setup instructions

---

## [1.1.0] - 2026-03-05

### Added

#### AIDA-managed Virtual Environment (#34)

- Bootstrap module (`scripts/shared/bootstrap.py`) that lazily creates
  and maintains a virtual environment at `~/.aida/venv/`
- Unified dependency management -- no manual `pip install` required
- Stamp file tracking to skip reinstall when dependencies haven't changed
- Venv health check in `/aida doctor`
- Optional AIDA bootstrap integration for skill creation flow
- Standardized `_paths.py` across all 8 skills

### Removed

- Ad-hoc "Install with: pip install ..." error messages from 6 scripts

## [1.0.0] - 2026-02-24

### Added

#### Plugin Scaffolding Skill (#23)

- Two-phase API for creating new plugins from templates
- Interactive setup with marketplace configuration

#### Plugin Update Skill (#27)

- `/aida plugin update` for standards migration
- Guides plugins through convention changes

### Changed

#### Decompose claude-code-management into Focused Skills (#31)

- Extracted `agent-manager`, `skill-manager`, `plugin-manager`,
  `hook-manager`, and `claude-md-manager` as standalone skills
- Shared logic moved to `extension_utils` module
- Standardized validate response shapes and default operations
- Replaced hand-rolled YAML parser with PyYAML
- Added `operation` key to list responses

#### Merge aida-dispatch into aida Skill (#24)

- Unified `/aida` routing into a single `aida` skill
- Removed `aida-dispatch` as a separate skill

#### Updated Knowledge Base (#31)

- Refreshed all 10 claude-code-expert knowledge files with current
  Claude Code capabilities

### Fixed

- Short-circuit permissions flow when no plugin recommendations
  exist (#28)

---

## [0.8.0] - 2026-02-23

### Changed

#### Merge Commands into Skills (#19)

- Eliminated "Command" as a separate extension type, aligning with Anthropic's
  upstream merge of commands into skills in Claude Code
- Migrated `commands/aida.md` to `skills/aida/SKILL.md` with `user-invocable: true`
  frontmatter field
- Removed `commands/` directory entirely
- Updated `.frontmatter-schema.json`: removed `command` from type enum, added
  skill-specific fields (`user-invocable`, `argument-hint`, `allowed-tools`,
  `disable-model-invocation`)
- Removed `command` from `COMPONENT_TYPES` in Python extension management code
- Removed command template from `skills/claude-code-management/templates/`
- Updated extension taxonomy from WHO/WHAT/HOW/CONTEXT to WHO/HOW/CONTEXT
  (Subagents/Skills/Knowledge)

#### Knowledge Documentation Rewrite

- Rewrote `extension-types.md` with updated decision tree (no Command branch)
- Rewrote `framework-design-principles.md` removing Command sections
- Updated `design-patterns.md`, `plugin-development.md`, `claude-md-files.md`,
  and `hooks.md` to reflect skills-only taxonomy
- Updated `schemas.md` with skill-specific field documentation and examples

#### User-Facing Documentation Updates

- Removed `docs/HOWTO_CREATE_COMMAND.md`
- Updated all HOWTO guides, Getting Started, Install Guide, Development Guide,
  Examples, and Architecture docs
- Updated C4 container and context diagrams (merged Commands container into Skills)
- Updated CI workflow, CODEOWNERS, and integration test scripts

### Fixed

- Fixed agent `model` frontmatter using invalid `claude-sonnet-4.5` model ID;
  changed to `sonnet` alias which resolves to latest Sonnet at runtime

---

## [0.7.0] - 2026-02-16

### Added

#### Auto-generate Agent Routing Directives (#12)

- Agent discovery scans three sources in priority order: project
  (`{project}/.claude/agents/`), user (`~/.claude/agents/`), and
  plugin-provided agents (via `aida-config.json` manifest)
- YAML frontmatter parsing reads agent metadata (name, description,
  version, tags, skills, model) with `yaml.safe_load()`
- Auto-generates `## Available Agents` section in project CLAUDE.md
  with routing directives for each discovered agent
- Marker-based idempotent updates — re-running config replaces the
  managed section without duplicating or losing manual content
- Agent Teams guidance included so team leads and teammates know
  when to consult domain-specific agents
- First-found-wins deduplication (project > user > plugin priority)

### Changed

- `_safe_read_file` in plugins.py now accepts `max_size` parameter
  (defaults to 1MB for backward compatibility, agents use 500KB)
- `aida-config.json` supports `agents` key declaring plugin agent
  names (falls back to directory scanning if absent)
- Phase 1 (`get_questions`) discovers agents and returns metadata
- Phase 2 (`configure`) updates CLAUDE.md with routing directives

### Security

- Agent file reading reuses TOCTOU-safe `_safe_read_file` with
  `O_NOFOLLOW`, size limits, and path containment checks
- Symlinked directories and files rejected during agent scanning

---

## [0.6.1] - 2026-02-16

### Fixed

#### Plugin Validator Compatibility (#13)

- Moved `config` and `recommendedPermissions` from `plugin.json` to new
  `aida-config.json` to resolve Claude Code plugin validator rejecting
  unrecognized keys
- Plugin discovery reads AIDA-specific fields from `aida-config.json`
  (strict separation, no fallback to `plugin.json`)

### Security

- TOCTOU-safe file reading with `O_NOFOLLOW` in plugin discovery and
  permission scanner (eliminates symlink race conditions)
- Directory-level symlink rejection for `.claude-plugin` directories
- Consistent `isinstance(data, dict)` validation at all JSON parse boundaries
- Reordered symlink check before `stat()` in permissions CLI

---

## [0.6.0] - 2026-02-15

### Added

#### User-Level Memento Storage (#3)

- Mementos stored at `~/.claude/memento/` (user-level, branch-independent)
- Project namespacing with `{project}--{slug}.md` filenames
- Auto-detected `project:` frontmatter block (name, path, repo, branch)
- List filtering: defaults to current project, `--all` for all projects,
  `--project <name>` for a specific project
- Completed mementos archived to `~/.claude/memento/.completed/`

#### Project-Level Permissions (#6, #9)

- Common development commands run without permission prompts
- Destructive operations still require confirmation
- Added Edit, Write, and NotebookEdit to allowed tools

### Changed

- Migrated from monorepo to standalone repository (#1)
- Adopted marketplace-centric distribution strategy (#2)
- Replaced custom YAML frontmatter parser with PyYAML `safe_load`

### Security

- Atomic file writes via tempfile + `os.replace` with 0o600 permissions
- Path containment validation with symlink rejection
- YAML injection prevention via `| tojson` in Jinja2 templates
- Regex backreference injection prevention via lambda replacements
- Git URL credential sanitization across all URL schemes
- Directory permissions enforced via `os.chmod(0o700)` after `mkdir`
- Input validation: slug format/length, project name, JSON size limits

---

## [0.2.0] - 2025-11-05

### Added

#### New `/aida` Command Dispatcher

- Unified command interface for all AIDA functionality
- 8 subcommands: config, status, doctor, upgrade, feedback, bug, feature-request, help
- Skill-based architecture with `aida-dispatch` skill

#### Smart Configuration System

- `/aida config` - Intelligent configuration menu with state detection
- Auto-detects installation state (global/project)
- Context-aware menu options (shows only relevant choices)
- Handles both initial setup AND updates
- "View current configuration" option

#### YAML-Based Configuration (Major Innovation)

- Auto-detection of 90% of project facts
- Single source of truth in `.claude/aida-project-context.yml`
- Detects: VCS (Git, worktrees, remotes), files (README, LICENSE, etc.), languages, tools
- Infers: project type, team size, documentation level
- **Massive question reduction: 22 questions → 2 questions!**

#### New Diagnostic Commands

- `/aida status` - Show installation and configuration status
- `/aida doctor` - Comprehensive health check with fix suggestions
- `/aida upgrade` - Check for updates and show upgrade instructions

#### Project Context Skill

- Auto-generated from YAML configuration
- Provides project-specific facts to Claude
- Updates automatically when config changes

### Changed

#### Architecture

- Migrated from `aida-core` skill to `aida-dispatch` skill
- Command dispatcher delegates to skill (cleaner separation)
- Scripts use YAML config instead of complex conditional logic

#### Configuration Flow

- Replaced questionnaire conditionals with fact detection
- Configuration saved to YAML before asking questions
- Skills rendered from YAML (not from questionnaire responses)

### Improved

- **User Experience**: Fewer questions, smarter defaults
- **Transparency**: Config file is human-readable YAML
- **Idempotency**: Can run config multiple times safely
- **Error Handling**: Better error messages with actionable suggestions
- **Documentation**: Comprehensive references and architecture docs

### Technical

#### New Scripts

- `scripts/detect.py` - Detect installation state
- Enhanced `scripts/configure.py` - YAML-based configuration
- Enhanced fact detection functions

#### New Utilities

- `utils/files.py` - Added `write_yaml()` function
- Enhanced `detect_project_info()` with structured schema
- New `detect_vcs_info()` and `detect_files()` functions

#### New Reference Documentation

- `references/config-driven-approach.md` - Architecture guide
- `references/project-facts.md` - Comprehensive fact taxonomy
- `docs/architecture/adr/007-yaml-config-single-source-truth.md` - ADR

### Fixed

- N/A (initial release of dispatcher)

### Deprecated

- Old `aida-core` skill (replaced by `aida-dispatch`)

### Security

- Validates YAML file sizes (max 1MB)
- Validates JSON payloads (max 1MB, max depth 10)
- Path validation prevents system directory access
- Template variable validation prevents injection

---

## [0.1.8] - 2025-11-04

### Previous Release

- Initial plugin structure
- Basic install/configure scripts
- Foundation utilities

See git history for details on versions prior to 0.2.0.

---

[1.4.6]: https://github.com/aida-core/aida-core-plugin/releases/tag/v1.4.6
[1.4.5]: https://github.com/aida-core/aida-core-plugin/releases/tag/v1.4.5
[1.4.4]: https://github.com/aida-core/aida-core-plugin/releases/tag/v1.4.4
[1.4.3]: https://github.com/aida-core/aida-core-plugin/releases/tag/v1.4.3
[1.4.2]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v1.4.2
[1.4.1]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v1.4.1
[1.4.0]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v1.4.0
[1.2.1]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v1.2.1
[1.2.0]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v1.2.0
[1.1.5]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v1.1.5
[1.1.4]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v1.1.4
[1.1.3]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v1.1.3
[1.1.2]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v1.1.2
[1.1.1]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v1.1.1
[1.1.0]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v1.1.0
[1.0.0]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v1.0.0
[0.8.0]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v0.8.0
[0.7.0]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v0.7.0
[0.6.1]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v0.6.1
[0.6.0]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v0.6.0
[0.2.0]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v0.2.0
[0.1.8]: https://github.com/oakensoul/aida-core-plugin/releases/tag/v0.1.8
