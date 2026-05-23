#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Plugin Manager Script - Unified Two-Phase API

Entry point for all plugin operations:
- Extension CRUD: create, validate, version, list
- Project scaffolding: scaffold
- Standards migration: update

Routes to the appropriate operations module based on context.

Usage:
    # Extension operations
    python manage.py --get-questions --context='{"operation": "create", ...}'
    python manage.py --execute --context='{"operation": "validate", ...}'

    # Scaffold operation
    python manage.py --get-questions --context='{"operation": "scaffold", ...}'
    python manage.py --execute --context='{"operation": "scaffold", ...}'

    # Update operation
    python manage.py --get-questions --context='{"operation": "update", ...}'
    python manage.py --execute --context='{"operation": "update", ...}'

Exit codes:
    0   - Success
    1   - Error occurred
"""

import sys
import json
import argparse
import logging
from typing import Any

# Path setup (must be before local imports)
import _paths  # noqa: F401

from shared.utils import safe_json_load  # noqa: E402
from operations import deps  # noqa: E402
from operations import extensions  # noqa: E402
from operations import scaffold  # noqa: E402
from operations import update  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def is_scaffold_operation(context: dict[str, Any]) -> bool:
    """Determine if this is a scaffold operation.

    Args:
        context: Operation context

    Returns:
        True if the operation is scaffold
    """
    return context.get("operation") == "scaffold"


def is_update_operation(context: dict[str, Any]) -> bool:
    """Determine if this is an update operation.

    Args:
        context: Operation context

    Returns:
        True if the operation is update
    """
    return context.get("operation") == "update"


def is_deps_operation(context: dict[str, Any]) -> bool:
    """Determine if this is a deps operation (#20).

    Args:
        context: Operation context

    Returns:
        True if the operation is deps
    """
    return context.get("operation") == "deps"


def get_questions(
    context: dict[str, Any],
) -> dict[str, Any]:
    """Route to appropriate get_questions based on context.

    Args:
        context: Operation context

    Returns:
        Questions result dictionary
    """
    if is_scaffold_operation(context):
        return scaffold.get_questions(context)

    if is_update_operation(context):
        return update.get_questions(context)

    if is_deps_operation(context):
        return deps.get_questions(context)

    # Force type to plugin for extension operations
    context["type"] = "plugin"
    return extensions.get_questions(context)


def execute(
    context: dict[str, Any],
    responses: dict[str, Any],
) -> dict[str, Any]:
    """Route to appropriate execute based on context.

    Args:
        context: Operation context
        responses: User responses

    Returns:
        Execution result dictionary
    """
    if is_scaffold_operation(context):
        # Scaffold uses single-dict context (no separate responses)
        if responses:
            context.update(responses)
        return scaffold.execute(context)

    if is_update_operation(context):
        return update.execute(context, responses)

    if is_deps_operation(context):
        return deps.execute(context, responses)

    # Force type to plugin for extension operations
    context["type"] = "plugin"
    return extensions.execute(
        context, responses, _paths.EXTENSION_TEMPLATES_DIR
    )


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Plugin Manager - Unified Two-Phase API"
    )

    parser.add_argument(
        "--get-questions",
        action="store_true",
        help=(
            "Phase 1: Analyze context and return questions "
            "(outputs JSON)"
        ),
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Phase 2: Execute operation with provided "
            "context/responses (outputs JSON)"
        ),
    )

    parser.add_argument(
        "--context",
        type=str,
        help="JSON string containing operation context",
    )

    parser.add_argument(
        "--responses",
        type=str,
        help="JSON string containing user responses for Phase 2",
    )

    args = parser.parse_args()

    try:
        if args.get_questions:
            context = (
                safe_json_load(args.context) if args.context else {}
            )
            result = get_questions(context)
            print(json.dumps(result, indent=2))
            return 0

        elif args.execute:
            context = (
                safe_json_load(args.context) if args.context else {}
            )
            responses = (
                safe_json_load(args.responses)
                if args.responses
                else {}
            )

            result = execute(context, responses)
            print(json.dumps(result, indent=2))

            return 0 if result.get("success", False) else 1

        else:
            parser.print_help()
            return 1

    except ValueError as e:
        logger.error("Validation error: %s", e)
        print(
            json.dumps(
                {
                    "success": False,
                    "message": f"Validation error: {e}",
                }
            )
        )
        return 1

    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        print(
            json.dumps(
                {
                    "success": False,
                    "message": f"Error: {e}",
                    "error_type": type(e).__name__,
                }
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
