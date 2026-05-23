# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""CLAUDE.md management operations.

Handles create, optimize, validate, and list operations
for CLAUDE.md files.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.spdx import spdx_template_variables

from .utils import (
    get_project_root,
    parse_frontmatter,
    render_template,
)

# Required sections per scope. project-scope files document a codebase
# and need overview + commands. user-scope files capture free-form
# personal preferences; plugin-scope files document a plugin's own surface.
# Neither benefits from project-style required sections.
REQUIRED_SECTIONS: Dict[str, List[str]] = {
    "project": ["overview", "commands"],
    "user": [],
    "plugin": [],
}
RECOMMENDED_SECTIONS = ["architecture", "conventions", "constraints"]


def required_sections_for(scope: str) -> List[str]:
    """Return the required-section list for a given scope.

    Unknown scopes fall back to the project list so callers that
    don't know the scope keep their previous behavior.
    """
    return REQUIRED_SECTIONS.get(scope, REQUIRED_SECTIONS["project"])

# Template options
TEMPLATES = {
    "project": "claude-md/project.md.jinja2",
    "user": "claude-md/user.md.jinja2",
    "plugin": "claude-md/plugin.md.jinja2",
}


def get_claude_md_path(
    scope: str, project_root: Optional[Path] = None
) -> Path:
    """Get the CLAUDE.md path for a given scope.

    Args:
        scope: One of 'project', 'user', 'plugin'
        project_root: Project root path (for project scope)

    Returns:
        Path to CLAUDE.md location
    """
    if scope == "user":
        return Path.home() / ".claude" / "CLAUDE.md"
    elif scope == "plugin":
        root = project_root or get_project_root()
        return root / ".claude-plugin" / "CLAUDE.md"
    else:  # project
        root = project_root or get_project_root()
        # Check both locations
        if (root / ".claude" / "CLAUDE.md").exists():
            return root / ".claude" / "CLAUDE.md"
        return root / "CLAUDE.md"


def find_claude_md(scope: str = "all") -> List[Dict[str, Any]]:
    """Find all CLAUDE.md files in the hierarchy.

    Args:
        scope: 'project', 'user', 'plugin', or 'all'

    Returns:
        List of found CLAUDE.md file info
    """
    files = []
    project_root = get_project_root()

    scopes_to_check = (
        [scope] if scope != "all"
        else ["project", "user", "plugin"]
    )

    for s in scopes_to_check:
        path = get_claude_md_path(s, project_root)

        # For project, also check alternate location
        if s == "project":
            alt_path = project_root / ".claude" / "CLAUDE.md"
            if alt_path.exists():
                path = alt_path
            elif not path.exists():
                path = project_root / "CLAUDE.md"

        if path.exists():
            try:
                stat = path.stat()
                files.append({
                    "scope": s,
                    "path": str(path),
                    "exists": True,
                    "updated": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "size": stat.st_size,
                })
            except OSError:
                pass

    return files


def detect_sections(content: str) -> List[str]:
    """Detect sections present in CLAUDE.md content.

    Args:
        content: Markdown content

    Returns:
        List of section names (lowercase)
    """
    sections = []
    for match in re.finditer(
        r'^##\s+(.+)$', content, re.MULTILINE
    ):
        section_name = match.group(1).lower().strip()
        # Normalize common section names
        if (
            "overview" in section_name
            or "about" in section_name
        ):
            sections.append("overview")
        elif "command" in section_name:
            sections.append("commands")
        elif "architect" in section_name:
            sections.append("architecture")
        elif (
            "convention" in section_name
            or "style" in section_name
        ):
            sections.append("conventions")
        elif (
            "constraint" in section_name
            or "important" in section_name
        ):
            sections.append("constraints")
        else:
            sections.append(section_name)

    return sections


def extract_commands_from_makefile(
    project_root: Path,
) -> List[Dict[str, str]]:
    """Extract commands from Makefile.

    Args:
        project_root: Project root directory

    Returns:
        List of command dicts with command and description
    """
    commands: List[Dict[str, str]] = []
    makefile = project_root / "Makefile"

    if not makefile.exists():
        return commands

    try:
        content = makefile.read_text(encoding="utf-8")

        # Find targets with optional comments
        for match in re.finditer(
            r'^([a-zA-Z_-]+):.*?(?:#\s*(.+))?$',
            content,
            re.MULTILINE,
        ):
            target = match.group(1)
            description = match.group(2) or ""

            # Skip internal targets (starting with . or _)
            if target.startswith(".") or target.startswith(
                "_"
            ):
                continue

            # Skip common non-user targets
            if target in [
                "all",
                "default",
                "FORCE",
                "PHONY",
            ]:
                continue

            commands.append({
                "command": f"make {target}",
                "description": description.strip(),
            })

    except (IOError, UnicodeDecodeError):
        pass

    return commands[:10]  # Limit to 10 most relevant


