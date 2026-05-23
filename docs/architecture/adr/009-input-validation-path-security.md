---
type: adr
title: "ADR-009: Input Validation and Path Security"
description: "All paths are validated via Path.resolve() and explicit checks to prevent directory traversal and symlink attacks."
status: accepted
date: "2026-02-16"
deciders:
  - "@oakensoul"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# ADR-009: Input Validation and Path Security

## Context

AIDA Core Plugin accepts user input through multiple channels that could
be exploited if not properly validated:

- File paths provided to skills (memento storage, plugin installation)
- GitHub CLI inputs (issue titles, labels, descriptions)
- JSON payloads (configuration, responses, context)
- Project names and slugs (memento namespacing)

Security concerns include:

1. **Path Traversal**: Malicious paths escaping allowed directories
2. **Injection Attacks**: Command injection via gh CLI, shell scripts
3. **Resource Exhaustion**: Large JSON payloads, deeply nested objects
4. **Symlink Attacks**: Following symlinks to unauthorized locations
5. **Null Byte Injection**: Bypassing path validation

## Decision

Implement **defense-in-depth input validation** across all user-facing
scripts using multiple layers of security controls.

### Path Security (`utils/paths.py`)

**Path Traversal Prevention**:

```python
def resolve_path(path, must_exist=False, allowed_base=None):
    # Validate against null bytes
    if '\x00' in str(path_obj):
        raise PathError("Invalid path contains null bytes")

    # Expand and resolve
    resolved = path_obj.expanduser().resolve()

    # Validate within allowed_base using relative_to()
    if allowed_base is not None:
        try:
            resolved.relative_to(allowed_resolved)
        except ValueError:
            raise PathError("Path traversal attempt detected")
```

**Symlink Protection**:

```python
def ensure_directory(path, permissions=0o755):
    # Check for symlinks before creating
    if expanded_path.exists() and expanded_path.is_symlink():
        raise PathError("Cannot create directory: path is a symlink")
```

### GitHub CLI Input Sanitization (`feedback.py`)

**Length Limits**:

- Titles: 200 characters max
- Descriptions: 5000 characters max
- Minimum: 10 characters (prevent spam)

**Argument Injection Prevention**:

```python
def sanitize_gh_input(text, max_length, allow_multiline):
    # Enforce length limits
    if len(text) > max_length:
        raise ValueError(f"Input too long (max {max_length} chars)")

    # Check for null bytes
    if '\x00' in text:
        raise ValueError("Invalid characters in input")

    # Prevent argument injection - escape lines starting with --
    lines = text.split('\n')
    for line in lines:
        if line.lstrip().startswith('--'):
            sanitized_lines.append('  ' + line)  # Add padding
```

**Label Validation** (allowlist pattern):

```python
ALLOWED_LABEL_PATTERN = re.compile(r'^[a-zA-Z0-9 \-:\/]+$')

def validate_labels(labels):
    for label in labels:
        if not label or not ALLOWED_LABEL_PATTERN.match(label):
            return False, "Invalid label: only alphanumeric, hyphens, spaces, colons, slashes allowed"
```

**Path Sanitization** (PII prevention):

```python
def sanitize_paths(text):
    home = str(Path.home())
    text = text.replace(home, "~")
    username = os.getlogin()
    text = text.replace(username, "<user>")
    return text
```

### JSON Safety (`json_utils.py`)

**Size Limits**:

- General payloads: 1MB maximum
- Memento payloads: 100KB maximum (lightweight session snapshots)

**Depth Limits**:

- Maximum nesting depth: 10 levels

```python
def safe_json_load(json_str, max_size=MAX_JSON_SIZE):
    # Check size
    if len(json_str) > max_size:
        raise ValueError(f"JSON payload too large (max {max_size} bytes)")

    # Parse
    data = json.loads(json_str)

    # Validate nesting depth recursively
    def check_depth(obj, depth=0, max_depth=10):
        if depth > max_depth:
            raise ValueError(f"JSON nesting too deep (max {max_depth})")
        if isinstance(obj, dict):
            for value in obj.values():
                check_depth(value, depth + 1)
    check_depth(data)
```

### Memento Security (`memento.py`)

**Path Containment Validation**:

```python
def _ensure_within_dir(path, base_dir):
    # Reject symlinks
    if path.is_symlink():
        raise ValueError(f"Symlink detected at {path}")

    # Resolve and validate containment
    resolved = path.resolve()
    base_resolved = base_dir.resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        raise ValueError(f"Path escape detected: {resolved}")
```

**Project Name Validation**:

```python
def validate_project_name(name):
    if '--' in name:
        return False, "Project name contains '--' separator"
    if '..' in name or '/' in name or '\\' in name:
        return False, "Project name contains path traversal characters"
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$', name):
        return False, "Invalid characters"
```

**Atomic Writes** (prevent partial corruption):

```python
def _atomic_write(path, content):
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".memento-")
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)  # Atomic on POSIX
    except BaseException:
        os.unlink(tmp_path)  # Clean up on failure
        raise
```

## Rationale

### Why Defense-in-Depth?

**Multiple Security Layers**:

- Input validation prevents bad data from entering
- Path validation prevents directory escapes
- Symlink checks prevent following malicious links
- Atomic operations prevent race conditions
- Size limits prevent resource exhaustion

**Fail-Safe Design**:

- If one layer fails, others still protect
- Explicit validation at every boundary
- No implicit trust of user input

### Why Path.relative_to() Over String Checks?

**String-Based Validation is Vulnerable**:

```python
# VULNERABLE to bypass attacks
if not str(resolved).startswith(str(base)):
    raise Error()
# Can be bypassed with: /allowed/../../etc/passwd
```

**Path.relative_to() is Robust**:

```python
# SECURE - validates after full path resolution
resolved.relative_to(base_resolved)
# Raises ValueError if path is outside base
```

### Why Null Byte Checks?

**Null Byte Injection Attack**:

```python
path = "/allowed/dir\x00../../etc/passwd"
# Some C functions stop at \x00, bypassing validation
```

**Prevention**:

```python
if '\x00' in str(path):
    raise PathError("Null bytes not allowed")
```

### Why Label Allowlists?

**Command Injection Risk**:

```bash
gh issue create --label "bug; rm -rf /"
# Prevents shell metacharacters in labels
```

**Allowlist Pattern**: Only safe characters permitted.

## Consequences

### Positive

- Prevents path traversal exploits
- Prevents command injection attacks
- Prevents resource exhaustion (DoS)
- Prevents symlink-based attacks
- Prevents null byte injection
- Defense-in-depth provides redundancy
- Clear, auditable validation code

### Negative

- More verbose validation code
- Slightly slower due to validation overhead
- May reject edge-case valid inputs (false positives)
- Maintenance burden to keep patterns up-to-date

### Mitigation

**False Positives**:

- Document allowed input formats clearly
- Provide helpful error messages with examples
- Test with real-world input patterns

**Maintenance**:

- Centralize validation in `utils/` modules
- Unit tests for each validation function
- Document security rationale in comments

**Performance**:

- Validation overhead is minimal (milliseconds)
- Cache resolved paths where applicable
- Accept cost for security benefit

## Implementation Notes

### Validation Hierarchy

**Level 1: Entry Points** (CLI args, JSON payloads):

- `safe_json_load()` - Size and depth limits
- `sanitize_gh_input()` - Length and character validation
- Argument parsing with type checking

**Level 2: Business Logic** (slugs, project names):

- `validate_slug()` - Format and length rules
- `validate_project_name()` - Path-safe naming
- `validate_labels()` - Allowlist pattern matching

**Level 3: Filesystem Operations** (paths):

- `resolve_path()` with `allowed_base`
- `_ensure_within_dir()` for containment
- Symlink rejection before operations

**Level 4: Atomic Operations** (writes):

- `_atomic_write()` - temp-file-then-rename
- `atomic_write()` with fsync
- Transaction rollback on failure

### Security Testing

**Test Cases**:

```python
# Path traversal
resolve_path("../../../etc/passwd", allowed_base=home)  # REJECT

# Null byte injection
resolve_path("/allowed\x00/../../etc", allowed_base=allowed)  # REJECT

# Symlink attack
Path("/tmp/link").symlink_to("/etc/passwd")
ensure_directory(Path("/tmp/link"))  # REJECT

# Command injection
sanitize_gh_input("title; rm -rf /")  # SANITIZE

# JSON bomb
safe_json_load("{" * 1000000)  # REJECT (size limit)

# Deep nesting
safe_json_load('{"a":' * 20 + '{}' + '}' * 20)  # REJECT (depth)
```

### Error Handling

**User-Facing Errors**:

- Clear error messages explaining what's wrong
- Suggestions for fixing the input
- No stack traces in production

**Security Logs**:

- Log validation failures (potential attacks)
- Include rejected input patterns (for analysis)
- Sanitize logs to prevent log injection

## Alternatives Considered

### Alternative 1: Trust User Input

**Approach**: Assume users won't provide malicious input.

**Pros**:

- Simpler code
- Faster execution
- No false positives

**Cons**:

- Vulnerable to all attack vectors
- Single mistake = full compromise
- No defense against mistakes

**Verdict**: Rejected - Unacceptable security risk.

### Alternative 2: External Validation Library

**Approach**: Use libraries like `pydantic`, `cerberus`, `schema`.

**Pros**:

- Well-tested validation logic
- Declarative schema definitions
- Community-maintained

**Cons**:

- Additional dependency
- Generic validation (not security-focused)
- May not cover all attack vectors
- Path security still needs custom code

**Verdict**: Rejected - Custom validation is more appropriate for
security-critical path operations. JSON schema validation could be
added later for config files.

### Alternative 3: Sandbox Execution

**Approach**: Run all operations in isolated sandboxes (containers,
chroot, namespaces).

**Pros**:

- Strong isolation
- Limits blast radius
- Defense against unknown attacks

**Cons**:

- Significant complexity
- Platform-specific implementation
- Performance overhead
- User experience impact (permissions)

**Verdict**: Rejected for M1 - Overkill for current threat model.
Input validation provides sufficient security for local scripts.

## Related Decisions

- [ADR-002: Python for Installation Scripts](002-python-for-scripts.md)
  - Python provides pathlib for safe path operations
- [ADR-005: Local-First Storage](005-local-first-storage.md)
  - Local storage requires path security
- [ADR-006: gh CLI for Feedback](006-gh-cli-feedback.md)
  - GitHub CLI inputs must be sanitized
- [ADR-011: User-Level Memento Storage](011-user-level-memento-storage.md)
  - Memento storage uses path validation

## Future Considerations

### Enhanced Validation

**Content Security Policy**:

- Define allowed file types for uploads
- Validate file extensions and MIME types
- Scan for malicious content patterns

**Rate Limiting**:

- Already implemented for feedback submission (60s interval)
- Could extend to other operations (memento creation, config updates)

**Audit Logging**:

- Log all validation failures
- Alert on repeated failures (potential attack)
- Periodic security reviews of logs

### Automated Testing

**Fuzzing**:

- Use fuzzing tools to generate malicious inputs
- Test all validation functions
- Discover edge cases and bypasses

**Security Scanning**:

- Static analysis (bandit, semgrep)
- Dependency scanning (safety, pip-audit)
- Regular penetration testing

---

**Decision Record**: @oakensoul, 2026-02-16
**Status**: Accepted
