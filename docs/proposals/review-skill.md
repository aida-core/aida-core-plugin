---
type: proposal
title: "Review/Grade Skill for Plugin Extensions"
description: "Deterministic rubric + LLM expert review, A-F letter grades, Progressive Knowledge as a first-class category. Generalizes /aida claude optimize to agents, skills, and plugins."
status: draft
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Proposal: Review/Grade Skill for Plugin Extensions

## Problem

We have **structural validation** for agents, skills, and plugins (`/aida agent
validate`, `/aida skill validate`, `/aida plugin validate`) — pass/fail
checks on frontmatter and required fields — and **quality scoring** only for
CLAUDE.md (`/aida claude optimize`, 0–100 with findings).

There's no equivalent quality grader for agents, skills, or plugins themselves.
The `claude-code-expert` agent's description claims it "reviews, scores, and
creates" extensions, but it's only invokable through the Task tool / @-mention.
Its output is subjective, not reproducible, and not CI-gateable.

This proposal generalizes the `claude optimize` pattern to the rest of the
extension surface, and pairs it with the existing expert agent so we get both
deterministic CI-grade scoring **and** narrative LLM critique in the same
report.

## Goals

- Reproducible quality grade (0–100 + A–F letter) for every agent, skill, and
  plugin in a project
- Findings cite `file:line` and the rubric rule they violate
- CI-gateable: deterministic phase exits non-zero below a configurable threshold
- Optional LLM expert layer that catches what static rules can't (semantic
  mismatches, prose quality, expertise authenticity)
- Project-configurable output format (terminal / JSON / markdown / ask)
- Rubric is versioned — scores stay reproducible across rubric updates

## Non-goals

- Replace structural validation (`validate` stays as the schema-level pass/fail)
- Run on user-level extensions in bulk mode (project-scoped only; see
  the Bulk mode section below)
- Grade quality of the LLM model's outputs at runtime — we grade the
  *artifacts*, not the agent's responses

## Command surface

```text
/aida agent review <name>          # single agent
/aida agent review --all           # every agent in the project
/aida skill review <name>          # single skill
/aida skill review --all           # every skill in the project
/aida plugin review                # whole-plugin roll-up
/aida plugin review --all          # every plugin in current scope (project only)
```

**Flags (all subcommands):**

- `--no-expert` — skip the LLM phase; deterministic only (fast, CI-friendly)
- `--format terminal|json|markdown` — override the project-configured format
- `--rubric-version <X.Y.Z>` — pin to an older rubric (default: latest)
- `--threshold A|B|C|D` — override CI gate threshold for this run

## Grading

### Numeric score + letter grade

Standard report-card mapping. No +/- variants.

| Letter | Range  | Label                           |
|--------|--------|---------------------------------|
| A      | 90–100 | Excellent                       |
| B      | 80–89  | Good                            |
| C      | 70–79  | Adequate                        |
| D      | 60–69  | Needs work                      |
| F      | <60    | Failing — recommend rewrite     |

Display together: `Grade: A (94/100)`. Letter is the headline; number is what
diffs across runs.

### Three-phase architecture

```text
┌─ Phase 1: Deterministic rubric (Python) ─┐
│  - Rule-based static checks               │
│  - Emits structural score + letter grade  │
│  - JSON findings (severity, file:line)    │
│  - Reproducible, CI-gateable              │
│  - Rubric is versioned                    │
└───────────────────┬───────────────────────┘
                    │ findings.json
                    ▼
┌─ Phase 2: Expert review (LLM) ───────────┐
│  - Invokes claude-code-expert agent       │
│  - Reads artifact + Phase 1 findings      │
│  - Narrative critique + advisory grade    │
│  - Catches description quality, knowledge │
│    depth, expertise authenticity          │
│  - Knowledge for grading lives WITH the   │
│    agent (see "Knowledge separation")     │
└───────────────────┬───────────────────────┘
                    │ expert.json
                    ▼
┌─ Phase 3: Behavioral evals (opt-in) ─────┐
│  - Runs only if artifact ships            │
│    `evals/evals.json`                     │
│  - With/without baseline runs             │
│  - Assertions graded → pass-rate          │
│  - Timing + tokens captured               │
│  - Adopts agentskills.io schema for       │
│    portability with `skill-creator`       │
└───────────────────┬───────────────────────┘
                    ▼
            Combined report:
            ┌─────────────────────────────┐
            │ Structural: A (94/100)      │ ← canonical, CI uses this
            │ Expert:     B (85/100)      │ ← advisory, narrative
            │ Behavioral: A (92/100)      │ ← only if evals shipped
            │ ───                         │
            │ Findings + recommendations  │
            │ Rubric: v1.0.0              │
            └─────────────────────────────┘
```

