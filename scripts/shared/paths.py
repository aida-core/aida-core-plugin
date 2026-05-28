# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Registered AIDA path constants.

Single source of truth for filesystem locations AIDA uses. Consumers
import from here rather than building paths by string concatenation, so
the layout can move without hunting through call sites.

INVARIANT: this module imports only the stdlib. No imports from
``bootstrap.py`` or any other ``shared/`` module — that would create
circular initialization risk as the module graph grows.
"""

from pathlib import Path

AIDA_DIR = Path.home() / ".aida"
VENV_DIR = AIDA_DIR / "venv"
STAMP_FILE = AIDA_DIR / ".venv-stamp"

CACHE_DIR = AIDA_DIR / "cache"
KNOWLEDGE_SYNC_CACHE_DIR = CACHE_DIR / "knowledge-sync"
