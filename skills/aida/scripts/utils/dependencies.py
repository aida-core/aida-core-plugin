# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Plugin dependency declaration + checking (#20).

This module is the foundation for plugin-to-plugin dependency
management. It parses dependency version specs declared in
`aida-config.json` (under the optional ``dependencies`` field) and
checks them against installed plugins.

Scope is deliberately small:

  - Parse and check version specs (exact, `>=`, `^` caret, `~` tilde)
  - Compare against the output of `discover_installed_plugins()`
  - Surface per-dep status: satisfied / wrong-version / missing

Out of scope (future work):

  - Install-time resolution / auto-install
  - Agent registry across plugins (`/aida agents list`)
  - Collision detection between same-named agents in different plugins

Why a tiny custom parser instead of `packaging` / `semver`: we don't
need NPM-grade range syntax, and adding a runtime dep for four
operators isn't worth it. If we ever need full PEP 440 / semver
ranges, swap this for `packaging.specifiers`.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# Recognized operators. Order matters: longest prefix first.
_OPERATORS = ("==", ">=", "<=", "^", "~", ">", "<")

_VERSION_RE = re.compile(r"^\d+(?:\.\d+){0,2}$")


def _parse_version(version: str) -> Tuple[int, int, int]:
    """Parse a 1-3 part dotted-int version into a 3-tuple.

    `"1"` -> (1, 0, 0); `"1.2"` -> (1, 2, 0); `"1.2.3"` -> (1, 2, 3).
    Raises ``ValueError`` on garbage so callers can tell a malformed
    spec from a missing one.
    """
    if not isinstance(version, str) or not _VERSION_RE.match(version):
        raise ValueError(f"Not a dotted-int version: {version!r}")
    parts = [int(p) for p in version.split(".")]
    while len(parts) < 3:
        parts.append(0)
    major, minor, patch = parts[:3]
    return major, minor, patch


def parse_version_spec(spec: str) -> Tuple[str, str]:
    """Parse a dependency version spec into (operator, version).

    Accepted forms:

      - ``"1.2.3"`` -> ``("==", "1.2.3")`` (bare version = exact)
      - ``">=1.2.3"``, ``">1.2.3"``, ``"<=1.2.3"``, ``"<1.2.3"``,
        ``"==1.2.3"`` -> straightforward comparators
      - ``"^1.2.3"`` -> caret: ``>=1.2.3, <2.0.0`` (major-compatible)
      - ``"~1.2.3"`` -> tilde: ``>=1.2.3, <1.3.0`` (minor-compatible)

    Returns:
        Tuple of (operator, version-string). The operator preserves
        the input form (``"^"`` stays ``"^"``); ``version_satisfies``
        handles the expansion.

    Raises:
        ValueError on malformed input.
    """
    if not isinstance(spec, str):
        raise ValueError(
            f"Version spec must be a string, got {type(spec).__name__}"
        )
    s = spec.strip()
    if not s:
        raise ValueError("Empty version spec")

    for op in _OPERATORS:
        if s.startswith(op):
            version = s[len(op):].strip()
            _parse_version(version)  # validate
            return op, version

    # Bare version -> exact match
    _parse_version(s)
    return "==", s


def version_satisfies(version: str, spec: str) -> bool:
    """Return True if ``version`` satisfies ``spec``.

    See :func:`parse_version_spec` for the supported operators.
    Malformed input returns False rather than raising — dep
    checking should be best-effort, not fragile.
    """
    try:
        op, want = parse_version_spec(spec)
        have = _parse_version(version)
        wanted = _parse_version(want)
    except ValueError:
        return False

    if op == "==":
        return have == wanted
    if op == ">":
        return have > wanted
    if op == ">=":
        return have >= wanted
    if op == "<":
        return have < wanted
    if op == "<=":
        return have <= wanted
    if op == "^":
        # Major-compatible: >= wanted, < next major
        next_major = (wanted[0] + 1, 0, 0)
        return wanted <= have < next_major
    if op == "~":
        # Minor-compatible: >= wanted, < next minor
        next_minor = (wanted[0], wanted[1] + 1, 0)
        return wanted <= have < next_minor

    # Unreachable — parse_version_spec only returns the operators above
    return False


def check_dependencies(
    declared: Dict[str, str],
    installed: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Resolve declared dependencies against installed plugins.

    Args:
        declared: Map of plugin-name -> version-spec, as read from
            an `aida-config.json` `dependencies` field.
        installed: List of plugin dicts from
            `discover_installed_plugins()` (each has at least
            ``name`` and ``version``).

    Returns:
        List of result dicts, one per declared dep:

        - ``name``: dep name
        - ``required``: original spec string
        - ``installed``: installed version, or None if missing
        - ``status``: ``"satisfied"``, ``"wrong-version"``, or
          ``"missing"``
    """
    by_name = {p.get("name"): p for p in installed if p.get("name")}
    results: List[Dict[str, Any]] = []
    for name, spec in sorted(declared.items()):
        plugin = by_name.get(name)
        if plugin is None:
            results.append(
                {
                    "name": name,
                    "required": spec,
                    "installed": None,
                    "status": "missing",
                }
            )
            continue

        installed_version = plugin.get("version", "0.0.0")
        ok = version_satisfies(installed_version, spec)
        results.append(
            {
                "name": name,
                "required": spec,
                "installed": installed_version,
                "status": "satisfied" if ok else "wrong-version",
            }
        )
    return results
