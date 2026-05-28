---
type: reference
name: skill-authoring-patterns
title: Skill Authoring Patterns
description: Reusable patterns for writing skills that calibrate control to task fragility, include gotchas, and use templates / checklists / validation loops where they actually pay off.
version: "1.0.0"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Skill Authoring Patterns

How to write skill bodies that get the agent to do useful work
reliably. These patterns come from the agentskills.io community
documentation, framed against our WHO/HOW/CONTEXT architecture and
the lessons baked into the existing knowledge files.

**When to use this file:** authoring a new skill, reviewing an
existing one for quality, deciding whether a workflow needs explicit
structure or can stay loose.

## Spend the agent's context wisely

Once a skill activates, its full SKILL.md body lands in the agent's
context window alongside conversation history, system context, and
every other active skill. Every token competes for the agent's
attention.

**Add what the agent lacks; omit what it knows.** Project-specific
conventions, domain-specific procedures, the particular tools or
APIs to use — these are signal. General programming knowledge ("PDFs
are a common file format", "HTTP requests can fail") is noise. Cut
anything that wouldn't change the agent's behavior if removed.

For each piece of content, ask: *Would the agent get this wrong
without this instruction?* If the answer is no, cut it. If unsure,
test it.

Skills that don't change the agent's behavior aren't pulling their
weight. If the agent already does the task well without the skill,
the skill isn't earning its tokens.

## Calibrate control to task fragility

Not every part of a skill needs the same level of prescriptiveness.
Match specificity to fragility.

**Give the agent freedom** when multiple approaches are valid and
the task tolerates variation. Explaining *why* tends to work better
than rigid directives — an agent that understands the purpose makes
better context-dependent decisions. A code-review skill can describe
what to look for without prescribing exact steps:

```markdown
Check all database queries for SQL injection (use parameterized queries).
Verify authentication checks on every endpoint.
Look for race conditions in concurrent code paths.
```

**Be prescriptive** when operations are fragile, consistency
matters, or a specific sequence must be followed:

````markdown
## Database migration

Run exactly this sequence:

```bash
python scripts/migrate.py --verify --backup
```

Do not modify the command or add additional flags.
````

Most skills have a mix. Calibrate each part independently.

## Provide defaults, not menus

When multiple tools or approaches could work, pick a default and
mention alternatives briefly. Don't present them as equal options.

```markdown
<!-- Too many options — agent has to choose, often gets it wrong -->
You can use pypdf, pdfplumber, PyMuPDF, or pdf2image...

<!-- Clear default with an escape hatch -->
Use pdfplumber for text extraction. For scanned PDFs requiring OCR,
use pdf2image with pytesseract instead.
```

A menu of equally-weighted options shifts the decision burden onto
the agent and produces inconsistent results across runs. Pick the
right call once, in the skill, where reviewers can argue about it.

## Favor procedures over declarations

A skill should teach the agent *how to approach* a class of problems,
not *what to produce* for a specific instance.

```markdown
<!-- Specific answer — only useful for this exact task -->
Join the `orders` table to `customers` on `customer_id`, filter
where `region = 'EMEA'`, and sum the `amount` column.

<!-- Reusable method — works for any analytical query -->
1. Read the schema from `references/schema.yaml` to find relevant tables
2. Join tables using the `_id` foreign key convention
3. Apply any filters from the user's request as WHERE clauses
4. Aggregate numeric columns as needed and format as a markdown table
```

This doesn't mean skills can't include specifics — output format
templates, hard constraints ("never log PII"), and tool-specific
instructions all belong. The point is that the *approach* should
generalize even when individual details are pinned down.

## Gotchas sections

The highest-value content in many skills is a list of gotchas —
environment-specific facts that defy reasonable assumptions. These
aren't general advice ("handle errors appropriately"); they're
concrete corrections to mistakes the agent will make without being
told otherwise:

```markdown
## Gotchas

- The `users` table uses soft deletes. Queries must include
  `WHERE deleted_at IS NULL` or results will include deactivated
  accounts.
- The user ID is `user_id` in the database, `uid` in the auth
  service, and `accountId` in the billing API. All three refer to
  the same value.
- The `/health` endpoint returns 200 as long as the web server is
  running, even if the database connection is down. Use `/ready`
  to check full service health.
```

Keep gotchas in SKILL.md, not in a `references/` file. The agent
needs to read them *before* encountering the situation. A separate
file works only if the SKILL.md tells the agent precisely when to
load it — and for surprises, the agent often won't recognize the
trigger until it has already gone wrong.

**When the agent makes a mistake you have to correct, that's a new
gotcha.** This is the most direct way to improve a skill: every
correction is a candidate for the gotchas list.

## Output templates

When the agent needs to produce output in a specific format, provide
a template. Agents pattern-match against concrete structures much
more reliably than they follow prose descriptions of structure.

Short templates inline:

````markdown
## Report structure

Use this template, adapting sections as needed:

```markdown
# [Analysis Title]

## Executive summary
[One-paragraph overview of key findings]

## Key findings
- Finding 1 with supporting data

## Recommendations
1. Specific actionable recommendation
```
````

Long templates in `assets/` or `templates/`, referenced from
SKILL.md so they only load when needed.

## Checklists for multi-step workflows

An explicit checklist helps the agent track progress and avoid
skipping steps, especially when steps have dependencies or
validation gates:

```markdown
## Form processing workflow

Progress:
- [ ] Step 1: Analyze the form (run `scripts/analyze_form.py`)
- [ ] Step 2: Create field mapping (edit `fields.json`)
- [ ] Step 3: Validate mapping (run `scripts/validate_fields.py`)
- [ ] Step 4: Fill the form (run `scripts/fill_form.py`)
- [ ] Step 5: Verify output (run `scripts/verify_output.py`)
```

The checkbox syntax invites the agent to walk through the steps in
order and report status, rather than jumping ahead.

## Validation loops

Instruct the agent to validate its own work before moving on.
Pattern: do the work, run a validator (script, reference checklist,
or self-check), fix any issues, and repeat until validation passes.

```markdown
## Editing workflow

1. Make your edits
2. Run validation: `python scripts/validate.py output/`
3. If validation fails:
   - Review the error message
   - Fix the issues
   - Run validation again
4. Only proceed when validation passes
```

A reference document can serve as the "validator" — instruct the
agent to check its work against the reference before finalizing.

## Plan-validate-execute

For batch or destructive operations, have the agent create an
intermediate plan in a structured format, validate it against a
source of truth, and only then execute.

```markdown
## PDF form filling

1. Extract form fields: `python scripts/analyze_form.py input.pdf`
   → `form_fields.json` (lists every field name, type, required-ness)
2. Create `field_values.json` mapping each field name to its
   intended value
3. Validate: `python scripts/validate_fields.py form_fields.json
   field_values.json` (checks every field name exists, types match,
   required fields aren't missing)
4. If validation fails, revise `field_values.json` and re-validate
5. Fill the form: `python scripts/fill_form.py input.pdf
   field_values.json output.pdf`
```

The load-bearing step is step 3: a validator that checks the plan
against the source of truth. Errors like *"Field 'signature_date'
not found — available fields: customer_name, order_total,
signature_date_signed"* give the agent enough information to
self-correct without guessing.

This is similar to the **get-questions / execute** two-phase
pattern AIDA uses for skills like `agent-manager` and `memento`,
but with three phases: gather inputs → validate against source of
truth → execute. Use plan-validate-execute when the cost of an
error is high enough to justify the validation overhead.

## Bundling reusable scripts

If you find the agent independently reinventing the same logic each
run — building a chart, parsing a specific format, validating output
— bundle the script into the skill's `scripts/` directory once and
have the SKILL.md reference it.

Heuristic: if it appears in three skill runs in roughly the same
form, it should be a script. Two is a coincidence; three is a
pattern; four is wasted tokens.

## Patterns we use here

Beyond the agentskills.io patterns, the existing AIDA skills lean
heavily on:

- **Two-phase API** — get-questions then execute. The skill asks
  any clarifying questions first (returns them as a structured
  list), then executes once the answers are in. Side-effects only
  ever happen in execute. See `agent-manager`, `memento`,
  `plugin-manager`.
- **Atomic primitives** — when a skill writes multiple related
  files, the I/O primitive enforces atomicity rather than relying
  on the skill body to remember the right order. See
  `decisions_log.write_decisions` (#144) for the canonical
  example: writes JSON and regenerates Markdown in one call; no
  exported way to write one without the other.
- **Knowledge with the agent, process with the skill** — when an
  LLM workflow needs reasoning context, the skill loads it from
  the relevant agent's knowledge directory rather than embedding
  the context in the skill. Lets the agent be refreshed without
  rebuilding the skill.

## What this doesn't replace

The architectural decisions about *which* extension type to create,
*what* should live in a skill vs. an agent vs. knowledge, and *how*
to organize a plugin remain in `framework-design-principles.md` and
`extension-types.md`. This file is about how to write the body of a
skill once you know that a skill is the right tool.

## Source materials

These patterns are synthesized from
<https://agentskills.io/skill-creation/best-practices> and adapted
to the AIDA framework. See
`agents/claude-code-expert/knowledge/external-references.md` for
the full list of upstream sources informing this agent's
knowledge.