**Why the structural score is canonical and not blended:**

- CI needs a reproducible gate (same code → same grade)
- LLM grades drift across model versions
- Behavioral pass-rate has variance across runs
- Blended scores hide which layer flagged what

**Where the LLM earns its keep:**

- "Description says 'helps with frontend' but the agent has no
  frontend-specific knowledge files" (semantic mismatch deterministic rules
  miss)
- "Knowledge index lists 8 files but they overlap — consolidate X and Y"
  (judgment call)
- "Three rubric findings cluster around one root cause — fix Z first"
  (synthesis)

**Where behavioral evals earn their keep:**

- "This skill technically has good structure but produces wrong outputs
  half the time" (only black-box testing catches this)
- "The skill adds 13s and 1700 tokens to lift pass-rate by 50 points"
  (cost/value visibility)
- "Pass-rate is unchanged with/without the skill" (the skill isn't
  actually contributing anything)

### Knowledge separation — Knowledge with the agent, process with the skill

The narrative guidance the LLM uses during Phase 2 is **knowledge**, not
code. It belongs with the `claude-code-expert` agent, not inside the
review skill.

```text
agents/claude-code-expert/knowledge/
  └── evaluating-extensions.md       ← narrative rubric, anti-patterns,
                                       reviewer instructions. The LLM
                                       loads this in Phase 2.

skills/review/
  ├── SKILL.md                        ← orchestration (dispatch, format)
  ├── rubric/v1.0.0/                  ← versioned rule definitions + weights
  │   ├── agent.yaml                  ← data: which rules + weights apply
  │   ├── skill.yaml
  │   └── plugin.yaml
  └── scripts/
      ├── run_rubric.py               ← Phase 1 deterministic execution
      ├── invoke_expert.py            ← Phase 2 expert invocation
      └── run_evals.py                ← Phase 3 behavioral runner
```

**Consequence:** when `claude-code-expert` is rebuilt (knowledge refresh
against upstream sources), the LLM scoring system updates automatically.
The deterministic rule code stays untouched. This is the same principle
that makes the agent rebuildable today — knowledge is data, code is code.

## Relationship to agentskills.io evaluation methodology

