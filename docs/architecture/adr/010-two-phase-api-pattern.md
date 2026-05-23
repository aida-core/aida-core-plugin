---
type: adr
title: "ADR-010: Two-Phase API Pattern for LLM Integration"
description: "Two-phase API (get_questions then execute) lets LLM orchestrators surface questions to the user between detection and action."
status: accepted
date: "2026-02-16"
deciders:
  - "@oakensoul"
---

<!-- SPDX-FileCopyrightText: 2026 The AIDA Core Authors -->
<!-- SPDX-License-Identifier: MPL-2.0 -->

# ADR-010: Two-Phase API Pattern for LLM Integration

## Context

AIDA skills need to integrate with Claude Code's LLM orchestration
while maintaining a clear separation between question generation and
execution. Traditional interactive CLI scripts don't work well with
LLM-driven workflows because:

1. **No Direct User Access**: Claude Code calls scripts via Bash tool,
   not interactive terminal
2. **Questions vs Execution**: LLM needs to present questions to users
   via AskUserQuestion tool, then call back with responses
3. **Inference Required**: Many values can be auto-detected from
   project context (languages, tools, structure)
4. **Reviewable Before Commit**: Users should see what will be created
   before execution
5. **Resumable Workflows**: If Claude Code is interrupted, work should
   be resumable

Traditional approaches don't fit:

- **Interactive Prompts**: `input()` calls block, Claude Code can't
  intercept
- **Single-Phase Execution**: No opportunity to review before commit
- **Flag-Based CLI**: Too many flags for all possible inference
  overrides

## Decision

Implement a **Two-Phase API Pattern** for all AIDA scripts that need
user input or context inference.

### Phase 1: get_questions(context)

**Purpose**: Analyze context, infer what we can, ask what we must.

**Input**: JSON context dict (via `--context` or stdin):

```json
{
  "operation": "create|configure|install",
  "description": "Optional user-provided description",
  "source": "manual|from-pr|from-changes",
  "project_root": "/path/to/project"
}
```

**Processing**:

1. **Detect Environment**: OS, tools, git config, project structure
2. **Infer Values**: Languages, frameworks, project type, team size
3. **Apply Heuristics**: Default preferences based on detected patterns
4. **Generate Questions**: Only ask what can't be inferred

**Output**: JSON response (via stdout):

```json
{
  "questions": [
    {
      "id": "project_type",
      "question": "What type of project is this?",
      "type": "choice|text",
      "options": ["Web app", "CLI tool", "Library"],
      "required": true,
      "default": "Web app"
    }
  ],
  "inferred": {
    "languages": ["Python", "JavaScript"],
    "tools": ["pytest", "ruff"],
    "project_name": "my-project"
  },
  "validation": {
    "valid": true,
    "errors": []
  }
}
```

### Phase 2: execute(context, responses)

**Purpose**: Perform operations with combined inferred + user data.

**Input**: JSON context + responses (via `--context` and `--responses`):

Context (from Phase 1):

```json
{
  "operation": "configure",
  "project_root": "/path/to/project"
}
```

Responses (from user via AskUserQuestion):

```json
{
  "project_type": "Web app",
  "team_size": "5-10",
  "custom_slug": "my-work"
}
```

Inferred (from Phase 1):

```json
{
  "languages": ["Python", "JavaScript"],
  "tools": ["pytest", "ruff"]
}
```

**Processing**:

1. **Merge Data**: Combine inferred values + user responses
2. **Validate**: Check for conflicts, missing required fields
3. **Execute**: Create files, update config, perform operations
4. **Atomic Operations**: Use temp-file-then-rename for safety

**Output**: JSON response (via stdout):

```json
{
  "success": true,
  "message": "Created project configuration",
  "path": "/path/to/.claude/skills/project-context",
  "created_files": [
    ".claude/skills/project-context/PROJECT_CONTEXT.md",
    ".claude/aida.yml"
  ]
}
```

### Implementation Pattern

**All scripts follow this structure**:

```python
def get_questions(context: Dict[str, Any]) -> Dict[str, Any]:
    """Phase 1: Analyze and generate questions."""
    # Detect environment
    inferred = detect_context()

    # Generate questions for missing data
    questions = []
    if not context.get("description"):
        questions.append({
            "id": "description",
            "question": "What are you working on?",
            "type": "text",
            "required": True
        })

    return {
        "questions": questions,
        "inferred": inferred,
        "validation": {"valid": True, "errors": []}
    }


def execute(context: Dict[str, Any],
            responses: Dict[str, Any]) -> Dict[str, Any]:
    """Phase 2: Execute with combined data."""
    # Merge inferred + responses
    data = {**context.get("inferred", {}), **responses}

    # Validate
    if "required_field" not in data:
        return {"success": False, "message": "Missing required field"}

    # Execute
    result = perform_operation(data)

    return {
        "success": True,
        "message": "Operation completed",
        "path": result.path
    }
```

