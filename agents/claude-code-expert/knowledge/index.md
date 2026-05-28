---
type: reference
name: index
title: Claude Code Expert Knowledge Index
description: Catalog of knowledge documents for the claude-code-expert agent
version: "1.0.0"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# Knowledge Index

This directory contains reference documentation for the claude-code-expert
agent. Use this index to find the right document for your needs.

## Documents

### framework-design-principles.md

**When to use:** For architectural decisions and quality standards

Contains:

- The WHO/HOW/CONTEXT framework
- Quality standards for all extension types
- The Consultant Rule (how agents should work)
- What belongs vs doesn't belong in each type

This is the **authoritative reference** for extension architecture.

### extension-types.md

**When to use:** When deciding which type of extension to create

Contains:

- Decision tree for choosing between agent, skill, plugin, and hook
- Characteristics of each extension type
- Example use cases for each type

### design-patterns.md

**When to use:** When designing the structure of an extension

Contains:

- Common architectural patterns
- Best practices for each extension type
- Template customization guidelines
- Plugin organization patterns

### plugin-development.md

**When to use:** When creating or distributing plugins

Contains:

- Plugin structure and required files
- plugin.json schema (all fields)
- marketplace.json for publishing
- Versioning and dependencies
- Installation and management

### claude-md-files.md

**When to use:** When creating or maintaining CLAUDE.md memory files

Contains:

- Memory vs Settings distinction
- Memory file hierarchy (Enterprise, Project, User, Parent)
- CLAUDE.local.md for personal project-specific overrides
- Modular rules system (`.claude/rules/` with glob patterns)
- Auto memory vs user-maintained CLAUDE.md distinction
- Import system (`@path/to/file` syntax, home-directory imports)
- `/memory` command usage
- Content guidelines and best practices
- Multi-file organization patterns

### settings.md

**When to use:** When configuring Claude Code behavior via settings.json

Contains:

- Settings file locations and precedence
- Core settings (model, env, permissions, hooks)
- MCP server configuration (transports, scopes, OAuth)
- Sandbox network configuration and filesystem controls
- Advanced settings (status line, sandbox, plugins, 23+ new fields)
- Expanded sandbox options (network, filesystem, commands)
- Authentication configuration
- Environment variables reference
- Example configurations for different scenarios

### skills.md

**When to use:** When creating or configuring skills (SKILL.md files)

Contains:

- Skill frontmatter fields and locations
- Skill discovery and invocation patterns
- String substitution syntax (`$ARGUMENTS`, `$N`, etc.)
- Context fork mode for running skills in subagents
- Agent Skills open standard (agentskills.io)
- Dynamic context injection with shell preprocessing

### subagents.md

**When to use:** When creating or configuring subagents (.md agent files)

Contains:

- Built-in subagent types (Explore, Plan, Bash, etc.)
- Subagent frontmatter fields and scopes
- Permission modes (default, acceptEdits, dontAsk, etc.)
- Persistent memory for subagents
- Background execution and worktree isolation
- Agent teams overview

### hooks.md

**When to use:** When implementing lifecycle automation via hooks

Contains:

- 17 hook lifecycle events across 6 categories, async hooks support
- 3 hook types: command (deterministic), prompt (LLM), agent (agentic)
- Configuration structure and matcher patterns
- Hook execution model (stdin JSON, exit codes, JSON output)
- Async hooks for background execution
- hookSpecificOutput and decision control patterns
- Security considerations
- Common patterns (formatting, logging, blocking, quality gates)

### skill-authoring-patterns.md

**When to use:** Writing a new skill body, reviewing an existing
skill for quality, deciding how loose vs. how prescriptive a
workflow should be

Contains:

- Spend the agent's context wisely (add what it lacks, omit what it
  knows)
- Calibrate control to task fragility (freedom vs. prescriptive)
- Provide defaults, not menus
- Favor procedures over declarations
- Gotchas sections — the highest-value content in many skills
- Output templates, checklists, validation loops, plan-validate-execute
- Bundling reusable scripts
- AIDA-specific patterns (two-phase API, atomic primitives, knowledge
  with the agent)

### skill-iteration.md

**When to use:** Authoring a new skill, troubleshooting a skill that
fails inconsistently, deciding whether a skill needs evals

Contains:

- Start from real expertise (extract from a hands-on task or
  synthesize from project artifacts)
- Refine with real execution (read execution traces, not just
  outputs)
- When evals pay off and when they're overkill
- The iteration loop in compressed form
- How to prompt an LLM to propose revisions

