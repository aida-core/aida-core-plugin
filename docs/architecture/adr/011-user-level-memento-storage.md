---
type: adr
title: "ADR-011: User-Level Memento Storage with Project Namespacing"
description: "Mementos live under ~/.claude/projects/<project>/memory/ with project namespacing — per-user, not per-checkout."
status: accepted
date: "2026-02-16"
deciders:
  - "@oakensoul"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# ADR-011: User-Level Memento Storage with Project Namespacing

## Context

Mementos are lightweight session snapshots that help Claude resume work
after `/clear`, `/compact`, or in new conversations. They capture:

- **Context**: What you're working on
- **Progress**: What's been completed, in progress, pending
- **Decisions**: Key architectural or implementation decisions
- **Next Steps**: Where to pick up work

Storage location affects several concerns:

1. **Persistence**: Survive project directory changes, deletion
2. **Discoverability**: Easy to find across projects
3. **Isolation**: Project-specific mementos don't pollute others
4. **Cross-Project Workflows**: Work spanning multiple repositories
5. **Cleanup**: Archive completed mementos without losing them

Possible storage approaches:

- **Project-Level**: `.claude/memento/` in each project
- **User-Level**: `~/.claude/memento/` with flat structure
- **User-Level with Namespacing**: `~/.claude/memento/` with project
  slug in filename
- **Database**: SQLite or similar structured storage

## Decision

Use **user-level storage** (`~/.claude/memento/`) with **project
namespacing** via filename prefixes.

### Storage Structure

**Mementos Directory**:

```text
~/.claude/memento/
├── aida-core-plugin--fix-auth-bug.md
├── aida-core-plugin--add-memento-skill.md
├── personal-website--redesign-homepage.md
├── client-project--implement-api.md
└── .completed/
    ├── aida-core-plugin--launch-prep.md
    └── personal-website--seo-optimization.md
```

**Filename Format**: `{project-slug}--{memento-slug}.md`

**Project Slug**:

