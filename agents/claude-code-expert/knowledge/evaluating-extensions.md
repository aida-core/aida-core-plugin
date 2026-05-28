---
type: reference
name: evaluating-extensions
title: Evaluating Extensions — Rubric Guidance for the Review Skill
description: Narrative rubric for grading agents, skills, and plugins. What "excellent" looks like per extension type, what to flag, and how to score sub-rationally when the structural rules don't catch what matters.
version: "1.0.0"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Evaluating Extensions

This file is the reasoning context for the **Phase 2 (LLM expert
review)** layer of the review skill design tracked in
`docs/proposals/review-skill.md`. The deterministic rubric scores
the structural properties of an extension; the LLM expert reads
this file to score the *qualitative* properties — description
clarity, knowledge depth, expertise authenticity, semantic match
between an extension's stated purpose and its actual content.

**When to use this file:** the review skill's Phase 2 invokes
`claude-code-expert` to render a narrative critique on top of the
rubric findings. The agent loads this file then walks the artifact
under review.

## The three-phase review model (recap)

| Phase | Owner | What it grades | Reproducible? |
|---|---|---|---|
| 1. Deterministic rubric | Python | Structural properties (frontmatter complete, knowledge index exists, tool scope, etc.) | Yes — CI-gateable |
| 2. LLM expert review | `claude-code-expert` (this agent) | Qualitative properties (description quality, semantic mismatch, redundancy) | No — advisory |
| 3. Behavioral evals | `evals/evals.json` runner | The extension's actual outputs against assertions | Yes (with caveats) |

The canonical grade for CI is **Phase 1**. The expert score in
Phase 2 is **advisory**. Both ship in the report; only one gates
merges.

## What excellence looks like — agents

An excellent agent has:

- **A description that names concrete activation triggers.** Not
  "helps with frontend code" but "expert on React component
  architecture and accessibility patterns; reviews component
  hierarchies and recommends ARIA patterns". Generic descriptions
  produce generic activations.
- **One coherent area of expertise**, not a kitchen sink. The
  agent's knowledge files should cluster around one domain. If
  reading the knowledge dir feels like reading three different
  agents stapled together, the agent is over-scoped.
- **Knowledge files organized for progressive disclosure.** The
  always-loaded `agent.md` is lean — it has the persona,
  judgment frameworks, and pointers. The deep content lives in
  `knowledge/*.md` files, each focused on a single topic, each
  named so the agent can reason about when to load it. An
  `index.md` lists the files with one-line "when to use" entries.
- **Tool scope matched to the work.** `allowed-tools` lists the
  specific tools the agent needs. A wildcard `*` is acceptable
  only when the agent genuinely needs the full toolset; "I
  couldn't be bothered to narrow it" is not.
- **An honest description.** If the agent description claims
  expertise the knowledge files don't back up, that's a Phase 2
  red flag — the structural rubric won't catch it, but a human
  reading the description and then the knowledge will.

## What excellence looks like — skills

An excellent skill has:

- **A lean shell.** `SKILL.md` is the always-loaded entry point.
  Anything that doesn't need to be in context on every activation
  belongs in `references/`, `scripts/`, or `templates/`. The
  hard ceiling is ~500 lines; below that, less is usually better.
- **Activation criteria stated explicitly.** "This skill
  activates when…" or equivalent in the body. Helps the model
  know whether to route here AND helps the human reviewer
  understand the skill's scope.
- **Progressive disclosure with explicit triggers.** Not "see
  `references/` for details" but "if the API returns a non-200
  status, read `references/api-errors.md`". The agent needs to
  know *when* to load each deeper file.
- **Process, not expertise.** Skills define HOW. Domain judgment
  ("which approach is better for our codebase?") belongs in an
  agent the skill can spawn. A skill that prescribes "this is
  the right way to architect X" is doing an agent's job.
- **The two-phase API where it applies.** For skills with side
  effects, get-questions / execute keeps the user in the loop
  about what's about to happen. Side effects in the questions
  phase is a serious bug — see `agent-manager`, `memento`, and
  `plugin-manager` for the pattern done right.
- **Scripts that earn their place.** Bundled scripts should
  encapsulate repeated logic; a script with one caller and no
  reuse story is suspect. Scripts must carry SPDX headers, type
  hints on public functions, and the `if __name__ == "__main__"`
  pattern.

### What to flag on skills

- **Quality judgments inline.** A skill that says "look for SQL
  injection, verify authentication checks" is putting expertise
  where process should be. The fix is to spawn a security-review
  agent whose knowledge covers those heuristics.
- **Menus instead of defaults.** "You can use pypdf, pdfplumber,
  PyMuPDF, or pdf2image" pushes decisions onto the agent and
  produces inconsistent runs. Pick one.
- **Specifics instead of procedures.** "Join orders to customers
  on customer_id" only works for one task. "Find the relevant
  tables in the schema, join on the `_id` foreign-key
  convention" works for any analytical query.
- **Missing gotchas.** If the skill operates against a system
  with non-obvious behavior (soft deletes, ambiguous IDs,
  health-vs-ready endpoints) and the gotchas aren't enumerated,
  the agent will make those mistakes. Every correction that
  comes back during dogfooding is a candidate gotcha.

## What excellence looks like — plugins

An excellent plugin has:

- **Complete metadata.** `plugin.json` has `name`, `description`
  (substantive, not a single phrase), `version`, `author`,
  `repository`. `LICENSE`, `AUTHORS`, and `REUSE.toml` exist.
  CI workflow + version-check workflow + CHANGELOG following
  Keep-a-Changelog.
- **Agents and skills that themselves score well.** A plugin's
  grade is partly a roll-up of its parts. A plugin shipping three
  agents and four skills where one agent is excellent and the
  rest are C-grade isn't excellent overall.
- **No name collisions.** Agents and skills inside the plugin
  don't conflict with anything else commonly installed.
- **Plugin-level docs follow the progressive-disclosure pattern.**
  README and CLAUDE.md route to deeper docs rather than inlining
  them.

## Cross-cutting failure modes the LLM should catch

These are the kinds of issues the structural rubric tends to miss
but that significantly degrade extension quality:

### Semantic mismatch

The description claims one thing; the content does another. An
agent described as "frontend architecture expert" with knowledge
files about backend API patterns. A skill described as "PR review"
that's actually a deploy workflow. The structural rubric can't
catch this; reading the artifact does.

When you see this, score it harshly. Misleading descriptions
cause activation failures in production.

### Knowledge that overlaps without acknowledging the overlap

Two knowledge files in the same agent that cover the same topic
from slightly different angles. The agent probably built them
incrementally and never reconciled. The fix is consolidation, not
cross-references — cross-references multiply the load cost. Flag
overlap and recommend consolidating, naming the specific files.

### Activation triggers that don't trigger

The description says "activates when reviewing PRs" but uses
phrasing that doesn't match how users actually ask for PR
reviews. Look at the description with a user's hat on: would
someone naturally produce a sentence that matches these
keywords?

### Tool scope that doesn't fit the work

An agent with `allowed-tools: *` whose knowledge only covers
read-only research. An agent with narrowly scoped tools whose
SKILL.md prescribes operations the tools can't perform. The
mismatch produces silent failures.

### Iteration debt

A knowledge file with a "TODO: expand this section" comment from
six months ago. A skill with a half-implemented feature. A
gotchas list with one entry, suggesting the author started the
list and walked away. These don't fail the rubric, but they
signal that the author lost interest before the extension was
done. Score them down and note specifically what looks
unfinished.

## How to write the review

The deterministic rubric gives you a score, findings (severity +
file:line + rule), and a letter grade. Your job is the *narrative
critique* on top. Write 2–4 paragraphs that:

1. **Reinforce or push back on the deterministic score.** If the
   rubric gave it an A but the description is a generic phrase,
   say so. The structural score is canonical for CI; your job is
   to be the second pair of eyes for the human reviewer.
2. **Cluster the findings.** If three rubric findings all point
   at one root cause, name it. "All three findings about the
   knowledge directory cluster around the fact that
   `knowledge/index.md` doesn't actually index the new files."
3. **Surface what the rubric can't see.** Semantic mismatch,
   overlap, iteration debt, misleading descriptions.
4. **Recommend a concrete next action** — "consolidate X and Y",
   "rewrite the description to name the actual activation
   scenarios", "drop the menu and pick a default" — not generic
   advice.

Cite `file:line` whenever possible. Avoid "this could be better"
verdicts; say what specifically is wrong and what good would look
like.

### Tone

Be honest. The structural rubric is forgiving by design; your job
is to be the more candid reviewer. But honesty isn't cruelty —
the goal is to make the extension better, not to demoralize the
author. A useful critique always points at the fix.

## Anti-patterns specific to LLM-grading

When the LLM does Phase 2 review, common failure modes to avoid:

- **Grading on prose quality of the SKILL.md.** Skills aren't
  essays. Choppy, terse instructions often work better than
  flowing prose. Don't penalize directness.
- **Penalizing brevity.** A 200-line SKILL.md that does its job
  cleanly is excellent. Don't recommend padding.
- **Recommending more options.** Defaults beat menus. If the
  skill picks one approach, that's usually correct — don't
  suggest "you could also support X, Y, Z."
- **Conflating structural rules with quality.** The Phase 1
  rubric handles "has SPDX header", "has frontmatter", etc. Your
  Phase 2 review should focus on things Phase 1 can't measure.

## Calibration notes

When grading on the 0–100 scale:

- **90–100 (A):** This is what you'd point to as an example of
  how to write the extension type. Few or no findings; what
  findings exist are minor polish.
- **80–89 (B):** Solid work. A few real issues that warrant
  fixing but the extension is usable as-is.
- **70–79 (C):** Adequate. Multiple real issues; the extension
  works but a reviewer would push back on shipping it.
- **60–69 (D):** Needs work. Structural or qualitative issues
  serious enough that a user trying to learn from this extension
  would learn the wrong lessons.
- **<60 (F):** Recommend rewrite. The artifact isn't doing what
  it claims, or the architecture is fundamentally wrong.

Don't grade-inflate. A C is fine — most extensions are C-grade
when first reviewed. The review skill exists to help authors get
to B.

## Source materials

This rubric draws on principles from
<https://agentskills.io/skill-creation/best-practices>,
<https://agentskills.io/skill-creation/evaluating-skills>, and our
own `framework-design-principles.md`. See
`agents/claude-code-expert/knowledge/external-references.md` for
the full upstream source list.
