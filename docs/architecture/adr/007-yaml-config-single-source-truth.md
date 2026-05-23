---
type: adr
title: "ADR-007: YAML Configuration as Single Source of Truth"
description: ".claude/aida-project-context.yml is the single source of truth for project configuration; SKILL.md is rendered from it."
status: accepted
date: "2025-11-05"
deciders:
  - "@oakensoul"
supersedes: "Complex conditional questionnaire logic"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# ADR-007: YAML Configuration as Single Source of Truth

## Context

Project configuration requires gathering ~30 different facts and preferences. Original approach used complex
conditional logic in YAML questionnaires with `when` clauses to determine which questions to ask.

### Problems with conditional questionnaires

- Hard to debug conditional expressions
- Difficult to understand question flow
- No persistence of detected facts
- Questions repeated on reconfiguration
- Complex state management

## Decision

Use **YAML configuration files as the single source of truth** with a "detect → save → ask gaps" approach.

## Architecture

### Flow

```text
1. Detect ALL facts → Save to .claude/aida-project-context.yml (with nulls for unknowns)
2. Load YAML → Identify null fields
3. Ask ONLY about nulls (0-3 questions vs 22)
4. Update YAML → Render skills from YAML
```

### YAML Structure

```yaml
version: 0.2.0
config_complete: false

# Auto-detected facts (booleans, strings)
vcs: {type: git, has_vcs: true, uses_worktrees: true, ...}
files: {has_readme: true, has_license: true, ...}
languages: {primary: Python, all: [...]}
tools: {detected: [Git], ...}

# Inferred characteristics (high confidence guesses)
inferred: {project_type: Unknown, team_collaboration: Solo, ...}

# User preferences (nulls until answered)
preferences: {branching_model: null, issue_tracking: null, ...}
```

## Rationale

### Benefits

1. **Transparency** - Config file is human-readable and editable
2. **Idempotency** - Can run config multiple times safely
3. **Simplicity** - No complex conditional evaluation logic
4. **Persistence** - Facts detected once, reused everywhere
5. **Efficiency** - Massive question reduction (22 → 2)

### Implementation

- `detect_project_info()` - Detects all facts with structured schema
- `get_questions()` - Loads YAML, asks only about nulls
- `configure()` - Updates YAML, renders skills from YAML

## Consequences

### Positive

- ✅ 90% reduction in user questions
- ✅ Config file visible and editable by users
- ✅ Skills auto-generate from config
- ✅ Reconfiguration is simple (just update YAML fields)
- ✅ Facts detected once, cached in YAML

### Negative

- ⚠️ YAML file must be kept in sync with templates
- ⚠️ Template variables must map from YAML structure
- ⚠️ More complex initial detection logic

### Mitigation

- Auto-save YAML in Phase 1 (detection happens automatically)
- Template mapping is one-way (YAML → templates, no reverse)
- Comprehensive fact detection utilities

## Comparison

### Before (Questionnaire-Based)

```text
User runs /aida config
  → Load questionnaire
  → Evaluate conditionals for each question
  → Ask 22 questions
  → Render skill from responses
```

### After (Config-Driven)

```text
User runs /aida config
  → Detect all facts → Save to YAML
  → Identify nulls in YAML
  → Ask 0-3 questions
  → Update YAML → Render skill from YAML
```

## Alternatives Considered

1. **Keep conditional questionnaires** - Complex, hard to debug
2. **SQLite database** - Overkill, adds dependency
3. **Multiple JSON files** - Fragmented, harder to understand
4. **No persistence** - Would require re-asking questions every time

## Related

- [ADR-004: YAML for Questionnaires](004-yaml-questionnaires.md) - Uses YAML for questions
- [ADR-005: Local-First Storage](005-local-first-storage.md) - Where YAML files are stored
- [config-driven-approach.md](../../skills/aida/references/config-driven-approach.md) - Implementation guide

---

**Impact**: High - This is the foundation of AIDA's configuration system

**Status**: Implemented and working in v0.2.0