def extract_commands_from_package_json(
    project_root: Path,
) -> List[Dict[str, str]]:
    """Extract npm scripts from package.json.

    Args:
        project_root: Project root directory

    Returns:
        List of command dicts with command and description
    """
    commands: List[Dict[str, str]] = []
    package_json = project_root / "package.json"

    if not package_json.exists():
        return commands

    try:
        content = package_json.read_text(encoding="utf-8")
        data = json.loads(content)

        scripts = data.get("scripts", {})
        for name, script in scripts.items():
            # Skip internal scripts
            if name.startswith("pre") or name.startswith(
                "post"
            ):
                continue

            commands.append({
                "command": f"npm run {name}",
                "description": (
                    script[:50] + "..."
                    if len(script) > 50
                    else script
                ),
            })

    except (IOError, json.JSONDecodeError):
        pass

    return commands[:10]


def extract_readme_description(
    project_root: Path,
) -> Optional[str]:
    """Extract project description from README.

    Args:
        project_root: Project root directory

    Returns:
        First paragraph of README or None
    """
    readme_files = [
        "README.md",
        "README.rst",
        "README.txt",
        "README",
    ]

    for readme in readme_files:
        readme_path = project_root / readme
        if readme_path.exists():
            try:
                content = readme_path.read_text(
                    encoding="utf-8"
                )

                # Skip frontmatter if present
                if content.startswith("---"):
                    end = content.find("---", 3)
                    if end > 0:
                        content = content[end + 3 :].strip()

                # Skip title
                lines = content.split("\n")
                start_idx = 0
                for i, line in enumerate(lines):
                    if line.startswith("#") or line.startswith(
                        "="
                    ):
                        start_idx = i + 1
                        break

                # Get first paragraph
                paragraph = []
                for line in lines[start_idx:]:
                    if line.strip():
                        paragraph.append(line.strip())
                    elif paragraph:
                        break

                if paragraph:
                    return " ".join(paragraph)[:500]

            except (IOError, UnicodeDecodeError):
                pass

    return None


def detect_project_context(
    project_root: Path,
) -> Dict[str, Any]:
    """Detect project context for CLAUDE.md generation.

    Args:
        project_root: Project root directory

    Returns:
        Dictionary of detected project facts
    """
    context: Dict[str, Any] = {
        "name": project_root.name,
        "languages": [],
        "tools": [],
        "commands": [],
        "project_type": None,
        "description": None,
    }

    # Try to import inference utilities from aida skill
    aida_utils = (
        Path(__file__).parent.parent.parent.parent
        / "aida"
        / "scripts"
        / "utils"
    )
    if aida_utils.exists():
        sys.path.insert(0, str(aida_utils.parent))

    try:
        from utils.inference import (
            detect_coding_standards,
            detect_languages,
            detect_project_structure,
            detect_project_type,
            detect_testing_approach,
            detect_tools,
        )

        languages = detect_languages(project_root)
        context["languages"] = sorted(list(languages))

        tools = detect_tools(project_root)
        context["tools"] = sorted(list(tools))

        context["project_type"] = detect_project_type(
            project_root
        )
        context["coding_standards"] = (
            detect_coding_standards(project_root)
        )
        context["testing_approach"] = (
            detect_testing_approach(project_root)
        )

        structure = detect_project_structure(project_root)
        context.update(structure)

    except ImportError:
        # Fallback to basic detection
        if (project_root / "package.json").exists():
            context["languages"].append("JavaScript")
            if (project_root / "tsconfig.json").exists():
                context["languages"].append("TypeScript")
        if (
            project_root / "pyproject.toml"
        ).exists() or (
            project_root / "setup.py"
        ).exists():
            context["languages"].append("Python")
        if (project_root / "go.mod").exists():
            context["languages"].append("Go")
        if (project_root / "Cargo.toml").exists():
            context["languages"].append("Rust")

        # Basic tool detection
        if (project_root / ".git").exists():
            context["tools"].append("Git")
        if (project_root / "Dockerfile").exists():
            context["tools"].append("Docker")
        if (project_root / "Makefile").exists():
            context["tools"].append("Make")

    # Extract commands
    makefile_commands = extract_commands_from_makefile(
        project_root
    )
    npm_commands = extract_commands_from_package_json(
        project_root
    )
    context["commands"] = makefile_commands + npm_commands

    # Extract description from README
    context["description"] = extract_readme_description(
        project_root
    )

    return context


