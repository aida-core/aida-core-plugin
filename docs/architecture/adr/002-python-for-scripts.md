---
type: adr
title: "ADR-002: Python for Installation Scripts"
description: "Python is the runtime for AIDA's installation, configuration, and skill-execution scripts."
status: accepted
date: "2025-11-01"
deciders:
  - "@oakensoul"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# ADR-002: Python for Installation Scripts

## Context

AIDA needs installation and configuration scripts that run outside of Claude conversations. These scripts need to:

- Check system requirements
- Run interactive questionnaires
- Create directory structures
- Render templates
- Update JSON configuration files
- Handle errors gracefully

Several language choices are available:

1. **Bash/Shell**: Native to Unix systems
2. **Python**: Cross-platform scripting
3. **JavaScript/Node.js**: Claude Code's runtime
4. **Go**: Compiled, single binary
5. **Rust**: Compiled, safe

The choice affects:

- Cross-platform compatibility
- Development speed
- Dependency management
- Maintenance burden
- User requirements

## Decision

We will use **Python 3.8+** for all AIDA installation and utility scripts.

## Rationale

### Why Python?

#### 1. Cross-Platform Compatibility

- Works on macOS, Linux, and WSL (Windows)
- Same code runs everywhere
- Standard library handles OS differences
- No platform-specific compilation

#### 2. Developer Ecosystem

- Rich standard library (json, pathlib, shutil, etc.)
- Excellent third-party packages (Jinja2, PyYAML)
- Well-documented
- Large community

#### 3. Likely Already Installed

- Most developers have Python installed
- Often pre-installed on macOS and Linux
- Common dependency for dev tools

#### 4. Development Speed

- Fast iteration
- Clear, readable code
- Excellent for scripting tasks
- Good error handling

#### 5. Template Rendering

- Jinja2 is industry-standard
- Powerful and flexible
- Used by many tools (Ansible, Salt, Flask)

#### 6. JSON Manipulation

- Native JSON support
- Easy to read/write/merge JSON files
- Perfect for settings.json management

### Why Not Bash?

**Against**:

- Not cross-platform (different on macOS vs Linux vs WSL)
- Limited data structures
- Error handling difficult
- JSON manipulation awkward
- Template rendering limited

**Verdict**: Bash is great for simple scripts, but AIDA needs more structure.

### Why Not JavaScript/Node.js?

**Against**:

- Requires Node.js installation
- Larger runtime
- Less common for system scripts
- Callback complexity
- npm dependencies management

**Verdict**: Node.js is great for web apps, but overkill for installation scripts.

### Why Not Go?

**Against**:

- Requires compilation step
- Binary distribution complexity
- Versioning and updates harder
- Steeper learning curve for contributors

**Pros**:

- Single binary (no dependencies)
- Fast execution

**Verdict**: Go is great for tools, but adds complexity for AIDA's needs.

### Why Not Rust?

**Against**:

- Long compilation times
- Steep learning curve
- Overkill for scripting tasks
- Binary distribution complexity

**Verdict**: Rust is great for systems programming, but too heavy for AIDA.

## Consequences

### Positive

✅ **Cross-platform**: Same code on macOS, Linux, WSL

✅ **Fast development**: Rich ecosystem speeds up implementation

✅ **Readable**: Python code is clear and maintainable

✅ **Good tooling**: Jinja2, PyYAML perfect for our needs

✅ **Easy to contribute**: Many developers know Python

✅ **Flexible**: Easy to extend and modify

### Negative

❌ **Python dependency**: Users must have Python 3.8+ installed

❌ **Startup time**: Python interpreter overhead (minor)

❌ **Distribution**: Not a single binary

❌ **Version conflicts**: Different Python versions could cause issues

### Mitigation Strategies

**Python Dependency**:

- Check for Python 3.8+ at install time
- Clear error message if not found
- Installation guide includes Python setup

**Version Conflicts**:

- Specify minimum version (3.8)
- Test on multiple Python versions
- Use only widely-supported features

**Distribution**:

- Ship as source code (no compilation needed)
- Claude Code plugin system handles distribution
- Dependencies minimal (Jinja2, PyYAML only)

## Implementation Notes

### Python Version Requirement

**Minimum**: Python 3.8

**Rationale**:

- Released October 2019 (widely adopted)
- Assignment expressions (`:=`)
- f-string improvements
- TypedDict support
- Long-term support still active

**Check**:

```python
import sys

MIN_VERSION = (3, 8)
if sys.version_info < MIN_VERSION:
    raise VersionError(f"Python {MIN_VERSION[0]}.{MIN_VERSION[1]}+ required")
```

### Dependency Management

**Core Dependencies**:

- `Jinja2` - Template rendering
- `PyYAML` - Questionnaire definitions

**requirements.txt**:

```text
jinja2>=3.0.0
pyyaml>=6.0
```

**Installation**:

