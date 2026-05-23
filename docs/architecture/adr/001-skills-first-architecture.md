---
type: adr
title: "ADR-001: Skills-First Architecture"
description: "Skills (SKILL.md files combining process + execution) are the primary extension type; agents and knowledge layer on top."
status: accepted
date: "2025-11-01"
deciders:
  - "@oakensoul"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# ADR-001: Skills-First Architecture

## Context

AIDA needs a core architectural pattern that defines how it provides value to users. There are several possible approaches:

1. **Memory-First**: Store conversation history and automatically build context
2. **Automation-First**: Focus on workflow automation and task execution
3. **Skills-First**: Provide persistent context through skill files
4. **Hybrid**: Combine multiple approaches

The architectural choice affects:

- User mental model
- Implementation complexity
- Maintenance burden
- Extensibility
- Privacy concerns

## Decision

We will use a **Skills-First** architecture for AIDA M1 (Minimum Lovable Product).

Skills are markdown files with YAML frontmatter that provide context to Claude. They are:

- **Persistent**: Stored as files, version-controllable
- **Explicit**: Users can read and edit them
- **Shareable**: Can be shared with teams
- **Scoped**: Global (personal) or project-specific

## Rationale

### Why Skills-First?

#### 1. Simplicity

- Skills are just markdown files
- No database or complex state management
- Easy to understand and debug
- Low implementation complexity

#### 2. Transparency

- Users can see exactly what context Claude has
- No "black box" behavior
- Users can manually edit skills
- Full control over content

#### 3. Shareability

- Skills can be committed to git
- Teams can share project skills
- Community can create and share skills
- No special export/import needed

#### 4. Privacy

- Skills stay local (file system)
- No network transmission required
- No cloud storage needed
- User owns their data

#### 5. Maintainability

- Skills don't require updates unless project changes
- No automatic sync issues
- No stale data problems
- User decides when to update

#### 6. Progressive Enhancement

- Start with skills (simple)
- Add memory later (complex)
- Add automation later (workflows)
- Natural upgrade path

### Why Not Memory-First?

**Against**:

- Requires conversation tracking
- State management complexity
- Synchronization issues
- Privacy concerns (where stored?)
- Maintenance burden (keeping fresh)
- Not lovable for M1

**Could Add Later**:

- Auto-updating skills from conversations
- Decision tracking
- Context summaries

### Why Not Automation-First?

**Against**:

- Higher complexity
- More prone to breaking
- Requires workflow design
- Not the core problem we're solving

**The Real Problem**:
Users don't want automation primarily; they want Claude to remember their context.

**Could Add Later**:

- `/aida implement` workflow
- `/start-day`, `/end-day` routines
- GitHub integration automation

## Consequences

### Positive

✅ **Quick to implement**: Skills are just files, no complex systems

✅ **Easy to explain**: "Skills are context files for Claude"

✅ **Lovable**: Users immediately see value

✅ **Extensible**: Can add memory and automation later

✅ **Privacy-first**: All data local

✅ **Version-controllable**: Skills can be in git

✅ **Shareable**: Teams benefit from shared skills

### Negative

❌ **Manual updates**: Skills don't auto-update from conversations

❌ **No memory**: AIDA doesn't remember what you did yesterday

❌ **No automation**: Can't automate workflows (yet)

❌ **User effort**: Users must configure skills explicitly

### Mitigation Strategies

For negative consequences:

**Manual Updates**:

- Make `/aida config` fast and easy
- Provide smart defaults from inference
- Future: Add auto-skill-update feature

**No Memory**:

- M2: Add decision tracking
- M3: Add memory management skill
- Future: Optional memory layer

**No Automation**:

- M4: Add workflow commands
- Future: Workflow automation layer

**User Effort**:

- Questionnaire-driven setup (< 5 minutes)
- Intelligent inference reduces questions
- Pre-built templates for common scenarios

## Implementation Notes

### Skill Structure

```yaml
---
name: skill-name
description: What this skill provides
scope: global|project
---

# Skill Title

Markdown content that Claude reads as context.
```

### Skill Types

**Personal Skills** (`~/.claude/skills/`):

- `user-context/` - Environment, preferences, and coding standards
- `aida-core/` - AIDA management knowledge

**Project Skills** (`.claude/skills/`):

- `project-context/` - Architecture, stack
- `project-documentation/` - Documentation standards

### Loading Mechanism

Claude Code loads skills automatically:

1. At startup, scan `~/.claude/skills/`
2. If in project, scan `.claude/skills/`
3. Parse frontmatter and content
4. Provide as context to all conversations

No AIDA code runs at runtime - just skill loading.

## Alternatives Considered

### Alternative 1: Memory-First with SQLite

**Approach**: Store conversation history in SQLite database, auto-extract context

**Pros**:

- Automatic context building
- No manual configuration
- Remembers past conversations

**Cons**:

- Database complexity
- Privacy concerns
- State synchronization issues
- Harder to debug and understand
- Higher maintenance burden

**Why Rejected**: Too complex for M1, privacy issues

### Alternative 2: Automation-First with Workflows

**Approach**: Focus on automating common tasks (commits, PRs, daily routines)

**Pros**:

- Tangible time savings
- "Wow" factor from automation

**Cons**:

- Doesn't solve core context problem
- Brittle (workflows break)
- High implementation cost
- Not the one killer use case

**Why Rejected**: Automation isn't the core problem users face

### Alternative 3: Hybrid (Skills + Memory)

**Approach**: Combine skills (manual) and memory (automatic)

**Pros**:

- Best of both worlds
- Flexible approach

**Cons**:

- Significantly more complex
- Longer time to M1
- Two systems to maintain
- Confusing for users (which one?)

**Why Rejected**: Too complex for MLP, violates "minimum" constraint

## Related Decisions

- [ADR-002: Python for Installation Scripts](002-python-for-scripts.md)
- [ADR-003: Jinja2 for Templates](003-jinja2-templates.md)
- [ADR-005: Local-First Storage](005-local-first-storage.md)

## Future Considerations

Skills-First doesn't preclude adding other features later:

**M5+ Memory Layer**:

- Auto-updating skills from conversations
- `memory/` directory alongside `skills/`
- Opt-in memory tracking

**M5+ Automation Layer**:

- Workflow commands built on top of skills
- Skills provide context, workflows automate

**M6+ Team Collaboration**:

- Shared skill libraries
- Team-wide context
- Cloud sync (optional)

## Success Metrics

How to measure if this decision was right:

- **Setup time**: < 5 minutes for most users
- **User feedback**: "This is exactly what I needed"
- **Adoption**: Users create custom skills
- **Team usage**: Skills committed to repos
- **Extensibility**: Easy to add memory/automation later

## References

- [AIDA Architecture](../../ARCHITECTURE.md)
- [MLP Scope](../../README.md#quick-start)
- [The One Killer Use Case](../../README.md#use-cases)

---

**Decision Record**: @oakensoul, 2025-11-01
**Status**: ✅ Accepted, implemented in M1
