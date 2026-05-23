---
type: adr
title: "ADR-004: YAML for Questionnaire Definitions"
description: "YAML stores questionnaire definitions consumed by the two-phase API pattern (ADR-010)."
status: accepted
date: "2025-11-01"
deciders:
  - "@oakensoul"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# ADR-004: YAML for Questionnaire Definitions

## Context

AIDA uses interactive questionnaires to configure personal and project skills. Questionnaire definitions need to be:

- Easy to read and modify
- Support multiple question types
- Include help text and defaults
- Extensible for future question types

Format options: JSON, YAML, TOML, Python code, custom DSL.

## Decision

Use **YAML** for questionnaire definitions.

## Rationale

### Why YAML?

- Human-readable and writable
- Comments supported
- Multi-line strings are natural
- Clean syntax without excess punctuation
- Standard for configuration (Ansible, Docker Compose, Kubernetes)

### Example

```yaml
questions:
  - id: coding_standards
    question: "What coding standards do you follow?"
    type: text
    default: "PEP 8"
    help: "Examples: PEP 8, Airbnb, PSR-12"

  - id: work_hours
    question: "What are your working hours?"
    type: choice
    options:
      - "9-5 traditional"
      - "Flexible with core hours"
      - "Async remote"
    default: "Flexible with core hours"
```

### Advantages

- Easy for non-programmers to edit
- Multi-line text natural (help text, descriptions)
- Comments for documentation
- PyYAML library well-supported

## Consequences

### Positive

- ✅ Easy to add new questions
- ✅ Non-technical users can edit
- ✅ Clean, readable format

### Negative

- ❌ YAML quirks (tabs, indentation sensitive)
- ❌ Adds PyYAML dependency

### Mitigation

Validate YAML on load, provide clear error messages.

## Alternatives Considered

- **JSON**: More verbose, no comments, harder to read
- **TOML**: Good but less common, learning curve
- **Python code**: Requires programming knowledge
- **Custom DSL**: Overkill for simple questionnaires

## Related

- [ADR-002: Python for Scripts](002-python-for-scripts.md)

---

**Status**: ✅ Accepted, implemented in M1
