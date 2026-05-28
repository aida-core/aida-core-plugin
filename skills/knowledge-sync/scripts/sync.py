#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Knowledge sync entry point (#22).

Reads `agents/<agent>/knowledge/sources.yml`, walks each declared
source, fetches its content, and applies updates to the targeted
section of the target knowledge file.

Two modes:
  - `sync`: apply updates to disk
  - `status` / `--dry-run`: report what *would* change, write nothing

Output is JSON (machine-friendly for CI) on stdout; exit 0 on
success (no changes needed or all applied cleanly), 1 on partial
failure (some sources had problems).

Usage:
    python sync.py --agent claude-code-expert
    python sync.py --agent claude-code-expert --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).parent
SHARED = SCRIPT_DIR.parent.parent.parent / "scripts"
sys.path.insert(0, str(SHARED))

from shared.decisions_log import (  # noqa: E402
    Decision,
    read_decisions,
)
from shared.http_source import (  # noqa: E402
    DEFAULT_CACHE_TTL,
    FetchOutcome,
    HttpFetcher,
)
from shared.knowledge_sync import (  # noqa: E402
    KnowledgeSyncError,
    diff_summary,
    read_local_source,
    update_section,
)

import yaml  # noqa: E402


def _agent_root(project_root: Path, agent: str) -> Path:
    return project_root / "agents" / agent