- Derived from project directory name
- Example: `/path/to/aida-core-plugin` → `aida-core-plugin`
- Validated against path traversal (no `..`, `/`, `\`)
- Sanitized (alphanumeric, hyphens, underscores, dots only)

**Memento Slug**:

- Derived from description (kebab-case)
- Example: "Fix auth token expiry" → `fix-auth-token-expiry`
- Validated (lowercase letters, numbers, hyphens only)
- Max length: 50 characters

**Archive Directory**: `.completed/` subdirectory

- Completed mementos moved here
- Same filename format
- Preserves history without cluttering active list

### Implementation

**Filename Construction** (`memento.py`):

```python
def make_memento_filename(project_name: str, slug: str) -> str:
    """Create namespaced memento filename.

    Args:
        project_name: Project directory name (e.g., 'aida-core-plugin')
        slug: Memento slug (e.g., 'fix-auth-bug')

    Returns:
        Filename like 'aida-core-plugin--fix-auth-bug.md'
    """
    # Validate project name (no '--' separator)
    if '--' in project_name:
        raise ValueError("Project name cannot contain '--'")

    return f"{project_name}--{slug}.md"
```

**Filename Parsing**:

```python
def parse_memento_filename(filename: str) -> Tuple[str, str]:
    """Parse namespaced filename into project and slug.

    Args:
        filename: 'aida-core-plugin--fix-auth-bug.md'

    Returns:
        ('aida-core-plugin', 'fix-auth-bug')
    """
    name = filename.removesuffix('.md')
    idx = name.find('--')
    if idx < 0:
        raise ValueError("Missing '--' separator")

    project = name[:idx]
    slug = name[idx + 2:]
    return project, slug
```

**Project Detection**:

```python
def get_project_context() -> Dict[str, Any]:
    """Detect project name from git repository.

    Walks up directories looking for .git, uses directory name
    as project slug. Falls back to cwd name if not in git repo.
    """
    cwd = Path.cwd()

    # Find git root
    for parent in [cwd] + list(cwd.parents):
        if (parent / '.git').exists():
            return {
                'name': parent.name,
                'path': str(parent),
                'repo': get_git_remote(parent),
                'branch': get_git_branch(parent)
            }

    # Fallback to cwd
    return {
        'name': cwd.name,
        'path': str(cwd),
        'repo': '',
        'branch': ''
    }
```

**Listing with Filtering**:

```python
def list_mementos(
    filter_status: str = 'active',
    project_filter: Optional[str] = None,
    all_projects: bool = False
) -> List[Dict[str, Any]]:
    """List mementos, optionally filtered by project.

    Args:
        filter_status: 'active', 'completed', 'all'
        project_filter: Specific project name (e.g., 'aida-core-plugin')
        all_projects: If True, show all projects

    Returns:
        List of memento metadata dicts
    """
    if not all_projects and not project_filter:
        # Default: current project only
        project_filter = get_project_context()['name']

    mementos = []
    for md_file in memento_dir.glob('*.md'):
        project, slug = parse_memento_filename(md_file.name)

        # Apply project filter
        if project_filter and project != project_filter:
            continue

        # Parse frontmatter
        content = md_file.read_text()
        frontmatter, _ = parse_frontmatter(content)

        mementos.append({
            'slug': slug,
            'project': project,
            'description': frontmatter.get('description'),
            'status': frontmatter.get('status'),
            'path': str(md_file)
        })

    return mementos
```

**Size Limit**: 100KB per memento

- Lightweight session snapshots, not full documentation
- Enforced in `safe_json_load()` for memento payloads
- Prevents resource exhaustion

## Rationale

### Why User-Level Storage?

**Persistence**:

- Survives project directory moves/renames
- Survives project deletion (intentional safety)
- Available even if project not checked out

**Cross-Project Workflows**:

- Work spanning multiple repositories
- Can reference mementos from other projects
- List all active work across projects

**Single Source of Truth**:

- One location for all mementos
- Easy backups (backup `~/.claude/`)
- Consistent permissions (user-owned)

**Discoverability**:

- `aida memento list --all` shows everything
- No need to remember which project has mementos
- Search across all mementos

### Why Project Namespacing?

**Isolation**:

- Project-specific mementos clearly identified
- No slug conflicts between projects
- Can have `fix-bug` in multiple projects

**Filtering**:

- List mementos for current project only (default)
- Or list all projects (`--all`)
- Or filter to specific project (`--project=foo`)

**Organization**:

- Filename conveys project at a glance
- Alphabetical sorting groups by project
- Easy to identify orphaned mementos

**Migration**:

- If project renamed, mementos stay with old name
- Can bulk-rename files if needed
- Clear audit trail

### Why Filename Prefix vs Subdirectories?

**Filename Prefix** (`project--slug.md`):

- Flat structure (simple)
- Glob filters easy (`project--*.md`)
- No empty directories
- Easy to rename projects (bulk file rename)

**Subdirectories** (`project/slug.md`):

- Would require directory management
- Empty directories after cleanup
- Harder to list all projects
- More filesystem operations

**Verdict**: Filename prefix is simpler and more robust.

### Why Archive Directory?

**Cleanup Without Loss**:

- Completed mementos moved to `.completed/`
- Keeps active list clean
- History preserved for reference

**Resumable**:

- Can "uncomplete" by moving back
- Audit trail of completed work
- No data loss

**Performance**:

- Fewer files in main directory
- Faster listing of active mementos
- Archive can be large without impact

### Why 100KB Size Limit?

**Lightweight Snapshots**:

- Mementos are session context, not full docs
- Should be quick to read and render
- Forces concise, focused content

**Resource Protection**:

- Prevents accidental large pastes
- Prevents memory exhaustion
- Prevents slow file operations

**Comparison**:

- General JSON limit: 1MB (config files)
- Memento limit: 100KB (session snapshots)
- Rationale: Different use cases, different limits

## Consequences

### Positive

- Survives project directory changes
- Enables cross-project workflows
- Single backup location
- Easy to list all work
- No slug conflicts between projects
- Clean archive for completed work
- Flat structure (simple)
- Fast filtering by project

### Negative

- Not in project directory (less discoverable for teams)
- Project rename doesn't auto-update mementos
- Requires project name validation
- Filename parsing overhead
- Manual cleanup if project deleted

### Mitigation

**Team Discoverability**:

- Mementos are personal session snapshots (not team docs)
- Team documentation goes in project repo
- Could add project-level `.claude/mementos.md` index

**Project Rename**:

- Provide `aida memento migrate` command
- Bulk rename files when project renamed
- Log warning if project name mismatch

**Cleanup**:

- Provide `aida memento clean` to remove orphans
- List mementos with missing projects
- Prompt to archive or delete

**Validation**:

- Centralized in `validate_project_name()`
- Clear error messages
- Suggest fixes (sanitize automatically)

## Implementation Notes

### Directory Structure

**Initialization** (`memento.py`):

```python
MEMENTOS_DIR = Path.home() / '.claude' / 'memento'
ARCHIVE_DIR = MEMENTOS_DIR / '.completed'

def get_user_mementos_dir() -> Path:
    """Get user-level mementos directory."""
    return MEMENTOS_DIR

def get_user_archive_dir() -> Path:
    """Get archive directory for completed mementos."""
    return ARCHIVE_DIR

# Ensure directories exist with restrictive permissions
MEMENTOS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
```

**Security**: Directories are `0o700` (owner-only access).

### Path Validation

**Project Name Validation**:

```python
def validate_project_name(name: str) -> Tuple[bool, Optional[str]]:
    """Validate project name for safe use in filenames."""
    if '--' in name:
        return False, "Project name contains '--' separator"
    if '..' in name or '/' in name or '\\' in name:
        return False, "Path traversal characters detected"
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$', name):
        return False, "Invalid characters"
    return True, None
```

**Path Containment** (prevent escapes):

```python
def _ensure_within_dir(path: Path, base_dir: Path) -> Path:
    """Validate path stays within base directory."""
    if path.is_symlink():
        raise ValueError("Symlink detected")

    resolved = path.resolve()
    base_resolved = base_dir.resolve()

    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        raise ValueError("Path escape detected")

    return resolved
```

### Atomic Operations

**Atomic Write** (prevent corruption):

```python
def _atomic_write(path: Path, content: str) -> None:
    """Write file atomically via temp-file-then-rename."""
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix='.memento-',
        suffix='.tmp'
    )
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, str(path))  # Atomic on POSIX
    except BaseException:
        os.unlink(tmp_path)  # Cleanup on failure
        raise
