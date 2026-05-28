---
type: reference
name: skill-iteration
title: How Skills Get Good
description: The iteration loop that produces quality skills — start from real expertise, refine with real execution, read traces not just outputs. Where evals fit and what they're for.
version: "1.0.0"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# How Skills Get Good

A skill that just works on the first try is rare. The skills that
work *reliably* — across varied prompts, in edge cases, better than
no skill at all — got there through iteration.

**When to use this file:** authoring a new skill, troubleshooting a
skill that fails inconsistently, deciding whether to add evals,
reviewing whether a skill is ready to ship.

## Start from real expertise

The common pitfall in skill creation is asking an LLM to generate a
skill from a one-line description, relying on its training-data
generalities. The result is vague, generic procedures ("handle
errors appropriately", "follow best practices") rather than the
specific API patterns, edge cases, and project conventions that
make a skill actually useful.

Effective skills are grounded in real, hands-on, project-specific
expertise. Two ways to ground them:

### Extract from a hands-on task

Do the task with an agent in conversation, providing context,
corrections, and preferences as you go. When the task succeeds,
extract the reusable pattern into a skill. Pay attention to:

- **Steps that worked** — the sequence of actions that led to success
- **Corrections you made** — places where you steered the agent away
  from a wrong approach. Each correction is a candidate gotcha.
- **Input/output formats** — what the data looked like going in and
  coming out
- **Project-specific context you provided** — facts, conventions,
  or constraints the agent didn't already know

A skill written from one successful run usually beats one written
from "what skills like this typically look like".

### Synthesize from existing project artifacts

When the project already has accumulated knowledge — runbooks,
incident reports, code review comments, style guides, schemas — feed
those into the synthesis instead of relying on generic references.

Good source material includes:

- Internal documentation, runbooks, and style guides
- API specifications, schemas, and configuration files
- Code review comments and issue trackers (captures recurring
  concerns and reviewer expectations)
- Version control history, especially patches and fixes — reveals
  patterns through what actually changed
- Real-world failure cases and their resolutions

A data-pipeline skill synthesized from your team's actual incident
reports will outperform one synthesized from a generic "data
engineering best practices" article, because it captures *your*
schemas, failure modes, and recovery procedures.

## Refine with real execution

The first draft of a skill usually needs refinement. Run the skill
against real tasks, then feed the results — all of them, not just
failures — back into the next revision. Ask:

- What triggered false positives?
- What was missed?
- What could be cut?

Even one pass of execute-then-revise noticeably improves quality.
Complex domains often benefit from several.

### Read execution traces, not just final outputs

The final output tells you whether the skill produced something
acceptable. The execution trace tells you *why*. Common signals in
traces:

- **Agent tries several approaches before finding one that works**
  — instructions are too vague; pick a default
- **Agent follows an instruction that doesn't apply to the current
  task** — instructions are over-eager; scope them or remove them
- **Agent waffles between options presented in the skill** — too
  many options, not enough opinion
- **Agent independently re-implements the same logic across runs**
  — that logic should be a bundled script

Traces are where the real iteration happens. Look at them.

## Evals — when and what for

Evals are how you stop relying on vibes for "is this skill good?"
The agentskills.io community has a working methodology that's
documented in our planning at `docs/proposals/review-skill.md`
under Phase 3. The pattern:

1. Write 2–3 test cases as realistic user prompts in
   `evals/evals.json` inside the skill directory. Each test case
   has a prompt, an expected-output description, and optional input
   files.
2. Run each prompt twice — once **with the skill** and once
   **without it** (or with the previous version). The delta is
   what tells you the skill is contributing.
3. After the first run, write assertions. Good assertions are
   verifiable ("the output is valid JSON", "the chart has labeled
   axes"). Bad assertions are vague ("the output is good") or
   brittle ("uses exactly the phrase 'Total Revenue'").
4. Grade each assertion against actual outputs, requiring evidence
   for a PASS. A section titled "Summary" with one vague sentence
   is not a PASS for "includes a summary" — the label is there but
   the substance isn't.
5. Aggregate pass-rate, timing, and tokens across runs. The delta
   between with-skill and without-skill tells you the cost and
   value.

### When evals pay off

- **The skill is shipped to other users** — you can't rely on
  catching regressions during dogfooding
- **The skill has subtle output requirements** — what counts as
  "good" varies enough that assertions help you stay honest
- **You're iterating on the skill** — evals let you compare
  versions empirically instead of reasoning about which one feels
  better

### When evals are overkill

- **The skill is a thin wrapper around a script that already has
  unit tests** — the script's tests cover the behavior; an
  end-to-end eval adds little
- **The skill is a one-off internal workflow** — the cost of
  setting up evals exceeds the value of the marginal quality
  improvement
- **The output is so structured that diffing it across versions
  is enough** — assertions duplicate effort

The review skill (`#146`) is meant to incorporate behavioral evals
as Phase 3 of its scoring, so when it lands, the question becomes
"do you ship evals?" rather than "do you write them by hand?".

## The iteration loop in compressed form

```text
1. Draft the skill from real expertise (extract from a task or
   synthesize from artifacts)
2. Run it on a few prompts and read the traces
3. Note what went wrong + what was wasted effort
4. Revise: add a gotcha, tighten an instruction, bundle a script,
   pick a default instead of a menu
5. Re-run. Did the trace get cleaner?
6. Repeat until traces are boring and outputs are consistent.
```

Stop when you're satisfied with results, feedback is consistently
empty, or you're no longer seeing meaningful improvement between
iterations. Over-iterating produces skills that are over-constrained
and brittle.

## A note on prompting an LLM to revise the skill

If you ask an LLM to propose revisions based on failed assertions
and execution traces, prime it with these guidelines:

- **Generalize from feedback.** A skill will be used across many
  prompts, not just the test cases. Fixes should address
  underlying issues broadly, not patch each example individually.
- **Keep the skill lean.** Fewer, better instructions often
  outperform exhaustive rules. If transcripts show wasted work,
  remove instructions, not add them.
- **Explain the why.** Reasoning-based instructions ("Do X
  because Y tends to cause Z") work better than rigid directives
  ("ALWAYS do X, NEVER do Y"). Models follow instructions more
  reliably when they understand the purpose.

## Source materials

The structured approach in this file is synthesized from
<https://agentskills.io/skill-creation/evaluating-skills> and
<https://agentskills.io/skill-creation/best-practices>, adapted to
the AIDA framework. The detailed eval methodology — including the
`evals/evals.json` schema, with/without baseline runs, assertion
grading, and benchmark aggregation — lives upstream and is
mirrored into the review skill design in
`docs/proposals/review-skill.md`. See
`agents/claude-code-expert/knowledge/external-references.md` for
the full upstream source list.
