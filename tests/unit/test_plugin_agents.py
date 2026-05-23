# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for the `/aida plugin agents` operation (#20)."""

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

# Cross-skill cache hygiene
sys.modules.pop("_paths", None)
for _name in list(sys.modules):
    if _name == "operations" or _name.startswith("operations."):
        del sys.modules[_name]

from operations import agents as _agents  # noqa: E402

_ops_snapshot = {
    k: v for k, v in sys.modules.items()
    if k == "operations" or k.startswith("operations.")
}


def _write_agent(
    agents_dir: Path,
    name: str,
    *,
    description: str = "Test agent",
    version: str = "0.1.0",
    tags: list | None = None,
) -> Path:
    """Write a minimal agent file at agents/<name>/<name>.md."""
    agent_dir = agents_dir / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    fm_lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
        f"version: {version}",
    ]
    if tags is not None:
        fm_lines.append("tags:")
        for tag in tags:
            fm_lines.append(f"  - {tag}")
    fm_lines.append("---")
    fm_lines.append("")
    fm_lines.append(f"# {name}")
    md = agent_dir / f"{name}.md"
    md.write_text("\n".join(fm_lines) + "\n", encoding="utf-8")
    return md


def _write_plugin_with_agent(
    cache_root: Path,
    plugin_name: str,
    agent_name: str,
    *,
    plugin_version: str = "0.1.0",
) -> Path:
    """Create a fake installed plugin with one agent."""
    plugin_root = cache_root / "org" / plugin_name
    cfg_dir = plugin_root / ".claude-plugin"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "plugin.json").write_text(
        json.dumps(
            {"name": plugin_name, "version": plugin_version}
        ),
        encoding="utf-8",
    )
    _write_agent(plugin_root / "agents", agent_name)
    return plugin_root


class TestDiscoverAllAgents(unittest.TestCase):
    """_discover_all_agents walks project + user + plugin sources."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.project = Path(self.tmp) / "proj"
        self.project.mkdir()
        self.fake_home = Path(self.tmp) / "home"
        self.fake_home.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _discover(self):
        with patch.object(Path, "home", return_value=self.fake_home):
            return _agents._discover_all_agents(self.project)

    def test_empty_returns_empty_list(self):
        self.assertEqual(self._discover(), [])

    def test_project_agents_discovered(self):
        _write_agent(self.project / ".claude" / "agents", "scribe")
        result = self._discover()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "scribe")
        self.assertEqual(result[0]["source"], "project")

    def test_user_agents_discovered(self):
        _write_agent(
            self.fake_home / ".claude" / "agents", "personal-ed"
        )
        result = self._discover()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "personal-ed")
        self.assertEqual(result[0]["source"], "user")

    def test_plugin_agents_discovered_with_plugin_name(self):
        cache = self.fake_home / ".claude" / "plugins" / "cache"
        _write_plugin_with_agent(
            cache, "aida-team-essentials", "tech-lead"
        )
        result = self._discover()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "tech-lead")
        self.assertEqual(result[0]["source"], "plugin")
        self.assertIn(
            "aida-team-essentials", result[0]["source_label"]
        )

    def test_all_sources_collected_no_dedup(self):
        """Distinct from utils.discover_agents (which dedupes —
        first-found wins). This view preserves duplicates so the
        caller can flag collisions.
        """
        _write_agent(
            self.project / ".claude" / "agents", "scribe"
        )
        _write_agent(
            self.fake_home / ".claude" / "agents", "scribe"
        )
        cache = self.fake_home / ".claude" / "plugins" / "cache"
        _write_plugin_with_agent(cache, "plug-a", "scribe")
        _write_plugin_with_agent(cache, "plug-b", "scribe")

        result = self._discover()
        names = [a["name"] for a in result]
        self.assertEqual(names.count("scribe"), 4)

    def test_malformed_frontmatter_falls_back_to_filename(self):
        agent_dir = (
            self.project / ".claude" / "agents" / "broken"
        )
        agent_dir.mkdir(parents=True)
        # Frontmatter delimiters but invalid YAML inside
        (agent_dir / "broken.md").write_text(
            "---\n[not valid yaml:\n---\n# body\n",
            encoding="utf-8",
        )
        result = self._discover()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "broken")

    def test_knowledge_dir_files_skipped(self):
        """`agents/<name>/knowledge/*.md` files aren't agents."""
        agents_dir = self.project / ".claude" / "agents"
        _write_agent(agents_dir, "expert")
        knowledge = agents_dir / "expert" / "knowledge"
        knowledge.mkdir()
        (knowledge / "intro.md").write_text(
            "# knowledge intro\n", encoding="utf-8"
        )
        result = self._discover()
        names = [a["name"] for a in result]
        self.assertEqual(names, ["expert"])


