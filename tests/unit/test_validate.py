# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for /aida config validate (#87).

Covers the validator's structured report shape and exit-code
contract — the latter matters because CI gates depend on it.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Add aida scripts to path
_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root / "scripts"))
sys.path.insert(0, str(_project_root / "skills" / "aida" / "scripts"))

# Clear any cached operations modules from prior test files
sys.modules.pop("_paths", None)
for _name in list(sys.modules):
    if _name == "operations" or _name.startswith("operations."):
        del sys.modules[_name]

import validate as _validator  # noqa: E402

_ops_snapshot = {
    k: v for k, v in sys.modules.items()
    if k == "operations" or k.startswith("operations.")
}


def _write_minimal_project_marker(project_root: Path) -> None:
    """Write a minimally-valid .claude/aida.yml for the project."""
    claude_dir = project_root / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "aida.yml").write_text(
        '---\nversion: "1.5.17"\nproject:\n  name: "demo"\n',
        encoding="utf-8",
    )


def _write_minimal_project_context(project_root: Path) -> None:
    """Write a minimally-valid aida-project-context.yml."""
    claude_dir = project_root / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "aida-project-context.yml").write_text(
        "---\n"
        'version: "0.2.0"\n'
        'project_name: "demo"\n'
        "vcs:\n  type: git\n"
        "files:\n  has_readme: true\n"
        "languages:\n  primary: Python\n"
        "tools:\n  detected: []\n"
        "inferred:\n  project_type: Unknown\n"
        "preferences:\n  branching_model: null\n",
        encoding="utf-8",
    )


def _write_minimal_global_marker(home: Path) -> None:
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".claude" / "aida.yml").write_text(
        '---\nversion: "1.5.17"\n', encoding="utf-8"
    )


class TestValidate(unittest.TestCase):
    """Test the validator's structured report."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp) / "proj"
        self.root.mkdir(parents=True)
        self.home = Path(self.tmp) / "home"
        self.home.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_clean_project_validates(self):
        _write_minimal_global_marker(self.home)
        _write_minimal_project_marker(self.root)
        _write_minimal_project_context(self.root)

        report = _validator.validate(self.root, self.home)
        self.assertTrue(
            report["valid"],
            f"Expected valid; got errors: {report['errors']}",
        )
        self.assertEqual(report["errors"], [])
        for name in (
            "global_install",
            "project_marker",
            "project_context",
        ):
            self.assertTrue(report["checks"][name]["pass"])

    def test_missing_global_marker_fails(self):
        # Project marker + context present, global marker absent.
        _write_minimal_project_marker(self.root)
        _write_minimal_project_context(self.root)

        report = _validator.validate(self.root, self.home)
        self.assertFalse(report["valid"])
        self.assertFalse(report["checks"]["global_install"]["pass"])
        self.assertTrue(
            any(
                "Global AIDA marker missing" in e
                for e in report["errors"]
            )
        )

    def test_missing_project_marker_fails(self):
        _write_minimal_global_marker(self.home)
        _write_minimal_project_context(self.root)

        report = _validator.validate(self.root, self.home)
        self.assertFalse(report["valid"])
        self.assertFalse(report["checks"]["project_marker"]["pass"])
        self.assertTrue(
            any(
                "Project marker missing" in e
                for e in report["errors"]
            )
        )

    def test_missing_project_context_fails(self):
        _write_minimal_global_marker(self.home)
        _write_minimal_project_marker(self.root)

        report = _validator.validate(self.root, self.home)
        self.assertFalse(report["valid"])
        self.assertFalse(
            report["checks"]["project_context"]["pass"]
        )
        self.assertTrue(
            any(
                "Project context missing" in e
                for e in report["errors"]
            )
        )

    def test_bad_yaml_in_project_context_surfaces_parse_error(self):
        _write_minimal_global_marker(self.home)
        _write_minimal_project_marker(self.root)
        # Malformed YAML
        (self.root / ".claude").mkdir(parents=True, exist_ok=True)
        (
            self.root / ".claude" / "aida-project-context.yml"
        ).write_text(":\n: not: valid: yaml\n", encoding="utf-8")

        report = _validator.validate(self.root, self.home)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any(
                "fails YAML parse" in e
                for e in report["errors"]
            )
        )

    def test_missing_expected_keys_flagged(self):
        """A project context that loads but lacks expected
        top-level keys flags them by name."""
        _write_minimal_global_marker(self.home)
        _write_minimal_project_marker(self.root)
        (self.root / ".claude").mkdir(parents=True, exist_ok=True)
        # Just version + project_name; missing vcs/files/etc.
        (
            self.root / ".claude" / "aida-project-context.yml"
        ).write_text(
            "---\nversion: '0.2.0'\nproject_name: 'demo'\n",
            encoding="utf-8",
        )

        report = _validator.validate(self.root, self.home)
        self.assertFalse(report["valid"])
        joined = " ".join(report["errors"])
        for required in (
            "vcs",
            "files",
            "languages",
            "tools",
            "inferred",
            "preferences",
        ):
            self.assertIn(required, joined)

    def test_wrong_section_type_flagged(self):
        """vcs / files / preferences must be mappings, not strings."""
        _write_minimal_global_marker(self.home)
        _write_minimal_project_marker(self.root)
        (self.root / ".claude").mkdir(parents=True, exist_ok=True)
        (
            self.root / ".claude" / "aida-project-context.yml"
        ).write_text(
            "---\n"
            "version: '0.2.0'\n"
            "project_name: 'demo'\n"
            "vcs: 'this should be a mapping'\n"
            "files: {}\n"
            "languages: {}\n"
            "tools: {}\n"
            "inferred: {}\n"
            "preferences: {}\n",
            encoding="utf-8",
        )
        report = _validator.validate(self.root, self.home)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any(
                "vcs section must be a mapping" in e
                for e in report["errors"]
            )
        )


if __name__ == "__main__":
    unittest.main()