The agentskills.io community has published a strong methodology for
**behavioral** skill evaluation
(<https://agentskills.io/skill-creation/evaluating-skills>): write test
cases as `evals/evals.json`, run each prompt with and without the skill,
grade assertions against actual outputs, compute pass-rate deltas. This
is fundamentally different from what our review skill does at its core:

| | **agentskills.io evals** | **Our review skill (Phases 1+2)** |
|---|---|---|
| Tests | The skill's *behavior* | The skill's *artifact* |
| Style | Black-box behavioral | White-box static |
| Catches | "Skill silently produces wrong outputs" | "Description is generic, tools are over-scoped" |
| Misses | Whether the artifact is well-organized | Whether the skill actually works |

These are **complementary phases of the same question**, so Phase 3
adopts agentskills.io's approach wholesale:

- **Schema:** use their `evals/evals.json` shape verbatim — portability
  with `skill-creator` and the broader ecosystem matters more than NIH'ing
  a new format
- **With/without baseline:** measure the *delta*, not just absolute
  pass-rate. A skill that doesn't improve pass-rate vs. no-skill isn't
  pulling its weight
- **Timing + tokens:** capture the cost side of the cost/value tradeoff
- **Assertion grading with evidence:** every PASS must quote/reference
  output; no "looks good" verdicts

Extensions we'd add on top:

- **Rubric versioning** applied to assertions — iteration N+1 should be
  comparable to N (their methodology doesn't enforce this)
- **Pass-rate → letter grade** mapping so Phase 3 outputs the same
  vocabulary as Phases 1+2
- **Roll-up** — `/aida plugin review` aggregates Phase 3 results across
  all skills in the plugin

## Rubric

Five categories per extension type. Total = 100.

### Agents (`/aida agent review`)

| Category                          | Weight | What's checked                                                                                              |
|-----------------------------------|--------|-------------------------------------------------------------------------------------------------------------|
| **Progressive Knowledge**         | 25     | `knowledge/` exists, `knowledge/index.md` lists files with one-line descriptions, each file is focused (≤N lines), main `agent.md` doesn't inline knowledge, each file has clear "load when…" criteria |
| **Single Responsibility**         | 20     | Description doesn't claim multiple unrelated expertises; knowledge files cluster around one domain          |
| **Description Specificity**       | 15     | Length ≥ N chars, contains concrete activation triggers, names the domain, avoids "helps with X" generic phrasing |
| **Tool Scope**                    | 15     | Tool list is scoped (not `*` unless justified); narrow set preferred                                        |
| **Frontmatter Completeness**      | 10     | `name`, `description`, `model`, version present; model id is valid                                          |
| **Activation Triggers Clear**     | 15     | Description names concrete scenarios where this agent should activate                                       |

### Skills (`/aida skill review`)

| Category                          | Weight | What's checked                                                                                              |
|-----------------------------------|--------|-------------------------------------------------------------------------------------------------------------|
| **Progressive Knowledge**         | 25     | `SKILL.md` is lean shell (routing only), `references/` exists and is referenced (not inlined), `scripts/` and `templates/` not pulled into context as text, multi-step workflows live in references |
| **Resource Organization**         | 15     | `scripts/`, `references/`, `templates/` used appropriately; not all-in-one SKILL.md                         |
| **Two-Phase API**                 | 15     | `get_questions` / `execute` pattern followed where applicable; no side effects in question phase            |
| **Script Hygiene**                | 15     | SPDX headers, type hints, `if __name__ == "__main__":`, no business logic in markdown                       |
| **Activation Criteria**           | 10     | SKILL.md states when this skill activates and what triggers route here                                      |
| **Frontmatter Completeness**      | 10     | `name`, `description`, `version`, type present; valid                                                       |
| **Behavioral Evals (Phase 3)**    | 10     | Skill ships `evals/evals.json` with ≥3 test cases + assertions; pass-rate above threshold when run with skill; meaningful delta vs. baseline |

### Plugins (`/aida plugin review`)

| Category                          | Weight | What's checked                                                                                              |
|-----------------------------------|--------|-------------------------------------------------------------------------------------------------------------|
| **Extension Quality (roll-up)**   | 40     | Every agent and skill in the plugin scores ≥ threshold; weighted average of individual scores               |
| **Progressive Knowledge**         | 15     | Plugin-level docs follow the pattern (CLAUDE.md / README route to deeper docs, don't inline them)           |
| **Plugin Metadata**               | 15     | `plugin.json` complete (author, repository, description ≥ N chars), LICENSE + AUTHORS + REUSE.toml present  |
| **Governance & CI**               | 15     | CI workflow + version-check + CHANGELOG follows Keep-a-Changelog + dependencies declared if any             |
| **Cross-Cutting Hygiene**         | 15     | No agent/skill name collisions, SPDX headers across files, REUSE clean                                      |

### Progressive Knowledge — first-class

Called out because it's the biggest lever on extension quality. The pattern:
**always-loaded shell stays lean; deeper content loads only when needed.**

For each extension type the checker walks:

1. What gets pulled into context unconditionally (the shell)
2. What's organized for lazy loading (knowledge files / references)
3. Whether the shell references the deeper content (catalog/index pattern)
4. Whether knowledge files have clear load-criteria so the model knows when
   to pull each one

Concrete checks per type are in the Rubric tables above.

## Configuration

Added during `/aida config` and persisted in `aida-project-context.yml`:

```yaml
review:
  output_format: terminal | json | markdown | ask
  ci_threshold: A | B | C | D       # default: B (≥80)
  rubric_version: current | "X.Y.Z" # default: current
  expert_phase: enabled | disabled  # default: enabled
```

**Setup questions during `/aida config`:**

1. "What output format do you want for `/aida {agent,skill,plugin} review`?"
   - Terminal (default — pretty-printed table)
   - JSON (machine-readable for CI)
   - Markdown (PR comment / report)
   - Ask every time
2. "Minimum grade for CI gates?" — default B; user can lower
3. "Enable LLM expert review by default?" — default yes; `--no-expert`
   overrides per-run

## Bulk mode (`--all`)

- `--all` is **project-scope only**. Walks `agents/` and `skills/` in the
  current project, never `~/.claude/agents/` or `~/.claude/skills/`.
- Rationale: user-level extensions are personal hacks not meant for review
  rigor. Repo-level extensions are the things CI cares about.
- Concurrency: deterministic phase parallelizes freely. Expert phase caps at
  N=3 concurrent (configurable) to keep token usage predictable.

## Rubric versioning

The rubric is a versioned contract, similar to `.frontmatter-schema.json`.

- `rubric/v1.0.0/` ships rule definitions + weights + thresholds
- Each report includes the rubric version it was generated against
- Semver:
  - **Major** = new rules or rules removed (scores will shift)
  - **Minor** = weight changes or refined thresholds (scores may shift)
  - **Patch** = bugfixes to rule implementations (scores stable)
- `--rubric-version 1.0.0` pins to an older version for CI stability
- Default = `current`; opt-in pinning for repos that want frozen scoring

When a rubric version is yanked or deprecated, reports generated against it
keep working but emit a warning.

## Output formats

### Terminal (default)

```text
Reviewing: agents/claude-code-expert

  Structural: A (94/100)
  Expert:     A (92/100)  [advisory]

  Category                       Score   Grade
  ─────────────────────────────────────────────
  Progressive Knowledge          24/25   A
  Single Responsibility          18/20   A
  Description Specificity        14/15   A
  Tool Scope                     15/15   A
  Frontmatter Completeness       10/10   A
  Activation Triggers Clear      13/15   B

  Findings:
    [info]  agents/claude-code-expert/knowledge/skills.md:1
            Knowledge file 421 lines — consider splitting
    [info]  agents/claude-code-expert/claude-code-expert.md:12
            Description could name more concrete activation triggers

  Expert notes:
    "Knowledge organization is exemplary. The plugin-development.md file
    overlaps with extension-types.md on plugin packaging — consider
    extracting a shared section or cross-linking."

  Rubric: v1.0.0
```

### JSON

```json
{
  "artifact": "agents/claude-code-expert",
  "rubric_version": "1.0.0",
  "structural": {
    "score": 94,
    "grade": "A",
    "categories": [
      {"name": "Progressive Knowledge", "score": 24, "max": 25, "grade": "A"},
      ...
    ]
  },
  "expert": {
    "score": 92,
    "grade": "A",
    "notes": "Knowledge organization is exemplary..."
  },
  "findings": [
    {
      "severity": "info",
      "file": "agents/claude-code-expert/knowledge/skills.md",
      "line": 1,
      "rule": "knowledge-file-length",
      "message": "Knowledge file 421 lines — consider splitting"
    }
  ]
}
```

### Markdown (for PR comments)

Renders the same data as a markdown table + collapsible details section
suitable for posting to GitHub PRs.

## Implementation milestones

1. **M1: Deterministic phase, agents only** — `/aida agent review <name>`
   with the agent rubric. JSON output. Rubric v1.0.0 frozen.
2. **M2: Skills + plugins** — `/aida skill review`, `/aida plugin review`.
   Roll-up math for plugin-level. Same rubric version.
3. **M3: Terminal + markdown formats** — pretty-printer and PR-comment
   renderer.
4. **M4: Config integration** — questions added to `/aida config`,
   `review:` block in `aida-project-context.yml`.
5. **M5: Expert phase** — wire in `claude-code-expert` invocation;
   advisory score + narrative. Concurrency cap on `--all`. Ships with
   `agents/claude-code-expert/knowledge/evaluating-extensions.md`
   (knowledge with the agent, not in the skill).
6. **M6: CI gate** — `--threshold` + non-zero exit; documented as a
   GitHub Actions step.
7. **M7: Bulk mode** — `--all` traversal for all three commands, project
   scope only.
8. **M8: Rubric versioning UX** — `--rubric-version` flag, deprecation
   warnings, version index in docs.
9. **M9: Behavioral evals (Phase 3)** — adopt agentskills.io
   `evals/evals.json` schema. With/without runner, assertion grading,
   pass-rate delta, timing/tokens capture. Opt-in per extension.
10. **M10: Expert knowledge sync** — once knowledge-sync ships HTTP
    fetcher support, migrate the URLs in
    `agents/claude-code-expert/knowledge/external-references.md` into
    `sources.yml` so the agent's grading knowledge refreshes
    automatically against upstream.

## Open questions

- **Rubric extensibility for downstream plugins** — should plugins be able to
  add their own rules to the rubric for self-review? Probably yes, but defer to
  M9+
- **Caching** — Phase 1 is fast; Phase 2 isn't. Should expert verdicts be
  cached by content hash so unchanged artifacts skip the LLM call?
- **Aggregation across plugins** — `/aida plugin review --all` over multiple
  plugins in a workspace: report shape?
- **Grade inflation guardrails** — when rubric version bumps, do we publish
  a migration note showing how typical scores shifted?
- **Hooks** — should `/aida agent review` run automatically as a pre-commit
  hook on changed files? (Probably opt-in via `/aida hook add`)

## Related

- `/aida claude optimize` — the existing CLAUDE.md scorer this generalizes
- `agents/claude-code-expert/` — the LLM agent used for Phase 2
- ADR-012 — expert-registry split (review skill stays in aida-core)
- `.frontmatter-schema.json` — precedent for versioned downstream contracts