def validate_claude_md(
    path: Path, scope: str = "project"
) -> Dict[str, Any]:
    """Validate a CLAUDE.md file.

    Args:
        path: Path to CLAUDE.md file
        scope: 'project', 'user', or 'plugin'. Controls which sections
            are treated as required. Defaults to 'project' for callers
            that don't know the scope.

    Returns:
        Validation results dictionary
    """
    results: Dict[str, Any] = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "checks": {
            "structure": {"pass": True, "details": ""},
            "consistency": {"pass": True, "details": ""},
            "best_practices": {
                "pass": True,
                "details": "",
            },
            "alignment": {"pass": True, "details": ""},
        },
    }

    if not path.exists():
        results["valid"] = False
        results["errors"].append("File does not exist")
        return results

    try:
        content = path.read_text(encoding="utf-8")
    except (IOError, UnicodeDecodeError) as e:
        results["valid"] = False
        results["errors"].append(f"Cannot read file: {e}")
        return results

    # Check structure
    frontmatter, _ = parse_frontmatter(content)
    sections = detect_sections(content)

    if not frontmatter:
        results["checks"]["structure"]["pass"] = False
        results["checks"]["structure"]["details"] = (
            "Missing frontmatter"
        )
        results["warnings"].append("No frontmatter found")
    else:
        results["checks"]["structure"]["details"] = (
            "Has frontmatter"
        )

    # Check required sections (scope-aware)
    missing_sections = []
    for req in required_sections_for(scope):
        if req not in sections:
            missing_sections.append(req)

    if missing_sections:
        results["checks"]["structure"]["pass"] = False
        results["checks"]["structure"]["details"] = (
            f"Missing sections: "
            f"{', '.join(missing_sections)}"
        )
        results["errors"].append(
            "Missing required sections: "
            f"{', '.join(missing_sections)}"
        )
        results["valid"] = False

    # Check best practices
    if len(content) > 50000:  # 50KB limit
        results["checks"]["best_practices"]["pass"] = False
        results["checks"]["best_practices"]["details"] = (
            "File too large (> 50KB)"
        )
        results["warnings"].append(
            "File is very large, consider splitting"
        )
    else:
        results["checks"]["best_practices"]["details"] = (
            "File size OK"
        )

    # Check for sensitive data patterns
    sensitive_patterns = [
        r'password\s*[:=]\s*["\'][^"\']+["\']',
        r'api[_-]?key\s*[:=]\s*["\'][^"\']+["\']',
        r'secret\s*[:=]\s*["\'][^"\']+["\']',
    ]
    for pattern in sensitive_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            results["checks"]["best_practices"][
                "pass"
            ] = False
            results["warnings"].append(
                "Possible sensitive data detected"
            )
            break

    return results


def calculate_audit_score(
    results: Dict[str, Any],
    sections: List[str],
    scope: str = "project",
) -> int:
    """Calculate audit score (0-100).

    Args:
        results: Validation results
        sections: Detected sections
        scope: 'project', 'user', or 'plugin'. Controls which sections
            count toward the required-section bonus.

    Returns:
        Score from 0 to 100
    """
    score = 50  # Base score

    # Add points for passing checks
    for check in results["checks"].values():
        if check["pass"]:
            score += 10

    # Add points for required sections present (scope-aware)
    for section in required_sections_for(scope):
        if section in sections:
            score += 5

    for section in RECOMMENDED_SECTIONS:
        if section in sections:
            score += 3

    # Subtract for errors and warnings
    score -= len(results["errors"]) * 10
    score -= len(results["warnings"]) * 3

    return max(0, min(100, score))