## Rationale

### Why Two Phases?

**1. Separation of Concerns**:

- **Phase 1**: Detection and inference (read-only)
- **Phase 2**: Execution and side effects (write)

**2. Reviewable Before Commit**:

- User sees what will be created
- Can override inferred values
- No surprises after execution

**3. LLM-Friendly**:

- Phase 1 returns structured questions
- Claude presents via AskUserQuestion tool
- Phase 2 receives structured responses

**4. Resumable**:

- Phase 1 can be called multiple times (idempotent)
- Phase 2 only called once with final answers
- No partial state if interrupted

**5. Testable**:

- Phase 1 tests: inference logic
- Phase 2 tests: execution logic
- Can test independently

### Why JSON Communication?

**Structured Data**:

- Type-safe (with validation)
- Machine-readable
- Easy to extend

**LLM Integration**:

- Claude Code can parse responses
- Can present questions to user
- Can collect answers programmatically

**Debugging**:

- Easy to log request/response
- Can replay with same inputs
- Clear interface boundary

### Why Inferred vs Responses Split?

**Transparency**:

- User sees what was auto-detected
- Can override if detection is wrong
- Clear provenance of each value

**Efficiency**:

- Don't ask questions we can answer
- Minimize user input required
- Smart defaults based on detection

**Validation**:

- Can validate inferred values
- Can check for conflicts
- Can warn about inconsistencies

## Consequences

### Positive

- Clean separation between detection and execution
- LLM can orchestrate multi-step workflows
- Users see what will happen before it happens
- Resumable if interrupted
- Testable phases independently
- Easy to add new questions without breaking API
- JSON makes debugging and logging easy

### Negative

- More complex than simple CLI prompts
- Two round trips (Phase 1, then Phase 2)
- JSON parsing overhead
- Must maintain backwards compatibility

### Mitigation

**Complexity**:

- Provide clear templates and examples
- Use shared utilities (`utils/json_utils.py`)
- Document pattern in ADR (this doc)

**Round Trips**:

- Acceptable for interactive workflows
- Phases are fast (< 1 second each)
- Better UX than blind execution

**JSON Overhead**:

- Minimal for small payloads
- Use size limits (see ADR-009)
- Benefits outweigh costs

**Backwards Compatibility**:

