# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for the `/aida plugin deps` operation (#20)."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root / "scripts"))
sys.path.insert(
    0, str(_project_root / "skills" / "plugin-manager" / "scripts")
)

# Cross-skill cache hygiene (matches other plugin-manager tests).
sys.modules.pop("_paths", None)
for _name in list(sys.modules):
    if _name == "operations" or _name.startswith("operations."):
        del sys.modules[_name]

from operations import deps as _deps  # noqa: E402

_ops_snapshot = {
    k: v for k, v in sys.modules.items()
    if k == "operations" or k.startswith("operations.")
}


def _write_aida_config(
    plugin_dir: Path, dependencies: dict | None = None
) -> None:
    """Write a minimal aida-config.json with optional deps."""
    cfg_dir = plugin_dir / ".claude-plugin"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    payload: dict = {"config": {}, "recommendedPermissions": {}}
    if dependencies is not None:
        payload["dependencies"] = dependencies
    (cfg_dir / "aida-config.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _write_plugin_manifest(
    plugin_dir: Path, name: str, version: str
) -> None:
    """Write a minimal plugin.json so the inline scanner picks it up."""
    cfg_dir = plugin_dir / ".claude-plugin"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "plugin.json").write_text(
        json.dumps({"name": name, "version": version}),
        encoding="utf-8",
    )


class TestReadDeclaredDependencies(unittest.TestCase):
    """deps._read_declared_dependencies tolerates missing / malformed
    inputs."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.plugin = Path(self.tmp) / "plugin"
        self.plugin.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_config_returns_empty(self):
        self.assertEqual(
            _deps._read_declared_dependencies(self.plugin), {}
        )

    def test_no_dependencies_field_returns_empty(self):
        _write_aida_config(self.plugin)  # no deps key
        self.assertEqual(
            _deps._read_declared_dependencies(self.plugin), {}
        )

    def test_reads_string_keyed_string_valued_deps(self):
        _write_aida_config(
            self.plugin,
            dependencies={
                "aida-team-essentials": ">=0.8.0",
                "aida-data": "^1.0.0",
            },
        )
        result = _deps._read_declared_dependencies(self.plugin)
        self.assertEqual(
            result,
            {
                "aida-team-essentials": ">=0.8.0",
                "aida-data": "^1.0.0",
            },
        )

    def test_filters_non_string_value(self):
        """Hand-edits with non-string values (numbers, lists) get
        filtered. (Non-string *keys* are impossible in JSON — they
        round-trip as strings — so we only need to defend against
        non-string values.)
        """
        _write_aida_config(
            self.plugin,
            dependencies={
                "ok": ">=1.0.0",
                "bad_spec": 1.0,
                "also_bad": ["1.0.0"],
            },
        )
        result = _deps._read_declared_dependencies(self.plugin)
        self.assertEqual(result, {"ok": ">=1.0.0"})

    def test_malformed_json_returns_empty(self):
        cfg = self.plugin / ".claude-plugin"
        cfg.mkdir()
        (cfg / "aida-config.json").write_text(
            "{not valid json", encoding="utf-8"
        )
        self.assertEqual(
            _deps._read_declared_dependencies(self.plugin), {}
        )

    def test_dependencies_not_dict_returns_empty(self):
        _write_aida_config(
            self.plugin, dependencies=["not", "a", "dict"]
        )
        self.assertEqual(
            _deps._read_declared_dependencies(self.plugin), {}
        )


class TestExecuteDepsOperation(unittest.TestCase):
    """deps.execute returns a structured report."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.plugin = Path(self.tmp) / "myplugin"
        self.plugin.mkdir()

        # Simulate two "installed" plugins via a fake cache root.
        cache = Path(self.tmp) / "claude_home"
        for name, version in [
            ("aida-team-essentials", "0.8.0"),
            ("aida-data", "1.0.5"),
        ]:
            d = cache / ".claude" / "plugins" / "cache" / "org" / name
            d.mkdir(parents=True)
            _write_plugin_manifest(d, name, version)
        self.fake_home = cache

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _execute_with_fake_home(self, context):
        with patch.object(Path, "home", return_value=self.fake_home):
            return _deps.execute(context)

    def test_no_declared_deps_succeeds(self):
        """A plugin without a dependencies field is trivially OK."""
        _write_aida_config(self.plugin)
        result = self._execute_with_fake_home(
            {"plugin_path": str(self.plugin)}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["summary"]["total"], 0)
        self.assertIn("No dependencies declared", result["message"])

    def test_all_satisfied(self):
        _write_aida_config(
            self.plugin,
            dependencies={
                "aida-team-essentials": ">=0.8.0",
                "aida-data": "^1.0.0",
            },
        )
        result = self._execute_with_fake_home(
            {"plugin_path": str(self.plugin)}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["summary"]["satisfied"], 2)
        self.assertEqual(result["summary"]["missing"], 0)
        self.assertEqual(result["summary"]["wrong_version"], 0)
        self.assertIn("All 2 dependencies satisfied", result["message"])

    def test_missing_dependency_fails(self):
        _write_aida_config(
            self.plugin,
            dependencies={
                "aida-team-essentials": ">=0.8.0",
                "aida-nope": ">=1.0.0",
            },
        )
        result = self._execute_with_fake_home(
            {"plugin_path": str(self.plugin)}
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["summary"]["missing"], 1)
        self.assertEqual(result["summary"]["satisfied"], 1)
        # Sorted output makes test stable regardless of dict iter order.
        statuses = {r["name"]: r["status"] for r in result["results"]}
        self.assertEqual(statuses["aida-nope"], "missing")
        self.assertEqual(
            statuses["aida-team-essentials"], "satisfied"
        )

    def test_wrong_version_fails(self):
        _write_aida_config(
            self.plugin,
            dependencies={"aida-team-essentials": ">=1.0.0"},
        )
        result = self._execute_with_fake_home(
            {"plugin_path": str(self.plugin)}
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["summary"]["wrong_version"], 1)
        self.assertEqual(
            result["results"][0]["installed"], "0.8.0"
        )
        self.assertEqual(
            result["results"][0]["status"], "wrong-version"
        )


class TestGetQuestions(unittest.TestCase):
    """deps.get_questions returns no questions and the report up-front."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.plugin = Path(self.tmp) / "myplugin"
        self.plugin.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_phase_marker_and_empty_questions(self):
        _write_aida_config(self.plugin)
        result = _deps.get_questions(
            {"plugin_path": str(self.plugin)}
        )
        self.assertEqual(result["questions"], [])
        self.assertEqual(result["phase"], "get_questions")
        self.assertIn("results", result["inferred"])
        self.assertEqual(result["inferred"]["declared_count"], 0)


if __name__ == "__main__":
    unittest.main()