def _load_sources(
    project_root: Path, agent: str
) -> List[Dict[str, Any]]:
    """Load and validate sources.yml. Returns [] if missing."""
    sources_path = (
        _agent_root(project_root, agent) / "knowledge" / "sources.yml"
    )
    if not sources_path.is_file():
        return []
    try:
        data = yaml.safe_load(sources_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise KnowledgeSyncError(
            f"sources.yml is not valid YAML: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise KnowledgeSyncError(
            "sources.yml must be a mapping with a top-level "
            "`sources:` key."
        )
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        raise KnowledgeSyncError(
            "`sources:` must be a list in sources.yml"
        )
    return sources


def _resolve_target(
    project_root: Path, agent: str, source: Dict[str, Any]
) -> Optional[Path]:
    """Return the absolute path to the target knowledge file."""
    target = source.get("target", {})
    if not isinstance(target, dict):
        return None
    rel = target.get("file")
    if not isinstance(rel, str):
        return None
    return _agent_root(project_root, agent) / rel


def _normalize_body(text: Optional[str]) -> Optional[str]:
    """Strip a single trailing newline so source-with-final-LF compares
    equal to the LF-stripped marker body. Without this, every sync
    would report ``changed`` because the marker-block parser strips
    the trailing newline from its body.
    """
    if text is None:
        return None
    return text[:-1] if text.endswith("\n") else text


def _validate_cache_ttl(source: Dict[str, Any]) -> Optional[FetchOutcome]:
    """Reject negative ``cache_ttl`` values at source-loading time."""
    ttl = source.get("cache_ttl")
    if ttl is None:
        return None
    if not isinstance(ttl, int) or isinstance(ttl, bool):
        return FetchOutcome(
            kind="fetch-error",
            message=(
                f"`cache_ttl` must be a non-negative integer, got "
                f"{ttl!r}."
            ),
        )
    if ttl < 0:
        return FetchOutcome(
            kind="fetch-error",
            message=(
                f"`cache_ttl` must be a non-negative integer, got {ttl}."
            ),
        )
    return None


def _dispatch_source(
    project_root: Path,
    source: Dict[str, Any],
    fetcher: HttpFetcher,
) -> FetchOutcome:
    """Dispatch a source declaration to its fetcher and return a
    :class:`FetchOutcome` describing the result.

    Body normalization (trailing-newline strip) is applied here so
    every dispatch path returns content shaped to compare cleanly
    against marker-block bodies.
    """
    typ = source.get("type")

    if typ == "local":
        path = source.get("path")
        if not isinstance(path, str):
            return FetchOutcome(
                kind="source-missing",
                message=(
                    "Local source missing a string `path` field."
                ),
            )
        text = read_local_source(str(project_root / path))
        if text is None:
            return FetchOutcome(
                kind="source-missing",
                message=(
                    f"Could not read local source at {path!r}."
                ),
            )
        return FetchOutcome(
            kind="content", content=_normalize_body(text)
        )

    if typ in ("http", "https"):
        url = source.get("url")
        if not isinstance(url, str) or not url:
            return FetchOutcome(
                kind="fetch-error",
                message="HTTP source requires a string `url` field.",
            )
        bad_ttl = _validate_cache_ttl(source)
        if bad_ttl is not None:
            return bad_ttl
        selector = source.get("selector")
        if selector is not None and not isinstance(selector, str):
            return FetchOutcome(
                kind="fetch-error",
                message="`selector` must be a string CSS selector.",
            )
        cache_ttl = source.get("cache_ttl")
        if cache_ttl is None:
            cache_ttl = DEFAULT_CACHE_TTL
        outcome = fetcher.fetch(
            url, selector=selector, cache_ttl=cache_ttl
        )
        if outcome.kind == "content":
            return FetchOutcome(
                kind="content",
                content=_normalize_body(outcome.content),
                from_cache=outcome.from_cache,
            )
        return outcome

    return FetchOutcome(
        kind="fetch-error",
        message=(
            f"Unsupported source type: {typ!r}. Supported types: "
            "local, http, https."
        ),
    )


def _materialize_decision(decision: Decision) -> Optional[Dict[str, Any]]:
    """Turn an in-use Decision into a source-shaped dict that sync's
    existing dispatch path can consume.

    ``target_file`` is interpreted as relative to the agent's
    ``knowledge/`` directory (matching the convention curator authors
    use). The materialized source uses the full
    ``knowledge/<file>`` path expected by ``_resolve_target``.

    Returns None if the decision lacks the target metadata needed to
    sync it (no target_file and no informs[0] fallback, or no
    target_section). Callers surface those as ``invalid-target``.
    """
    target_file = decision.target_file or (
        decision.informs[0] if decision.informs else None
    )
    if not target_file or not decision.target_section:
        return None
    if not target_file.startswith("knowledge/"):
        target_file = f"knowledge/{target_file}"
    return {
        "name": f"decision:{decision.url}",
        "type": "http",
        "url": decision.url,
        "target": {
            "file": target_file,
            "section": decision.target_section,
        },
    }


def _detect_conflicts(
    sources: List[Dict[str, Any]],
    decisions: List[Decision],
) -> Dict[str, str]:
    """Map sources.yml URLs that conflict with the decision log to a
    human-readable reason.

    A conflict exists when sources.yml asserts a URL should be synced
    but the decision log marks that URL ``rejected``. The user is
    silently editing past a curator verdict; sync surfaces it so they
    can run ``/aida knowledge review`` to override.
    """
    conflicts: Dict[str, str] = {}
    by_url = {d.url: d for d in decisions}
    for source in sources:
        if source.get("type") not in ("http", "https"):
            continue
        url = source.get("url")
        if not isinstance(url, str):
            continue
        decision = by_url.get(url)
        if decision and decision.status == "rejected":
            locked_note = " (locked)" if decision.locked else ""
            conflicts[url] = (
                f"URL is listed in sources.yml but decisions.json "
                f"marks it rejected{locked_note}. Run "
                "`/aida knowledge review <agent>` to override, or "
                "remove the entry from sources.yml."
            )
    return conflicts


def run(
    project_root: Path,
    agent: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Walk sources for ``agent`` and sync (or report) each.

    Sources come from two places:

      1. ``sources.yml`` — hand-curated entries (existing behavior)
      2. ``decisions.json`` — every ``status: in-use`` decision is
         materialized into an http source and processed alongside
         the rest. Re-runs are idempotent because the http fetcher's
         cache deduplicates network calls.

    Conflicts (a URL listed in sources.yml that's marked ``rejected``
    in decisions.json) surface as ``conflict-suppressed`` per-source
    results so the user can run ``/aida knowledge review`` to
    reconcile.

    Returns a structured report; never raises for per-source
    failures — those go in the per-source ``status`` field.
    """
    try:
        sources = _load_sources(project_root, agent)
    except KnowledgeSyncError as exc:
        return {
            "success": False,
            "agent": agent,
            "message": str(exc),
            "results": [],
        }

    knowledge_dir = _agent_root(project_root, agent) / "knowledge"
    try:
        decisions = read_decisions(knowledge_dir)
    except ValueError as exc:
        return {
            "success": False,
            "agent": agent,
            "message": (
                f"Could not read decisions.json: {exc}"
            ),
            "results": [],
        }

    # Merge in-use decisions as additional http sources, skipping any
    # URLs the user has already declared by hand in sources.yml.
    yml_urls = {
        s.get("url")
        for s in sources
        if s.get("type") in ("http", "https")
    }
    for decision in decisions:
        if decision.status != "in-use":
            continue
        if decision.url in yml_urls:
            continue  # sources.yml wins; explicit declaration trumps materialized
        materialized = _materialize_decision(decision)
        if materialized is None:
            sources.append(
                {
                    "name": f"decision:{decision.url}",
                    "type": "http",
                    "url": decision.url,
                    # No target — will be caught as invalid-target
                    "_decision_missing_target": True,
                }
            )
        else:
            sources.append(materialized)

    if not sources and not decisions:
        return {
            "success": True,
            "agent": agent,
            "message": (
                f"No sources declared for agent {agent!r} "
                "(sources.yml missing or empty, no in-use decisions)."
            ),
            "results": [],
        }

    conflicts = _detect_conflicts(sources, decisions)

    results: List[Dict[str, Any]] = []
    overall_ok = True
    fetcher = HttpFetcher()

    # Emit conflict-suppressed entries first so they appear at the
    # top of the report and can't be missed.
    for url, message in conflicts.items():
        results.append(
            {
                "name": f"conflict:{url}",
                "status": "conflict-suppressed",
                "target": None,
                "message": message,
            }
        )
        overall_ok = False

    # Drop the conflicting URLs from the source list before
    # dispatching, so we don't actually sync rejected content into
    # the knowledge files.
    sources = [
        s
        for s in sources
        if s.get("url") not in conflicts
    ]

    for source in sources:
        name = source.get("name") or source.get("type") or "<unnamed>"
        result: Dict[str, Any] = {
            "name": name,
            "status": "unknown",
            "target": None,
        }

        target = _resolve_target(project_root, agent, source)
        if target is None:
            result["status"] = "invalid-target"
            result["message"] = (
                "Source has no valid `target.file` field."
            )
            overall_ok = False
            results.append(result)
            continue
        result["target"] = str(target)

        section_name = (source.get("target") or {}).get("section")
        if not isinstance(section_name, str) or not section_name:
            result["status"] = "invalid-target"
            result["message"] = (
                "Source target must declare a `section` name."
            )
            overall_ok = False
            results.append(result)
            continue

        outcome = _dispatch_source(project_root, source, fetcher)
        if outcome.kind != "content":
            result["status"] = outcome.kind
            if outcome.message is not None:
                result["message"] = outcome.message
            overall_ok = False
            results.append(result)
            continue
        body = outcome.content
        if outcome.from_cache:
            result["from_cache"] = True

        if not target.is_file():
            result["status"] = "target-missing"
            result["message"] = (
                f"Target knowledge file does not exist: {target}"
            )
            overall_ok = False
            results.append(result)
            continue

        try:
            content = target.read_text(encoding="utf-8")
            summary = diff_summary(content, {section_name: body})
            section_status = summary[0]["status"]
        except KnowledgeSyncError as exc:
            result["status"] = "marker-error"
            result["message"] = str(exc)
            overall_ok = False
            results.append(result)
            continue

        if section_status == "missing":
            result["status"] = "missing-section"
            result["message"] = (
                f"Knowledge file {target.name} has no upstream "
                f"section named {section_name!r}. Add "
                f'`<!-- upstream:start name="{section_name}" -->`'
                " markers to opt that section into sync."
            )
            overall_ok = False
            results.append(result)
            continue

        if section_status == "unchanged":
            result["status"] = "unchanged"
            results.append(result)
            continue

        # status == "changed"
        if dry_run:
            result["status"] = "would-change"
            result["bytes_changed"] = (
                summary[0]["new_length"]
                - summary[0]["old_length"]
            )
            results.append(result)
            continue

        try:
            new_content, _ = update_section(
                content, section_name, body
            )
            target.write_text(new_content, encoding="utf-8")
        except (KnowledgeSyncError, OSError) as exc:
            result["status"] = "write-error"
            result["message"] = str(exc)
            overall_ok = False
            results.append(result)
            continue

        result["status"] = "changed"
        results.append(result)

    return {
        "success": overall_ok,
        "agent": agent,
        "dry_run": dry_run,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="sync.py",
        description=(
            "Sync an agent's knowledge files with declared "
            "upstream sources."
        ),
    )
    parser.add_argument(
        "--agent",
        required=True,
        help="Agent name (e.g., 'claude-code-expert')",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Don't write anything; report what would change."
        ),
    )
    args = parser.parse_args()

    report = run(
        project_root=args.project_root.resolve(),
        agent=args.agent,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