- Add new optional fields (don't remove)
- Version API if breaking changes needed
- Document schema in code comments

## Implementation Notes

### Scripts Using Two-Phase API

**configure.py** (`skills/aida/scripts/`):

```python
# Phase 1: Infer project context
get_questions(context)
# Returns: languages, tools, project_type inference
# Questions: project_type, team_size, documentation_level

# Phase 2: Create project skills
configure(responses, inferred)
# Creates: .claude/skills/project-context/
```

**install.py** (`skills/aida/scripts/`):

```python
# Phase 1: Detect environment
get_questions(context)
# Returns: OS, shell, git config, paths
# Questions: NONE (global install is automatic)

# Phase 2: Create user-level config
install(responses, inferred)
# Creates: ~/.claude/aida.yml, ~/.claude/skills/user-context/
```

**feedback.py** (`skills/aida/scripts/`):

```python
# Phase 1: Detect system context
get_questions(context)
# Returns: OS, Python version, AIDA version
# Questions: description, steps, expected, actual

# Phase 2: Submit GitHub issue
execute(responses, inferred)
# Creates: GitHub issue with sanitized content
```

**memento.py** (`skills/memento/scripts/`):

```python
# Phase 1: Infer from source
get_questions(context)
# Returns: slug (from PR title/description), files, tags
# Questions: description (if manual), problem, slug (if conflict)

# Phase 2: Create memento
execute(responses, inferred)
# Creates: ~/.claude/memento/{project}--{slug}.md
```

### CLI Usage

**Claude Code Orchestration** (typical flow):

```python
# 1. Claude calls get_questions
result = subprocess.run([
    "python", "configure.py",
    "--get-questions",
    "--context", json.dumps({"operation": "configure"})
], capture_output=True)
questions_data = json.loads(result.stdout)

# 2. Claude presents questions via AskUserQuestion tool
for q in questions_data["questions"]:
    answer = ask_user_question(q["question"], q["options"])
    responses[q["id"]] = answer

# 3. Claude calls execute with responses
result = subprocess.run([
    "python", "configure.py",
    "--execute",
    "--context", json.dumps({"operation": "configure"}),
    "--responses", json.dumps(responses),
    "--inferred", json.dumps(questions_data["inferred"])
], capture_output=True)
result_data = json.loads(result.stdout)
```

**Direct CLI Testing** (development):

```bash
# Phase 1: See what questions would be asked
python configure.py --get-questions \
  --context='{"operation": "configure"}' | jq

# Phase 2: Execute with mock responses
python configure.py --execute \
  --context='{"operation": "configure"}' \
  --responses='{"project_type": "Web app"}' \
  --inferred='{"languages": ["Python"]}' | jq
```

### Error Handling

**Phase 1 Errors** (detection failures):

```json
{
  "questions": [],
  "inferred": {},
  "validation": {
    "valid": false,
    "errors": ["Failed to detect project type: No package.json or requirements.txt found"]
  }
}
```

**Phase 2 Errors** (execution failures):

```json
{
  "success": false,
  "message": "Failed to create project-context skill",
  "error": "Permission denied: ~/.claude/skills/"
}
```

## Alternatives Considered

### Alternative 1: Interactive CLI Prompts

**Approach**: Traditional `input()` prompts for user interaction.

**Pros**:

- Simple to implement
- Familiar pattern
- Works in terminal

**Cons**:

- Doesn't work with Claude Code's Bash tool
- No LLM orchestration
- Not resumable
- Hard to test

**Verdict**: Rejected - Incompatible with LLM integration.

### Alternative 2: Single-Phase Execution

**Approach**: One script call with all data via flags.

**Pros**:

- Single round trip
- Simpler API
- Faster execution

**Cons**:

- Must provide all data upfront (no inference)
- No review before execution
- Can't ask follow-up questions
- Not resumable

**Verdict**: Rejected - Loses benefits of smart inference and review.

### Alternative 3: Config File Approach

**Approach**: Write config file, then execute based on config.

**Pros**:

- Reviewable (config file)
- Resumable (re-read config)
- Familiar pattern

**Cons**:

- Extra file management
- Harder to integrate with LLM
- Still need inference step
- Cleanup overhead

**Verdict**: Rejected - Two-phase API is more direct and LLM-friendly.

### Alternative 4: GraphQL/REST API

**Approach**: Run web server, use HTTP API for communication.

**Pros**:

- Industry-standard pattern
- Rich tooling
- Strong typing (schemas)

**Cons**:

- Massive overkill for local scripts
- Requires server process
- Complex deployment
- Security overhead (auth, CORS)

**Verdict**: Rejected - Overkill for CLI scripts.

## Related Decisions

- [ADR-001: Skills-First Architecture](001-skills-first-architecture.md)
  - Skills define WHAT, two-phase API defines HOW
- [ADR-002: Python for Installation Scripts](002-python-for-scripts.md)
  - Python enables structured JSON communication
- [ADR-004: YAML Questionnaires](004-yaml-questionnaires.md)
  - Questionnaires define static questions, two-phase adds
    dynamic inference
- [ADR-009: Input Validation and Path Security](009-input-validation-path-security.md)
  - JSON payloads validated with safe_json_load()

## Future Considerations

### Schema Validation

**JSON Schema**:

- Define schemas for request/response
- Validate at runtime with `jsonschema` library
- Generate TypeScript types for Claude Code

**Versioning**:

- Add `api_version` field to all requests
- Support multiple versions simultaneously
- Deprecation warnings for old versions

### Streaming Responses

**Long-Running Operations**:

- Phase 2 could stream progress updates
- Use JSON Lines format (one object per line)
- Claude could show live progress to user

**Example**:

```json
{"type": "progress", "step": "Detecting languages", "percent": 25}
{"type": "progress", "step": "Creating skills", "percent": 50}
{"type": "success", "message": "Complete", "path": "/path"}
```

### Retry and Idempotency

**Retry Logic**:

- Phase 1 always idempotent (read-only)
- Phase 2 could support idempotency tokens
- Prevent duplicate operations on retry

**Example**:

```json
{
  "operation": "configure",
  "idempotency_token": "uuid-1234",
  "responses": {"lang": "python", "framework": "flask"}
}
```

### Parallel Question Resolution

**Dependency Graph**:

- Some questions depend on previous answers
- Could ask independent questions in parallel
- Build dependency graph in Phase 1

**Example**:

```json
{
  "questions": [
    {"id": "lang", "depends_on": []},
    {"id": "framework", "depends_on": ["lang"]}
  ]
}
```

---

**Decision Record**: @oakensoul, 2026-02-16
**Status**: Accepted
