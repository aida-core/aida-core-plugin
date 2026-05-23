# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Shared constants for plugin-manager operations."""

GENERATOR_VERSION = "0.9.0"
# "none" is a skills-only / markdown-only flavor — no Python or
# TypeScript toolchain (no pyproject.toml, no package.json, no
# language-specific tests directory). Used for plugins that ship
# pure agents / skills / CLAUDE.md content (#96).
SUPPORTED_LANGUAGES = ("python", "typescript", "none")