```

### Operations

**Create**:

```python
# filename = make_memento_filename(project_name, slug)
# path = MEMENTOS_DIR / filename
# _ensure_within_dir(path, MEMENTOS_DIR)
# _atomic_write(path, content)
```

**Read**:

```python
# memento = find_memento(slug, include_archive=True)
# content = Path(memento['path']).read_text()
```

**List**:

```python
# mementos = list_mementos('active', project_filter='aida-core-plugin')
# for m in mementos: print(m['slug'], m['description'])
```

**Update**:

```python
# memento = find_memento(slug)
# content = Path(memento['path']).read_text()
# frontmatter, body = parse_frontmatter(content)
# frontmatter['updated'] = datetime.now().isoformat()
# new_content = rebuild_file(frontmatter, body)
# _atomic_write(Path(memento['path']), new_content)
```

**Complete** (archive):

```python
# source = MEMENTOS_DIR / filename
# dest = ARCHIVE_DIR / filename
# frontmatter['status'] = 'completed'
# _atomic_write(dest, content)
# source.unlink()
```

**Remove**:

```python
# memento = find_memento(slug, include_archive=True)
# Path(memento['path']).unlink()
```

## Alternatives Considered

### Alternative 1: Project-Level Storage

**Approach**: Store mementos in `.claude/memento/` within each project.

**Pros**:

- Discoverable by team (in repo)
- Lives with project
- No project namespacing needed
- Committed to git (optional)

**Cons**:

- Lost when project deleted
- Lost when project moved
- No cross-project listing
- Requires `.claude/` in every project
- Harder to backup (scattered)

**Verdict**: Rejected - Doesn't survive project changes, poor for
cross-project workflows.

### Alternative 2: User-Level Flat Structure

**Approach**: All mementos in `~/.claude/memento/` without project
prefix.

**Pros**:

- Simpler filenames
- No parsing needed
- Fewer validation rules

**Cons**:

- Slug conflicts between projects
- Can't filter by project easily
- Harder to identify orphans
- Confusing with multiple projects

**Verdict**: Rejected - Slug conflicts and poor organization.

### Alternative 3: Database Storage (SQLite)

**Approach**: Store mementos in `~/.claude/memento.db` SQLite database.

**Pros**:

- Rich queries (filter, sort, search)
- No filename validation
- Atomic transactions
- Relational data (tags, links)

**Cons**:

- Binary format (not user-editable)
- Database schema versioning
- Migration complexity
- Corruption risk
- Not git-friendly

**Verdict**: Rejected - Mementos should be markdown files (readable,
editable, version-controllable).

### Alternative 4: Cloud Sync

**Approach**: Store mementos in cloud service (Dropbox, iCloud,
GitHub).

**Pros**:

- Automatic backup
- Sync across machines
- Version history
- Team collaboration

**Cons**:

- Privacy concerns
- Network dependency
- Requires authentication
- Complexity
- Not local-first

**Verdict**: Rejected for M1 - Violates local-first principle
(see ADR-005). Could be added later as opt-in sync.

## Related Decisions

- [ADR-001: Skills-First Architecture](001-skills-first-architecture.md)
  - Mementos complement skills (session vs persistent context)
- [ADR-005: Local-First Storage](005-local-first-storage.md)
  - Mementos stored locally, user owns data
- [ADR-009: Input Validation and Path Security](009-input-validation-path-security.md)
  - Path validation prevents traversal attacks
- [ADR-010: Two-Phase API Pattern](010-two-phase-api-pattern.md)
  - Memento creation uses two-phase pattern

## Future Considerations

### Migration Command

**Rename Project**:

```bash
aida memento migrate --from=old-project --to=new-project
# Renames all 'old-project--*.md' to 'new-project--*.md'
```

**Clean Orphans**:

```bash
aida memento clean --orphans
# Lists mementos for non-existent projects
# Prompts: archive, delete, or keep
```

### Search and Tagging

**Full-Text Search**:

```bash
aida memento search "authentication bug"
# Searches across all memento content
```

**Tag-Based Filtering**:

```bash
aida memento list --tag=bug
aida memento list --tag=pr-123
```

### Cloud Sync (Opt-In)

**GitHub Gist Sync**:

- Upload mementos to private gists
- Pull down on other machines
- Preserve local-first (sync is optional)

**Conflict Resolution**:

- Last-write-wins (simple)
- Or: Manual merge (safe)

### Project-Level Index

**Team Visibility**:

- Create `.claude/mementos.md` in project
- Lists mementos for this project
- Committed to git for team awareness
- Generated automatically on memento create

---

**Decision Record**: @oakensoul, 2026-02-16
**Status**: Accepted