def generate_audit_findings(
    path: Path,
    content: str,
    validation: Dict[str, Any],
    detected_context: Dict[str, Any],
    scope: str = "project",
) -> List[Dict[str, Any]]:
    """Generate audit findings with fix suggestions.

    Args:
        path: Path to CLAUDE.md
        content: File content
        validation: Validation results
        detected_context: Detected project context
        scope: 'project', 'user', or 'plugin'. Controls which required
            sections are checked for fix suggestions.

    Returns:
        List of findings with fixes
    """
    findings: List[Dict[str, Any]] = []
    sections = detect_sections(content)

    # Check for missing required sections (scope-aware)
    for req in required_sections_for(scope):
        if req not in sections:
            fix_content = ""
            if req == "commands" and detected_context.get(
                "commands"
            ):
                commands = detected_context["commands"]
                cmd_lines = "\n".join([
                    (
                        f"{cmd['command']}  "
                        f"# {cmd['description']}"
                        if cmd.get("description")
                        else cmd["command"]
                    )
                    for cmd in commands[:5]
                ])
                fix_content = (
                    "## Key Commands\n\n"
                    f"```bash\n{cmd_lines}\n```"
                )
            elif req == "overview":
                desc = detected_context.get(
                    "description",
                    "Project description here.",
                )
                fix_content = (
                    f"## Project Overview\n\n{desc}"
                )

            findings.append({
                "id": f"missing-{req}",
                "category": "critical",
                "title": f"Missing {req.title()} section",
                "impact": (
                    "Users won't understand "
                    f"the project {req}"
                ),
                "fix": {
                    "type": "add_section",
                    "content": fix_content,
                },
            })

    # Check for missing recommended sections
    for rec in RECOMMENDED_SECTIONS:
        if rec not in sections:
            findings.append({
                "id": f"missing-{rec}",
                "category": "recommended",
                "title": f"Missing {rec.title()} section",
                "impact": (
                    "Would improve project understanding"
                ),
                "fix": {
                    "type": "add_section",
                    "content": (
                        f"## {rec.title()}\n\n"
                        f"Add {rec} information here."
                    ),
                },
            })

    # Check for alignment with detected facts
    if detected_context.get("languages"):
        for lang in detected_context["languages"]:
            if lang.lower() not in content.lower():
                findings.append({
                    "id": (
                        f"missing-mention-{lang.lower()}"
                    ),
                    "category": "nice_to_have",
                    "title": f"No mention of {lang}",
                    "impact": (
                        "Detected technology not documented"
                    ),
                    "fix": None,
                })

    return findings


