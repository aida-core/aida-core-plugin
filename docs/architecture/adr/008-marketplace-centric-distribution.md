---
type: adr
title: "ADR-008: Marketplace-Centric Distribution"
description: "Plugins are distributed through marketplace manifests; users add marketplaces, then install plugins from them."
status: accepted
date: "2025-01-21"
deciders:
  - "@oakensoul"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# ADR-008: Marketplace-Centric Distribution

## Context

AIDA plugins need a distribution strategy that addresses:

- How users discover and install plugins
- How plugin versions are managed
- Where feedback and issues are centralized
- How plugins relate to each other (dependencies, compatibility)

Distribution options:

1. **Direct GitHub**: Users install from individual GitHub repos
2. **Marketplace-Centric**: Central registry with short names and versioning
3. **Package Manager**: Publish to npm, PyPI, or similar
4. **Hybrid**: Support multiple installation methods

## Decision

Use a **Marketplace-Centric** distribution model where:

1. **`aida-marketplace`** is the central registry for all AIDA plugins
2. Users install plugins using short names: `/plugin install core@aida`
3. All feedback/issues go to the `aida-marketplace` repository
4. Plugin repos contain source code; marketplace provides discovery and versioning

### Installation Flow

```bash
# One-time: Add the AIDA marketplace
/plugin marketplace add aida-core/aida-marketplace

# Install plugins by short name
/plugin install core@aida
```

### Naming Convention

| Component                    | Name                           |
| ---------------------------- | ------------------------------ |
| Marketplace repo             | `aida-core/aida-marketplace`   |
| Marketplace name             | `aida`                         |
| Core plugin (in marketplace) | `core`                         |
| Core plugin repo             | `aida-core/aida-core-plugin`   |
| Install command              | `/plugin install core@aida`    |

## Rationale

### Why Marketplace-Centric?

#### 1. Discoverability

- Single place to find all AIDA plugins
- Curated list with descriptions and tags
- Future: Search, categories, popularity metrics

#### 2. Simplified Installation

- Short, memorable names: `core@aida` vs `aida-core/aida-core-plugin`
- Consistent pattern for all plugins
- No need to remember GitHub paths

#### 3. Centralized Versioning

- Marketplace tracks compatible versions
- Can enforce version constraints between plugins
- Single source of truth for "latest stable"

#### 4. Unified Feedback

- All issues in one repository
- Cross-plugin issues easier to track
- Community builds in one place
- Maintainer doesn't need to monitor multiple repos

#### 5. Built-in Claude Support

- Marketplace can include CLAUDE.md with plugin-specific instructions
- Consistent onboarding experience
- Plugin-specific context automatically loaded

#### 6. Future Extensibility

- Plugin dependencies
- Compatibility matrices
- Automated testing across plugin combinations
- Community contributions

### Why Not Direct GitHub?

**Against:**

- Verbose installation: `/plugin install aida-core/aida-core-plugin`
- No central discovery
- Version management per-repo
- Issues scattered across repos
- No namespace/branding

**When to Use:**

- Development/testing: Install from local path or branch
- Fallback: If marketplace is unavailable

### Why Not Package Managers (npm, PyPI)?

**Against:**

- AIDA plugins are Claude Code extensions, not traditional packages
- Would require separate tooling
- Doesn't integrate with Claude Code's plugin system
- Overkill for markdown/config files

## Consequences

### Positive

- Simpler user experience with short names
- Central place for discovery and feedback
- Consistent versioning across plugins
- Clear branding (`@aida` namespace)
- Easier to maintain (single issues repo)
- Built-in onboarding via marketplace CLAUDE.md

### Negative

- Extra step: Must add marketplace first
- Marketplace repo must be maintained
- Version sync between marketplace.json and plugin repos
- Single point of failure (if marketplace repo is down)

### Mitigation

**Extra Step:**

- Document clearly in all plugin READMEs
- One-time setup, then forgotten
- Could automate in future

**Maintenance Burden:**

- Automated version checking (GitHub Actions)
- Clear contribution guidelines
- Semantic versioning for compatibility

**Version Sync:**

- CI to validate marketplace.json versions match plugin repos
- Release automation to update marketplace on plugin release

**Single Point of Failure:**

- Direct GitHub install as documented fallback
- Marketplace is just a JSON file, very stable

## Implementation

### Marketplace Structure

```text
aida-marketplace/
├── .claude-plugin/
│   └── marketplace.json    # Plugin registry
├── README.md               # User-facing docs
├── CLAUDE.md               # Claude context for marketplace
└── docs/
    └── ...                 # Plugin documentation
```

### marketplace.json Format

```json
{
  "name": "aida",
  "description": "AIDA plugins for Claude Code",
  "owner": {
    "name": "oakensoul",
    "email": "...",
    "url": "https://github.com/oakensoul"
  },
  "plugins": [
    {
      "name": "core",
      "source": {
        "type": "github",
        "repo": "aida-core/aida-core-plugin"
      },
      "description": "Core AIDA functionality",
      "version": "0.5.0",
      "tags": ["core", "essential"]
    }
  ]
}
```

### Plugin Repo Requirements

Each plugin repo must have:

- `.claude-plugin/plugin.json` - Plugin manifest
- `README.md` - Documentation
- `CLAUDE.md` - Claude context (optional but recommended)

### Feedback Flow

All user feedback goes to `aida-core/aida-marketplace`:

- Bug reports
- Feature requests
- General feedback
- Cross-plugin issues

Individual plugin repos are for:

- Source code
- Plugin-specific development
- Releases/tags

## Alternatives Considered

### Alternative 1: Direct GitHub Only

**Approach:** Users install directly from GitHub repos

**Pros:**

- Simpler architecture (no marketplace)
- One less repo to maintain

**Cons:**

- Poor discoverability
- Verbose install commands
- No central versioning
- Scattered issues

**Verdict:** Doesn't scale, poor UX

### Alternative 2: Hybrid (Marketplace + Direct)

**Approach:** Support both equally

**Pros:**

- Flexibility for users
- Fallback options

**Cons:**

- Documentation complexity
- Two "blessed" paths confuse users
- Version drift between methods

**Verdict:** Marketplace primary, direct as undocumented fallback only

### Alternative 3: Monorepo

**Approach:** All plugins in one repository

**Pros:**

- Single repo to manage
- Atomic cross-plugin changes
- Simpler versioning

**Cons:**

- Doesn't scale with many plugins
- All-or-nothing releases
- Large repo size
- Harder for community contributions

**Verdict:** Separate repos with marketplace registry is more flexible

## Related Decisions

- [ADR-001: Skills-First Architecture](001-skills-first-architecture.md)
- [ADR-005: Local-First Storage](005-local-first-storage.md)
- [ADR-006: gh CLI for Feedback](006-gh-cli-feedback.md)

## Future Considerations

### Plugin Dependencies

Marketplace could track dependencies:

```json
{
  "name": "workflows",
  "requires": ["core@>=0.5.0"]
}
```

### Compatibility Matrix

Track which plugin versions work together:

```json
{
  "compatibility": {
    "core@0.5.x": ["workflows@0.2.x"]
  }
}
```

### Community Plugins

Allow third-party plugins in marketplace:

- Submission process
- Review/approval workflow
- Verified publisher badges

### Automated Releases

GitHub Actions to:

- Bump marketplace.json when plugin releases
- Validate version compatibility
- Run cross-plugin tests

---

**Decision Record:** @oakensoul, 2025-01-21
**Status:** Accepted
