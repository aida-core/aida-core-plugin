#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Validate YAML frontmatter in markdown files against a JSON schema.

All markdown files must have frontmatter with a 'type' field that determines
which validation rules apply. Supported types:
  - skill, agent: require name, description, version, tags
  - adr: requires title, status, date
  - documentation, guide, reference, readme: require title
  - diagram: requires title, diagram-type
  - changelog: requires title
  - issue: requires title, issue (number)

Usage:
    python validate_frontmatter.py [--schema SCHEMA] [FILES...]

If no files specified, finds all *.md files in the project.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional, List

# Bootstrap AIDA environment to ensure dependencies are available
from shared.bootstrap import ensure_aida_environment
ensure_aida_environment()

import yaml  # noqa: E402
import jsonschema  # noqa: E402


FRONTMATTER_PATTERN = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)

# Directories/patterns to ignore
IGNORE_PATTERNS = [
    'node_modules',
    '.git',
    '__pycache__',
    '.pytest_cache',
    '.ruff_cache',
    'venv',
    '.venv',
    'issues',
    '.issues',
]

# Individual filenames to skip. GitHub renders these directly into
# its UI (PR description box, etc.); embedding YAML frontmatter
# would show up verbatim in every PR description created from the
# template, which is exactly the wrong thing.
IGNORE_FILENAMES = frozenset({
    "PULL_REQUEST_TEMPLATE.md",
})


def should_ignore(filepath: Path) -> bool:
    """Check if file should be ignored."""
    parts = filepath.parts
    if any(pattern in parts for pattern in IGNORE_PATTERNS):
        return True
    return filepath.name in IGNORE_FILENAMES


def extract_frontmatter(content: str) -> Optional[dict]:
    """Extract YAML frontmatter from markdown content."""
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        return None
    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in frontmatter: {e}")


def validate_file(filepath: Path, schema: dict) -> List[str]:
    """Validate a single file's frontmatter. Returns list of errors."""
    errors = []

    try:
        content = filepath.read_text(encoding='utf-8')
    except Exception as e:
        return [f"Cannot read file: {e}"]

    try:
        frontmatter = extract_frontmatter(content)
    except ValueError as e:
        return [str(e)]

    if frontmatter is None:
        return ["Missing frontmatter (all markdown files must have frontmatter with 'type' field)"]

    # Validate against schema
    validator = jsonschema.Draft7Validator(schema)
    for error in validator.iter_errors(frontmatter):
        path = '.'.join(str(p) for p in error.absolute_path) if error.absolute_path else 'root'
        errors.append(f"{path}: {error.message}")

    return errors


def find_markdown_files(root: Path) -> List[Path]:
    """Find all markdown files in the project."""
    files = []
    for f in root.rglob('*.md'):
        if not should_ignore(f):
            files.append(f)
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description='Validate frontmatter in markdown files')
    parser.add_argument('files', nargs='*', help='Files to validate (default: all *.md)')
    parser.add_argument('--schema', default='.frontmatter-schema.json',
                        help='Path to JSON schema file')
    args = parser.parse_args()

    # Load schema
    schema_path = Path(args.schema)
    if not schema_path.exists():
        print(f"Error: Schema file not found: {schema_path}", file=sys.stderr)
        sys.exit(1)

    try:
        schema = json.loads(schema_path.read_text())
    except Exception as e:
        print(f"Error loading schema: {e}", file=sys.stderr)
        sys.exit(1)

    # Get files to validate
    if args.files:
        files = [Path(f) for f in args.files]
    else:
        files = find_markdown_files(Path.cwd())

    if not files:
        print("No files to validate")
        sys.exit(0)

    # Validate each file
    total_errors = 0
    files_with_errors = 0
    for filepath in files:
        errors = validate_file(filepath, schema)
        if errors:
            files_with_errors += 1
            print(f"\n{filepath}:")
            for error in errors:
                print(f"  - {error}")
            total_errors += len(errors)

    # Summary
    if total_errors:
        print(f"\nFound {total_errors} error(s) in {files_with_errors} of {len(files)} file(s)")
        sys.exit(1)
    else:
        print(f"All {len(files)} file(s) valid")
        sys.exit(0)


if __name__ == '__main__':
    main()
