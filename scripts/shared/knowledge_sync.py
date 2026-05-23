# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Knowledge-file section synchronization primitives (#22).

The goal: keep upstream facts in an agent's knowledge file current,
while preserving custom design decisions and conventions written by
the agent author.

Approach: marker-delimited sections. A knowledge file can carry
zero or more "upstream" sections, each named:

    <!-- upstream:start name="extension-types" -->
    ...content that gets replaced on sync...
    <!-- upstream:end -->

Everything outside markers stays untouched. Multiple sections per
file work. Section names must be unique within a file.

Sync operations (`update_section`, `replace_or_append`) are
pure-function over file contents — call sites are responsible for
the read / write cycle so dry-run / diff modes are trivial to
build.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Markers are HTML comments so they survive markdown renderers
# without showing up as visible text in editors / preview panes.
_START_RE = re.compile(
    r"<!--\s*upstream:start\s+name=\"(?P<name>[A-Za-z0-9_\-]+)\"\s*-->",
    re.IGNORECASE,
)
_END_RE = re.compile(
    r"<!--\s*upstream:end\s*-->", re.IGNORECASE
)


@dataclass(frozen=True)
class SectionLocation:
    """Where a named upstream section lives in a file."""

    name: str
    # Slice indices of the body (between the start and end markers,
    # not including the marker lines themselves).
    body_start: int
    body_end: int
    # Slice indices of the *entire* block including markers — useful
    # for whole-block replacement.
    block_start: int
    block_end: int


class KnowledgeSyncError(ValueError):
    """Raised on malformed marker structure (unbalanced / nested /
    duplicated section names).
    """


def find_sections(content: str) -> List[SectionLocation]:
    """Return all upstream sections in ``content``, ordered by position.

    Raises:
        KnowledgeSyncError: if markers are unbalanced, nested, or if
            two sections share a name.
    """
    sections: List[SectionLocation] = []
    seen_names: set[str] = set()
    pos = 0
    while True:
        start_match = _START_RE.search(content, pos)
        if start_match is None:
            break

        # No nesting — search for end *after* the start, but
        # confirm no second start appears before the end.
        end_match = _END_RE.search(content, start_match.end())
        if end_match is None:
            raise KnowledgeSyncError(
                f"Unbalanced upstream:start marker at offset "
                f"{start_match.start()} — missing upstream:end."
            )
        nested_start = _START_RE.search(
            content, start_match.end(), end_match.start()
        )
        if nested_start is not None:
            raise KnowledgeSyncError(
                f"Nested upstream:start at offset "
                f"{nested_start.start()} — sections may not nest."
            )

        name = start_match.group("name")
        if name in seen_names:
            raise KnowledgeSyncError(
                f"Duplicate upstream section name {name!r}. "
                "Each section name must be unique per file."
            )
        seen_names.add(name)

        # Body = content between the two markers (skip the marker
        # lines themselves; strip the leading/trailing newlines so
        # callers get clean content).
        body_start = start_match.end()
        body_end = end_match.start()
        # If the start marker is on its own line, drop the trailing
        # newline so the body doesn't begin with a blank line.
        if content[body_start:body_start + 1] == "\n":
            body_start += 1
        # Same for the end marker — if there's a newline immediately
        # before it, treat that as the end of the body.
        if (
            body_end > body_start
            and content[body_end - 1:body_end] == "\n"
        ):
            body_end -= 1

        sections.append(
            SectionLocation(
                name=name,
                body_start=body_start,
                body_end=body_end,
                block_start=start_match.start(),
                block_end=end_match.end(),
            )
        )
        pos = end_match.end()

    return sections


def get_section_bodies(content: str) -> Dict[str, str]:
    """Return a {name: body-text} map of all upstream sections."""
    return {
        s.name: content[s.body_start:s.body_end]
        for s in find_sections(content)
    }


def update_section(
    content: str,
    name: str,
    new_body: str,
) -> Tuple[str, bool]:
    """Replace the body of a named section.

    The new body is sandwiched between the original marker pair —
    the markers are *not* rewritten so any whitespace quirks
    around them survive.

    Args:
        content: The full file content.
        name: Section name (must already exist in ``content``).
        new_body: New body text. Leading / trailing newlines are
            preserved as-passed; callers usually want the body
            to end in a newline so the closing marker sits on its
            own line.

    Returns:
        Tuple of (new_content, changed). `changed` is False when
        the new body is byte-identical to the old one, so callers
        can skip a no-op write.

    Raises:
        KnowledgeSyncError: if ``name`` doesn't exist in
            ``content``, or the marker structure is malformed.
    """
    for section in find_sections(content):
        if section.name != name:
            continue
        old_body = content[section.body_start:section.body_end]
        if old_body == new_body:
            return content, False
        new_content = (
            content[: section.body_start]
            + new_body
            + content[section.body_end:]
        )
        return new_content, True

    raise KnowledgeSyncError(
        f"No upstream section named {name!r} in content. "
        "Add `<!-- upstream:start name=\"...\" -->` ... "
        "`<!-- upstream:end -->` markers to the file first."
    )


def diff_summary(
    content: str,
    updates: Dict[str, str],
) -> List[Dict[str, object]]:
    """Compute a per-section change summary without writing anything.

    Args:
        content: Current file content.
        updates: Map of section-name → new body text.

    Returns:
        Sorted list of dicts:
        - ``name``: section name
        - ``status``: ``"unchanged"`` | ``"changed"`` | ``"missing"``
            (``"missing"`` means the file has no section by that
            name — caller might want to add one before syncing)
        - ``old_length``, ``new_length``: byte counts of the
            bodies (cheap proxy for "how much changed")
    """
    existing = get_section_bodies(content)
    summary: List[Dict[str, object]] = []
    for name in sorted(updates):
        new_body = updates[name]
        if name not in existing:
            summary.append(
                {
                    "name": name,
                    "status": "missing",
                    "old_length": 0,
                    "new_length": len(new_body),
                }
            )
            continue
        old_body = existing[name]
        summary.append(
            {
                "name": name,
                "status": (
                    "unchanged"
                    if old_body == new_body
                    else "changed"
                ),
                "old_length": len(old_body),
                "new_length": len(new_body),
            }
        )
    return summary


def fence_section(name: str, body: str) -> str:
    """Render a freshly-fenced section block.

    Useful for tooling that wants to *add* a new upstream section
    rather than just update existing ones. Returns:

        <!-- upstream:start name="<name>" -->
        <body>
        <!-- upstream:end -->

    The body is sandwiched between newlines so the markers sit on
    their own lines regardless of what the body ends with.
    """
    if not re.match(r"^[A-Za-z0-9_\-]+$", name):
        raise KnowledgeSyncError(
            f"Invalid section name {name!r} — must match "
            f"[A-Za-z0-9_-]+"
        )
    trimmed = body.strip("\n")
    return (
        f'<!-- upstream:start name="{name}" -->\n'
        f"{trimmed}\n"
        f"<!-- upstream:end -->"
    )


def read_local_source(
    path: str,
) -> Optional[str]:
    """Read a local file as an upstream-section source.

    Returns the file's contents, or None if the file doesn't exist
    or can't be read. Callers should treat None as "skip this
    source" rather than fail — knowledge sync should be best-effort.
    """
    from pathlib import Path

    p = Path(path)
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