class TestDetectCollisions(unittest.TestCase):
    """_detect_collisions groups duplicates by name."""

    def test_no_duplicates(self):
        agents = [
            {"name": "a", "source": "project", "source_label": "x"},
            {"name": "b", "source": "user", "source_label": "y"},
        ]
        self.assertEqual(_agents._detect_collisions(agents), [])

    def test_cross_source_collision_flagged(self):
        agents = [
            {
                "name": "code-reviewer",
                "source": "plugin",
                "source_label": "plugin: pkg-a",
            },
            {
                "name": "code-reviewer",
                "source": "plugin",
                "source_label": "plugin: pkg-b",
            },
        ]
        result = _agents._detect_collisions(agents)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "code-reviewer")
        self.assertEqual(result[0]["count"], 2)
        self.assertEqual(
            sorted(result[0]["sources"]),
            ["plugin: pkg-a", "plugin: pkg-b"],
        )

    def test_result_sorted_by_name(self):
        agents = [
            {"name": "z", "source_label": "a"},
            {"name": "z", "source_label": "b"},
            {"name": "a", "source_label": "c"},
            {"name": "a", "source_label": "d"},
        ]
        result = _agents._detect_collisions(agents)
        self.assertEqual([r["name"] for r in result], ["a", "z"])


class TestExecuteAgentsOperation(unittest.TestCase):
    """`agents.execute` returns a structured report + success flag."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.project = Path(self.tmp) / "proj"
        self.project.mkdir()
        self.fake_home = Path(self.tmp) / "home"
        self.fake_home.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _execute(self, **ctx_overrides):
        ctx = {"project_root": str(self.project)}
        ctx.update(ctx_overrides)
        with patch.object(Path, "home", return_value=self.fake_home):
            return _agents.execute(ctx)

    def test_empty_succeeds(self):
        result = self._execute()
        self.assertTrue(result["success"])
        self.assertEqual(result["summary"]["total"], 0)
        self.assertIn("No agents discovered", result["message"])

    def test_no_collisions_succeeds(self):
        _write_agent(
            self.project / ".claude" / "agents", "scribe"
        )
        cache = self.fake_home / ".claude" / "plugins" / "cache"
        _write_plugin_with_agent(cache, "pkg-a", "tech-lead")
        result = self._execute()
        self.assertTrue(result["success"])
        self.assertEqual(result["summary"]["total"], 2)
        self.assertEqual(result["summary"]["collisions"], 0)
        self.assertIn("no collisions", result["message"])

    def test_collision_fails(self):
        cache = self.fake_home / ".claude" / "plugins" / "cache"
        _write_plugin_with_agent(cache, "pkg-a", "code-reviewer")
        _write_plugin_with_agent(cache, "pkg-b", "code-reviewer")
        result = self._execute()
        self.assertFalse(result["success"])
        self.assertEqual(result["summary"]["collisions"], 1)
        self.assertEqual(len(result["collisions"]), 1)
        self.assertEqual(
            result["collisions"][0]["name"], "code-reviewer"
        )
        self.assertIn("name collision", result["message"])

    def test_summary_breaks_down_by_source(self):
        _write_agent(
            self.project / ".claude" / "agents", "proj-a"
        )
        _write_agent(
            self.fake_home / ".claude" / "agents", "user-a"
        )
        cache = self.fake_home / ".claude" / "plugins" / "cache"
        _write_plugin_with_agent(cache, "pkg-a", "plug-a")
        result = self._execute()
        self.assertEqual(
            result["summary"]["by_source"],
            {"project": 1, "user": 1, "plugin": 1},
        )


class TestGetQuestions(unittest.TestCase):
    """`agents.get_questions` returns the registry up-front."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.project = Path(self.tmp) / "proj"
        self.project.mkdir()
        self.fake_home = Path(self.tmp) / "home"
        self.fake_home.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_phase_marker_and_no_questions(self):
        with patch.object(Path, "home", return_value=self.fake_home):
            result = _agents.get_questions(
                {"project_root": str(self.project)}
            )
        self.assertEqual(result["questions"], [])
        self.assertEqual(result["phase"], "get_questions")
        self.assertEqual(
            result["inferred"]["agent_count"], 0
        )
        self.assertEqual(
            result["inferred"]["collision_count"], 0
        )


if __name__ == "__main__":
    unittest.main()
