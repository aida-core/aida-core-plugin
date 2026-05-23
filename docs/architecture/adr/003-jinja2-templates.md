---
type: adr
title: "ADR-003: Jinja2 for Template Rendering"
description: "Jinja2 is the template engine for scaffold and skill rendering across the plugin."
status: accepted
date: "2025-11-01"
deciders:
  - "@oakensoul"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# ADR-003: Jinja2 for Template Rendering

## Context

AIDA needs to generate skill files from templates, incorporating user responses from questionnaires. Templates must support:

- Variable substitution
- Conditional content
- Loops and iteration
- Readable syntax

Options: String formatting, Jinja2, Mako, Mustache, or custom templating.

## Decision

Use **Jinja2** for all template rendering.

## Rationale

### Why Jinja2?

- Industry standard (Ansible, Flask, Salt use it)
- Powerful: variables, conditionals, loops, filters, includes
- Well-documented and mature
- Great error messages
- Widely known by developers

### Advantages

- `{{ variable }}` syntax is clear and familiar
- `{% if %}` conditionals for optional content
- `{% for %}` loops for repeated elements
- Filters: `{{ name | title }}`
- Template inheritance and includes

### Example

```jinja2
---
name: {{ skill_name }}
---

# {{ skill_name | title }}

{% if coding_standards %}
## Coding Standards
{{ coding_standards }}
{% endif %}
```

## Consequences

### Positive

- ✅ Powerful templating with minimal learning curve
- ✅ Great documentation and community support
- ✅ Easy to debug with clear error messages

### Negative

- ❌ Adds Python dependency (acceptable given ADR-002)
- ❌ Learning curve for template syntax (minimal)

## Alternatives Considered

- **String formatting**: Too limited, hard to read complex templates
- **Mustache**: Simpler but less powerful, no conditionals
- **Custom solution**: Not worth the effort

## Related

- [ADR-002: Python for Scripts](002-python-for-scripts.md)

---

**Status**: ✅ Accepted, implemented in M1
