---
type: adr
title: "ADR-006: GitHub CLI for Feedback System"
description: "The `gh` CLI is the transport for the /aida feedback, /aida bug, and /aida feature-request flows."
status: accepted
date: "2025-11-01"
deciders:
  - "@oakensoul"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# ADR-006: GitHub CLI for Feedback System

## Context

AIDA needs a feedback mechanism for users to:

- Report bugs
- Request features
- Provide general feedback

Options for implementation:

1. GitHub CLI (`gh`) to create issues
2. Direct GitHub API calls
3. Web form submission
4. Email-based feedback
5. In-app chat system

Considerations: ease of use, authentication, privacy, maintenance.

## Decision

Use **GitHub CLI (`gh`)** to create GitHub issues for all feedback.

### Commands

- `/aida bug` - Bug reports
- `/aida feature-request` - Feature requests
- `/aida feedback` - General feedback

## Rationale

### Why gh CLI?

1. **Official Tool**: Maintained by GitHub, well-supported
2. **Authentication**: Uses existing `gh auth` - no tokens to manage
3. **Simple Integration**: Shell command from Python
4. **User Control**: User reviews issue before submission
5. **No Server**: No infrastructure needed
6. **Transparent**: Users can see exactly what's submitted

### Process

```text
/aida bug
  ↓
Collect environment info (Python version, OS, etc.)
  ↓
Show issue template with prefilled data
  ↓
User edits in their editor
  ↓
User confirms
  ↓
gh issue create --title "..." --body "..."
  ↓
GitHub issue created
```

### Benefits

- No AIDA server infrastructure
- GitHub's issue tracker (labels, search, discussion)
- Public or private repository option
- User sees what's submitted
- No AIDA-managed authentication

## Consequences

### Positive

- ✅ Zero infrastructure cost
- ✅ Leverages GitHub's excellent issue system
- ✅ User controls submission (reviews first)
- ✅ No auth tokens to manage
- ✅ Simple Python implementation

### Negative

- ❌ Requires `gh` CLI installed
- ❌ Requires GitHub authentication
- ❌ Only works with GitHub (not GitLab, etc.)
- ❌ Requires internet connection

### Mitigation

- Check for `gh` CLI in `/aida doctor`
- Provide installation instructions
- Fallback: Manual issue creation instructions
- Optional: Make feedback system plugin-extensible

## Implementation

### Check for gh CLI

```python
import subprocess

def check_gh_cli() -> bool:
    """Check if gh CLI is installed and authenticated"""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
```

### Create Issue

```python
def create_bug_report(
    title: str,
    body: str,
    labels: list = ["bug"]
) -> None:
    """Create GitHub issue via gh CLI"""
    cmd = [
        "gh", "issue", "create",
        "--repo", "aida-core/aida-core-plugin",
        "--title", title,
        "--body", body,
        "--label", ",".join(labels)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✓ Issue created: {result.stdout}")
    else:
        print(f"✗ Failed: {result.stderr}")
```

### Environment Info Collection

```python
def get_environment_info() -> dict:
    """Collect system information for bug reports"""
    return {
        "python_version": platform.python_version(),
        "os": platform.system(),
        "os_version": platform.version(),
        "aida_version": get_aida_version(),
        "claude_code_version": get_claude_version()
    }
```

### Templates

**Bug Report Template**:

```text
## Bug Description

[User describes the bug here]

## Steps to Reproduce

1. [Step 1]
2. [Step 2]
3. [See error]

## Expected Behavior

[What should happen]

## Actual Behavior

[What actually happens]

## Environment

- OS: {os}
- Python: {python_version}
- AIDA: {aida_version}
- Claude Code: {claude_code_version}
```

**Feature Request Template**:

```text
## Problem

[What problem does this solve?]

## Proposed Solution

[How should it work?]

## Alternatives Considered

[Other approaches]

## Use Case

[Real-world example]
```

## Alternatives Considered

### Alternative 1: Direct GitHub API

**Approach**: Use GitHub REST API directly from Python

**Pros**: No external dependency

#### Cons

- Token management complexity
- Security concerns (token storage)
- Rate limiting
- More code to maintain

**Verdict**: gh CLI handles this better

### Alternative 2: Web Form

**Approach**: Web form that posts to GitHub API

**Pros**: No CLI dependency

#### Cons

- Requires web server
- Infrastructure cost
- Auth complexity
- Breaks local-first principle

**Verdict**: Too complex for MLP

### Alternative 3: Email-Based

**Approach**: Send feedback via email

**Pros**: Universal, no special tools

#### Cons

- Email setup complexity
- Spam filtering issues
- No tracking system
- Harder to organize

**Verdict**: GitHub issues better organized

## Graceful Degradation

If `gh` not available:

```text
❌ gh CLI not found

To report this bug, please:
1. Install gh CLI: https://cli.github.com/
2. Authenticate: gh auth login
3. Run: /aida bug

Or manually create an issue:
https://github.com/aida-core/aida-core-plugin/issues/new
```

## Future Considerations

### Plugin System for Feedback

Could make feedback system extensible:

```python
# Default: GitHub via gh
feedback_backend = GithubFeedback()

# Alternative: GitLab
feedback_backend = GitLabFeedback()

# Alternative: Jira
feedback_backend = JiraFeedback()
```

For M1: GitHub only is sufficient.

### Anonymous Feedback

Currently requires GitHub account. Could add:

- Anonymous feedback endpoint
- Public Google Form
- Email option

For M1: GitHub account requirement is acceptable (target audience).

## Related

- [ADR-005: Local-First Storage](005-local-first-storage.md) - Consistent with local-first principle

---

**Status**: ✅ Accepted, implemented in M1
