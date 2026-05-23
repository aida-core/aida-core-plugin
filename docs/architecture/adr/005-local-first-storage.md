---
type: adr
title: "ADR-005: Local-First Storage"
description: "AIDA state lives on the user's machine (~/.claude/, .claude/); no remote or cloud storage by default."
status: accepted
date: "2025-11-01"
deciders:
  - "@oakensoul"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# ADR-005: Local-First Storage

## Context

AIDA needs to persist user data including:

- Personal preferences and work patterns
- Project-specific context
- Configuration settings
- Generated skills

Storage options:

1. Local file system only
2. Cloud storage with local cache
3. Database (SQLite, PostgreSQL)
4. Hybrid (local + optional cloud sync)

Considerations: privacy, offline support, simplicity, sync, backup.

## Decision

Store all AIDA data **locally in the file system** with no cloud storage or database in M1.

### Locations

- Global: `~/.claude/`
- Project: `.claude/` (in project root)

### Format

Markdown files (skills), JSON (settings)

## Rationale

### Why Local-First?

1. **Privacy**: User data never leaves their machine
2. **Offline**: Works without internet connection
3. **Simplicity**: No server infrastructure, no sync logic
4. **Ownership**: User fully controls their data
5. **Backup**: Standard file backup tools work
6. **Version Control**: Skills can be committed to git
7. **Transparency**: Users can see and edit all files

### File System Benefits

- No database setup or maintenance
- Easy to debug and inspect
- Natural for skills (markdown files)
- Git-friendly for project skills

## Consequences

### Positive

- ✅ Complete privacy - data never transmitted
- ✅ Works offline always
- ✅ Zero infrastructure cost
- ✅ Easy backup and restore
- ✅ Git integration natural
- ✅ Transparent to users

### Negative

- ❌ No cross-device sync
- ❌ No collaborative editing
- ❌ No cloud backup (user responsibility)
- ❌ No version history (unless in git)

### Mitigation

- Document manual sync methods (git, rsync, cloud storage)
- Future: Optional cloud sync as addon
- For now: Simplicity trumps convenience

## Implementation

### Directory Structure

```text
~/.claude/                  # Global config
├── skills/
│   ├── user-context/
│   └── aida-core/
└── settings.json

your-project/.claude/       # Project config
├── skills/
│   ├── project-context/
│   └── project-documentation/
└── settings.json
```

### File Permissions

- Owner read/write only (644)
- Standard Unix permissions
- No special encryption (future consideration)

### Git Integration

**Recommended** `.gitignore`:

```text
# Global user-level config lives in ~/.claude/ (not in project repos)
# Project skills live in .claude/ and SHOULD be committed

# But DO commit project skills
!.claude/skills/project-*
```

**Rationale**: Personal skills are personal; project skills should be shared.

## Alternatives Considered

### Alternative 1: SQLite Database

**Approach**: Store skills and settings in SQLite

**Pros**: Structured queries, transactions, indexing

#### Cons

- Binary format (not human-readable)
- Harder to edit manually
- Git-unfriendly
- Overkill for simple key-value storage

**Verdict**: Files are simpler and more transparent

### Alternative 2: Cloud Storage (S3, etc.)

**Approach**: Store skills in cloud with local cache

**Pros**: Cross-device sync, automatic backup

#### Cons

- Privacy concerns
- Requires internet
- Infrastructure cost
- Sync conflicts
- Vendor lock-in
- Complexity

**Verdict**: Violates privacy-first principle, too complex for M1

### Alternative 3: Hybrid (Local + Optional Cloud)

**Approach**: Local storage with optional cloud sync

**Pros**: Best of both worlds when cloud enabled

#### Cons

- Significant complexity
- Two codepaths to maintain
- Sync conflict resolution
- Not minimal for MLP

**Verdict**: Could add in M5+, not for M1

## Future Considerations

### M5+ Cloud Sync (Optional)

Could add optional cloud sync while keeping local-first:

- Default: Local only
- Opt-in: Enable cloud sync
- Mechanism: rsync, Dropbox, git, custom

### M5+ Encryption

Could add optional encryption:

- Skills encrypted at rest
- User-provided passphrase
- Transparent to Claude Code

### M6+ Collaborative Features

Could add team features:

- Shared skill repositories
- Collaborative editing
- Approval workflows

**Key**: Always keep local-first as foundation

## Related

- [ADR-001: Skills-First Architecture](001-skills-first-architecture.md)
- [ADR-006: gh CLI for Feedback](006-gh-cli-feedback.md)

---

**Status**: ✅ Accepted, implemented in M1