```bash
pip install -r requirements.txt
```

Or bundled with plugin.

### Script Organization

```text
scripts/
├── install.py              # Main installation script
├── configure.py            # Project configuration (planned)
├── feedback.py             # GitHub feedback
└── utils/                  # Shared utilities
    ├── __init__.py
    ├── version.py
    ├── paths.py
    ├── files.py
    ├── questionnaire.py
    ├── inference.py
    ├── template_renderer.py
    └── errors.py
```

**Module Design**:

- utils/ is a proper Python package
- Clean API via **init**.py
- Type hints where helpful
- Comprehensive docstrings

### Error Handling

**Custom Exceptions**:

```python
class AidaError(Exception):
    """Base exception for all AIDA errors"""

class VersionError(AidaError):
    """Python version incompatible"""

class InstallationError(AidaError):
    """Installation failed"""
```

**User-Friendly Messages**:

```python
try:
    check_python_version()
except VersionError as e:
    print(f"❌ {e}")
    print("\nPlease install Python 3.8 or higher:")
    print("  macOS: brew install python3")
    print("  Linux: sudo apt install python3")
    sys.exit(1)
```

### Cross-Platform Considerations

**Path Handling**:

```python
from pathlib import Path

# Use pathlib.Path for all paths
claude_dir = Path.home() / ".claude"

# Automatically handles OS differences
```

**Line Endings**:

- Write files with platform-appropriate line endings
- Python's open() handles this automatically

**File Permissions**:

- Check and set appropriately
- Use os.chmod() when needed

## Alternatives Considered

### Alternative 1: Bash with Python Fallback

**Approach**: Use bash where possible, fall back to Python for complex tasks

**Pros**:

- Minimal dependencies for simple operations
- Fast for basic tasks

**Cons**:

- Complexity of maintaining two languages
- Inconsistent behavior
- Hard to test and debug

**Why Rejected**: Two languages harder to maintain than one

### Alternative 2: Node.js (Claude Code's Runtime)

**Approach**: Use JavaScript since Claude Code uses Node.js

**Pros**:

- Same runtime as Claude Code
- No additional installation

**Cons**:

- Assumes Node.js installed (not guaranteed)
- Less suitable for system scripting
- More verbose for file operations
- Template rendering less mature

**Why Rejected**: Python better suited for system scripts

### Alternative 3: Compiled Go Binary

**Approach**: Distribute as single Go binary

**Pros**:

- No runtime dependencies
- Fast execution
- Single file distribution

**Cons**:

- Must compile for each platform
- Updates require new binary
- Build complexity
- Harder for contributors

**Why Rejected**: Distribution complexity outweighs benefits for our use case

## Related Decisions

- [ADR-001: Skills-First Architecture](001-skills-first-architecture.md)
- [ADR-003: Jinja2 for Templates](003-jinja2-templates.md)
- [ADR-004: YAML for Questionnaires](004-yaml-questionnaires.md)

## Future Considerations

### Potential Future Changes

**If Python becomes a problem**:

- Could rewrite in Go (single binary)
- Could use Node.js (leverage Claude Code runtime)
- Could use shell scripts (Unix-only)

**When to consider rewriting**:

- Python installation becomes common blocker
- Performance becomes issue (unlikely)
- Distribution complexity too high

**For now**: Python is the right choice for M1.

### Python Version Evolution

**When to bump minimum version**:

- Major Python version EOL (e.g., 3.8 EOL in 2024)
- Need features from newer version
- Widely adopted new version

**Process**:

- Announce in advance
- Update documentation
- Provide migration guide

## Success Metrics

How to measure if this decision was right:

- **Installation success rate**: > 95% of users have compatible Python
- **Cross-platform**: Works identically on macOS, Linux, WSL
- **Contributor ease**: New contributors can modify scripts
- **Maintenance**: Low bug rate, easy fixes
- **Performance**: Installation completes in < 30 seconds

## Testing Strategy

### Unit Tests

```python
# tests/test_utils.py
import pytest
from utils import check_python_version, get_claude_dir

def test_check_python_version():
    # Should not raise for current Python
    check_python_version()

def test_get_claude_dir():
    result = get_claude_dir()
    assert result.name == ".claude"
```

### Integration Tests

```python
def test_full_installation(tmp_path):
    # Mock questionnaire responses
    # Run installation
    # Verify skills created
```

### Cross-Platform Tests

Run tests on:

- macOS (GitHub Actions)
- Ubuntu Linux (GitHub Actions)
- Windows WSL (manual testing initially)

## References

- [Python 3.8 Release Notes](https://docs.python.org/3/whatsnew/3.8.html)
- [Jinja2 Documentation](https://jinja.palletsprojects.com/)
- [PyYAML Documentation](https://pyyaml.org/)

---

**Decision Record**: @oakensoul, 2025-11-01
**Status**: ✅ Accepted, implemented in M1
