# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for plugin dependency parsing + checking (#20)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_project_root = Path(__file__).parent.parent.parent
sys.path.insert(
    0, str(_project_root / "skills" / "aida" / "scripts")
)

from utils.dependencies import (  # noqa: E402
    check_dependencies,
    parse_version_spec,
    version_satisfies,
)


class TestParseVersionSpec(unittest.TestCase):
    """parse_version_spec extracts the operator + version."""

    def test_bare_version_is_exact(self):
        self.assertEqual(
            parse_version_spec("1.2.3"), ("==", "1.2.3")
        )

    def test_explicit_equal(self):
        self.assertEqual(
            parse_version_spec("==1.2.3"), ("==", "1.2.3")
        )

    def test_gte(self):
        self.assertEqual(
            parse_version_spec(">=1.2.3"), (">=", "1.2.3")
        )

    def test_caret(self):
        self.assertEqual(
            parse_version_spec("^1.2.3"), ("^", "1.2.3")
        )

    def test_tilde(self):
        self.assertEqual(
            parse_version_spec("~1.2.3"), ("~", "1.2.3")
        )

    def test_leading_whitespace_tolerated(self):
        self.assertEqual(
            parse_version_spec("  >=1.2.3  "), (">=", "1.2.3")
        )

    def test_partial_versions_accepted(self):
        """1, 1.2, and 1.2.3 all parse — `_parse_version` pads."""
        for v in ("1", "1.2", "1.2.3"):
            op, version = parse_version_spec(v)
            self.assertEqual(op, "==")
            self.assertEqual(version, v)

    def test_garbage_raises(self):
        for bad in ("", "  ", "1.x.x", "v1.2.3", "1.2.3-rc1", "foo"):
            with self.assertRaises(ValueError):
                parse_version_spec(bad)

    def test_non_string_raises(self):
        for bad in (None, 1.2, [], {}):
            with self.assertRaises(ValueError):
                parse_version_spec(bad)


class TestVersionSatisfies(unittest.TestCase):
    """version_satisfies checks a version against a spec."""

    def test_exact_match(self):
        self.assertTrue(version_satisfies("1.2.3", "1.2.3"))
        self.assertTrue(version_satisfies("1.2.3", "==1.2.3"))
        self.assertFalse(version_satisfies("1.2.4", "1.2.3"))

    def test_gte(self):
        self.assertTrue(version_satisfies("1.2.3", ">=1.2.3"))
        self.assertTrue(version_satisfies("2.0.0", ">=1.2.3"))
        self.assertFalse(version_satisfies("1.2.2", ">=1.2.3"))

    def test_gt(self):
        self.assertFalse(version_satisfies("1.2.3", ">1.2.3"))
        self.assertTrue(version_satisfies("1.2.4", ">1.2.3"))

    def test_lt_and_lte(self):
        self.assertTrue(version_satisfies("1.0.0", "<1.2.3"))
        self.assertFalse(version_satisfies("1.2.3", "<1.2.3"))
        self.assertTrue(version_satisfies("1.2.3", "<=1.2.3"))
        self.assertTrue(version_satisfies("1.2.2", "<=1.2.3"))
        self.assertFalse(version_satisfies("1.2.4", "<=1.2.3"))

    def test_caret_allows_same_major(self):
        """^1.2.3 ≡ >=1.2.3, <2.0.0."""
        self.assertTrue(version_satisfies("1.2.3", "^1.2.3"))
        self.assertTrue(version_satisfies("1.5.0", "^1.2.3"))
        self.assertTrue(version_satisfies("1.99.99", "^1.2.3"))
        self.assertFalse(version_satisfies("2.0.0", "^1.2.3"))
        self.assertFalse(version_satisfies("1.2.2", "^1.2.3"))
        self.assertFalse(version_satisfies("0.9.9", "^1.2.3"))

    def test_tilde_allows_same_minor(self):
        """~1.2.3 ≡ >=1.2.3, <1.3.0."""
        self.assertTrue(version_satisfies("1.2.3", "~1.2.3"))
        self.assertTrue(version_satisfies("1.2.99", "~1.2.3"))
        self.assertFalse(version_satisfies("1.3.0", "~1.2.3"))
        self.assertFalse(version_satisfies("1.2.2", "~1.2.3"))

    def test_malformed_returns_false_not_raise(self):
        """Dep checking is best-effort; we want False on garbage,
        not a crash."""
        self.assertFalse(version_satisfies("1.2.3", "garbage"))
        self.assertFalse(version_satisfies("not-a-version", "^1.2.3"))
        self.assertFalse(version_satisfies("1.2.3", ""))


class TestCheckDependencies(unittest.TestCase):
    """check_dependencies resolves a declared map against installed."""

    def test_all_satisfied(self):
        installed = [
            {"name": "aida-team-essentials", "version": "0.8.0"},
            {"name": "aida-data", "version": "1.0.0"},
        ]
        declared = {
            "aida-team-essentials": ">=0.8.0",
            "aida-data": "^1.0.0",
        }
        result = check_dependencies(declared, installed)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(r["status"] == "satisfied" for r in result))

    def test_missing_dependency(self):
        installed = [{"name": "aida-other", "version": "1.0.0"}]
        declared = {"aida-team-essentials": ">=0.8.0"}
        result = check_dependencies(declared, installed)
        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0],
            {
                "name": "aida-team-essentials",
                "required": ">=0.8.0",
                "installed": None,
                "status": "missing",
            },
        )

    def test_wrong_version(self):
        installed = [
            {"name": "aida-team-essentials", "version": "0.7.0"},
        ]
        declared = {"aida-team-essentials": ">=0.8.0"}
        result = check_dependencies(declared, installed)
        self.assertEqual(result[0]["status"], "wrong-version")
        self.assertEqual(result[0]["installed"], "0.7.0")
        self.assertEqual(result[0]["required"], ">=0.8.0")

    def test_mixed_statuses(self):
        """One satisfied, one missing, one wrong-version."""
        installed = [
            {"name": "ok-plugin", "version": "1.0.0"},
            {"name": "old-plugin", "version": "0.5.0"},
        ]
        declared = {
            "ok-plugin": ">=1.0.0",
            "missing-plugin": "^1.0.0",
            "old-plugin": ">=1.0.0",
        }
        result = check_dependencies(declared, installed)
        by_name = {r["name"]: r for r in result}
        self.assertEqual(by_name["ok-plugin"]["status"], "satisfied")
        self.assertEqual(by_name["missing-plugin"]["status"], "missing")
        self.assertEqual(
            by_name["old-plugin"]["status"], "wrong-version"
        )

    def test_results_are_sorted_by_name(self):
        """Deterministic output makes diffs / reports stable."""
        installed = []
        declared = {"z-plugin": "1.0.0", "a-plugin": "1.0.0"}
        result = check_dependencies(declared, installed)
        names = [r["name"] for r in result]
        self.assertEqual(names, sorted(names))

    def test_empty_declared_returns_empty(self):
        self.assertEqual(check_dependencies({}, []), [])

    def test_installed_without_name_ignored(self):
        """A malformed installed entry (no `name`) doesn't crash."""
        installed = [
            {"version": "1.0.0"},  # missing name
            {"name": "real", "version": "1.0.0"},
        ]
        declared = {"real": "1.0.0"}
        result = check_dependencies(declared, installed)
        self.assertEqual(result[0]["status"], "satisfied")


if __name__ == "__main__":
    unittest.main()