def get_questions(
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Analyze context and return questions (Phase 1).

    Args:
        context: Operation context containing:
            - operation: create, optimize, validate, list
            - scope: project, user, plugin, all

    Returns:
        Dictionary containing:
            {
                "questions": [...],
                "inferred": {...},
                "audit": {...},  # For optimize
                "existing": {...},  # Existing info
            }
    """
    operation = context.get("operation", "create")
    scope = context.get("scope", "project")

    result: Dict[str, Any] = {
        "questions": [],
        "inferred": {},
        "validation": {"valid": True, "errors": []},
    }

    project_root = get_project_root()

    if operation == "create":
        # Detect project context
        detected = detect_project_context(project_root)
        result["inferred"] = detected

        # Check if file already exists
        target_path = get_claude_md_path(
            scope, project_root
        )
        if target_path.exists():
            result["existing"] = {
                "path": str(target_path),
                "exists": True,
            }
            result["questions"].append({
                "id": "overwrite",
                "question": (
                    "CLAUDE.md already exists at "
                    f"{target_path}. Overwrite?"
                ),
                "type": "choice",
                "options": [
                    "Yes, overwrite",
                    "No, cancel",
                ],
                "required": True,
            })

        # Ask for scope if not specified
        if not context.get("scope"):
            result["questions"].append({
                "id": "scope",
                "question": (
                    "Which CLAUDE.md would you like "
                    "to create?"
                ),
                "type": "choice",
                "options": ["project", "user", "plugin"],
                "required": True,
            })

    elif operation == "optimize":
        # Find existing file
        files = find_claude_md(scope)
        if not files:
            result["validation"]["valid"] = False
            result["validation"]["errors"].append(
                f"No CLAUDE.md found at scope '{scope}'"
            )
            return result

        # Analyze first found file
        file_info = files[0]
        path = Path(file_info["path"])
        content = path.read_text(encoding="utf-8")
        file_scope = file_info.get("scope", "project")

        # Run validation
        validation = validate_claude_md(path, file_scope)
        sections = detect_sections(content)
        score = calculate_audit_score(
            validation, sections, file_scope
        )

        # Detect project context for comparison
        detected = detect_project_context(project_root)

        # Generate findings
        findings = generate_audit_findings(
            path, content, validation, detected, file_scope
        )

        result["audit"] = {
            "score": score,
            "findings": findings,
            "validation": validation,
        }

        result["existing"] = {
            "path": str(path),
            "sections": sections,
            "content": content,
        }

        # Ask how to fix
        if findings:
            critical_count = len([
                f
                for f in findings
                if f["category"] == "critical"
            ])
            result["questions"].append({
                "id": "fix_mode",
                "question": (
                    f"Found {len(findings)} issues "
                    f"({critical_count} critical). "
                    "How would you like to fix them?"
                ),
                "type": "choice",
                "options": [
                    "Fix all",
                    "Fix critical only",
                    "Interactive",
                    "Skip",
                ],
            })

    elif operation == "validate":
        # Find and validate files
        files = find_claude_md(scope)
        if not files:
            result["validation"]["valid"] = False
            result["validation"]["errors"].append(
                f"No CLAUDE.md found at scope '{scope}'"
            )
            return result

        result["inferred"] = {"files": files}

    elif operation == "list":
        # List is direct execution, no questions needed
        result["inferred"] = {"scope": scope}

    return result


def execute_create(
    context: Dict[str, Any],
    templates_dir: Path,
) -> Dict[str, Any]:
    """Execute CLAUDE.md creation.

    Args:
        context: Context with all required fields
        templates_dir: Path to templates directory

    Returns:
        Result dictionary
    """
    scope = context.get("scope", "project")
    project_root = get_project_root()

    # Get target path
    target_path = get_claude_md_path(scope, project_root)

    # Check for existing file
    if (
        target_path.exists()
        and context.get("overwrite") != "Yes, overwrite"
    ):
        return {
            "success": False,
            "message": (
                f"CLAUDE.md already exists at "
                f"{target_path}. Use optimize instead."
            ),
        }

    # Prepare template variables. The three scopes ship templates that
    # reference disjoint variable sets — wire each scope's expected keys
    # explicitly so --responses content from Phase 2 actually renders.
    template_vars: Dict[str, Any] = {
        "name": context.get("name", project_root.name),
        "description": context.get("description", ""),
    }

    if scope == "user":
        template_vars.update({
            "preferred_languages": context.get(
                "preferred_languages", []
            ),
            "preferred_tools": context.get(
                "preferred_tools", []
            ),
            "default_behaviors": context.get(
                "default_behaviors", ""
            ),
            "patterns": context.get("patterns", ""),
            "tool_config": context.get("tool_config", ""),
        })
    elif scope == "plugin":
        template_vars.update({
            "plugin_type": context.get("plugin_type", ""),
            "provides": context.get("provides", []),
            "usage": context.get("usage", ""),
            "config_options": context.get(
                "config_options", ""
            ),
            "extension_points": context.get(
                "extension_points", ""
            ),
        })
    else:  # project (default)
        template_vars.update({
            "languages": context.get("languages", []),
            "tools": context.get("tools", []),
            "commands": context.get("commands", []),
            "project_type": context.get("project_type", ""),
            "architecture": context.get("architecture", ""),
            "conventions": context.get("conventions", ""),
            "constraints": context.get("constraints", ""),
        })

    # Seed SPDX template vars (year, copyright_holder, license_id,
    # plus pre-formatted spdx_md / spdx_hash / spdx_slash blocks).
    template_vars.update(spdx_template_variables(context))

    # Select template
    template_name = TEMPLATES.get(
        scope, TEMPLATES["project"]
    )

    try:
        content = render_template(
            templates_dir, template_name, template_vars
        )
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to render template: {e}",
        }

    # Ensure directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Write file
    try:
        target_path.write_text(content, encoding="utf-8")
    except IOError as e:
        return {
            "success": False,
            "message": f"Failed to write file: {e}",
        }

    return {
        "success": True,
        "message": f"Created CLAUDE.md at {target_path}",
        "path": str(target_path),
    }


def execute_optimize(
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute CLAUDE.md optimization.

    Args:
        context: Context with fixes to apply

    Returns:
        Result dictionary
    """
    scope = context.get("scope", "project")
    fix_mode = context.get("fix_mode", "Skip")
    fixes = context.get("fixes", [])

    if fix_mode == "Skip":
        return {
            "success": True,
            "message": "Optimization skipped",
            "changes": [],
        }

    # Find file
    files = find_claude_md(scope)
    if not files:
        return {
            "success": False,
            "message": (
                "No CLAUDE.md found at "
                f"scope '{scope}'"
            ),
        }

    file_info = files[0]
    path = Path(file_info["path"])
    content = path.read_text(encoding="utf-8")
    file_scope = file_info.get("scope", "project")

    # Get findings
    project_root = get_project_root()
    detected = detect_project_context(project_root)
    validation = validate_claude_md(path, file_scope)
    findings = generate_audit_findings(
        path, content, validation, detected, file_scope
    )

    # Filter findings based on fix_mode
    if fix_mode == "Fix critical only":
        findings = [
            f
            for f in findings
            if f["category"] == "critical"
        ]
    elif fix_mode == "Interactive" and fixes:
        findings = [
            f for f in findings if f["id"] in fixes
        ]

    # Apply fixes
    changes: List[str] = []
    for finding in findings:
        if finding.get("fix") and finding["fix"].get(
            "content"
        ):
            fix = finding["fix"]
            if fix["type"] == "add_section":
                # Add section before the footer
                footer_match = re.search(
                    r'\n---\s*\n\*Generated', content
                )
                if footer_match:
                    insert_pos = footer_match.start()
                    content = (
                        content[:insert_pos]
                        + "\n"
                        + fix["content"]
                        + "\n"
                        + content[insert_pos:]
                    )
                else:
                    content = (
                        content.rstrip()
                        + "\n\n"
                        + fix["content"]
                        + "\n"
                    )
                changes.append(
                    f"Added {finding['title']}"
                )

    if changes:
        try:
            path.write_text(content, encoding="utf-8")
        except IOError as e:
            return {
                "success": False,
                "message": (
                    f"Failed to write changes: {e}"
                ),
            }

    # Recalculate score
    new_validation = validate_claude_md(path, file_scope)
    new_sections = detect_sections(content)
    new_score = calculate_audit_score(
        new_validation, new_sections, file_scope
    )

    return {
        "success": True,
        "message": (
            f"Applied {len(changes)} fixes to CLAUDE.md"
        ),
        "changes": changes,
        "new_score": new_score,
        "path": str(path),
    }


def execute_validate(
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute CLAUDE.md validation.

    Args:
        context: Context with scope

    Returns:
        Result dictionary
    """
    scope = context.get("scope", "all")
    files = find_claude_md(scope)

    if not files:
        return {
            "success": True,
            "operation": "validate",
            "results": [],
            "summary": {
                "total": 0,
                "valid": 0,
                "invalid": 0,
            },
        }

    results = []

    for file_info in files:
        path = Path(file_info["path"])
        file_scope = file_info.get("scope", "project")
        validation = validate_claude_md(path, file_scope)

        results.append({
            "name": file_info["scope"],
            "path": str(path),
            "valid": validation["valid"],
            "errors": validation["errors"],
            "warnings": validation["warnings"],
        })

    valid_count = sum(
        1 for r in results if r["valid"]
    )
    invalid_count = len(results) - valid_count

    return {
        "success": True,
        "operation": "validate",
        "results": results,
        "summary": {
            "total": len(results),
            "valid": valid_count,
            "invalid": invalid_count,
        },
    }


def execute_list(
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute CLAUDE.md listing.

    Args:
        context: Context (optional scope filter)

    Returns:
        Result dictionary
    """
    scope = context.get("scope", "all")
    files = find_claude_md(scope)

    # Add validation status to each file
    for file_info in files:
        path = Path(file_info["path"])
        file_scope = file_info.get("scope", "project")
        validation = validate_claude_md(path, file_scope)
        file_info["valid"] = validation["valid"]
        file_info["errors"] = len(validation["errors"])
        file_info["warnings"] = len(
            validation["warnings"]
        )

    return {
        "success": True,
        "operation": "list",
        "files": files,
        "count": len(files),
    }


def execute(
    context: Dict[str, Any],
    responses: Dict[str, Any],
    templates_dir: Path,
) -> Dict[str, Any]:
    """Execute the requested operation (Phase 2).

    Args:
        context: Operation context
        responses: User responses to questions (if any)
        templates_dir: Path to templates directory

    Returns:
        Result dictionary
    """
    operation = context.get("operation", "create")

    # Merge responses into context
    if responses:
        context.update(responses)

    if operation == "create":
        return execute_create(context, templates_dir)
    elif operation == "optimize":
        return execute_optimize(context)
    elif operation == "validate":
        return execute_validate(context)
    elif operation == "list":
        return execute_list(context)
    else:
        return {
            "success": False,
            "message": (
                f"Unknown operation: {operation}"
            ),
        }