### evaluating-extensions.md

**When to use:** When the review skill's Phase 2 LLM grading runs;
this is the reasoning context that informs the narrative critique

Contains:

- The three-phase review model (deterministic / LLM / behavioral)
- What "excellent" looks like per extension type (agents, skills,
  plugins)
- Cross-cutting failure modes the LLM should catch (semantic
  mismatch, overlapping knowledge, missing gotchas, iteration debt)
- How to write the narrative review
- Anti-patterns specific to LLM grading
- Calibration notes for the A–F scale

### external-references.md

**When to use:** When rebuilding or refreshing this agent's knowledge

Contains:

- Upstream URLs that knowledge files derive from
- Mapping of URL → which knowledge file it informs
- Guidance for refresh workflow (walk list, update relevant files,
  preserve local additions)
- Source materials for the review-skill rubric and Phase 3 behavioral
  evals design

## Quick Reference

| Question                                        | Document                        |
| ----------------------------------------------- | ------------------------------- |
| "What's the architecture framework?"            | framework-design-principles.md  |
| "What belongs in an agent vs skill?"            | framework-design-principles.md  |
| "What does 'excellent' look like?"              | framework-design-principles.md  |
| "Should I create an agent or skill?"            | extension-types.md              |
| "What's the difference between types?"          | extension-types.md              |
| "How should I structure my agent?"              | design-patterns.md              |
| "What are best practices?"                      | design-patterns.md              |
| "How do I organize a plugin?"                   | design-patterns.md              |
| "What goes in plugin.json?"                     | plugin-development.md           |
| "How do I publish a plugin?"                    | plugin-development.md           |
| "How do plugins work?"                          | plugin-development.md           |
| "How do I create a skill?"                      | skills.md                       |
| "What frontmatter does a skill use?"            | skills.md                       |
| "What are the built-in agents?"                 | subagents.md                    |
| "How do I create a custom agent?"               | subagents.md                    |
| "How do agent teams work?"                      | subagents.md                    |
| "What permission modes exist?"                  | subagents.md                    |
| "What should CLAUDE.md contain?"                | claude-md-files.md              |
| "Where do CLAUDE.md files go?"                  | claude-md-files.md              |
| "How do I write project instructions?"          | claude-md-files.md              |
| "How do memory files work?"                     | claude-md-files.md              |
| "How do I import files in CLAUDE.md?"           | claude-md-files.md              |
| "What goes in settings.json?"                   | settings.md                     |
| "How do I configure permissions?"               | settings.md                     |
| "Memory vs settings - when to use?"             | settings.md, claude-md-files.md |
| "How do I configure MCP servers?"               | settings.md                     |
| "What are prompt and agent hooks?"              | hooks.md                        |
| "How do I set up agent team quality gates?"     | hooks.md, subagents.md          |
| "How do hooks work?"                            | hooks.md                        |
| "How do I auto-format code?"                    | hooks.md                        |
| "How do I block dangerous operations?"          | hooks.md                        |
| "What lifecycle events exist?"                  | hooks.md                        |
| "How do I write a good skill body?"             | skill-authoring-patterns.md     |
| "When should the agent have freedom vs. prescription?" | skill-authoring-patterns.md |
| "What's a gotchas section?"                     | skill-authoring-patterns.md     |
| "Defaults vs menus?"                            | skill-authoring-patterns.md     |
| "Procedures vs declarations?"                   | skill-authoring-patterns.md     |
| "Plan-validate-execute pattern?"                | skill-authoring-patterns.md     |
| "How do skills get good?"                       | skill-iteration.md              |
| "How do I iterate on a skill?"                  | skill-iteration.md              |
| "When should I add evals?"                      | skill-iteration.md              |
| "How do I read execution traces?"               | skill-iteration.md              |
| "How does the review skill grade extensions?"   | evaluating-extensions.md        |
| "What does 'excellent' look like for X?"        | evaluating-extensions.md, framework-design-principles.md |
| "What should the LLM reviewer catch?"           | evaluating-extensions.md        |

## External Resources

For edge cases or latest features not covered here, fetch the official
Claude Code documentation:

- Claude Code Docs: <https://code.claude.com/docs/en/overview>
- Agent SDK: <https://platform.claude.com/docs/en/agent-sdk/overview>

Use WebFetch tool to retrieve current documentation when:

- User asks about features not covered in knowledge/
- Schema or API has potentially changed
- Best practices need verification against latest docs
