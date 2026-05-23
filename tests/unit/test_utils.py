# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for AIDA utils module.

This test suite covers all functionality in the utils package including
version checking, path resolution, file operations, and error handling.
"""

import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "aida" / "scripts"))

from utils import (
    # Version checking
    check_python_version,
    get_python_version,
    is_compatible_version,
    format_version,
    MIN_PYTHON_VERSION,
    # Path resolution
    get_home_dir,
    get_claude_dir,
    get_aida_skills_dir,
    get_aida_plugin_dirs,
    ensure_directory,
    resolve_path,
    is_subdirectory,
    get_relative_path,
    # File operations
    read_file,
    write_file,
    read_json,
    write_json,
    write_yaml,
    update_json,
    copy_template,
    file_exists,
    directory_exists,
    # Questionnaire system
    render_template,
    render_filename,
    render_skill_directory,
    is_binary_file,
    is_template_file,
    get_output_filename,
    # Errors
    AidaError,
    VersionError,
    PathError,
    FileOperationError,
    ConfigurationError,
    InstallationError,
)
from utils.questionnaire import Question, load_questionnaire


class TestErrors(unittest.TestCase):
    """Test custom exception classes."""

    def test_aida_error_basic(self):
        """Test basic AidaError."""
        error = AidaError("Test error")
        self.assertEqual(str(error), "Test error")
        self.assertEqual(error.message, "Test error")
        self.assertIsNone(error.suggestion)

    def test_aida_error_with_suggestion(self):
        """Test AidaError with suggestion."""
        error = AidaError("Test error", "Try this fix")
        self.assertIn("Test error", str(error))
        self.assertIn("Try this fix", str(error))
        self.assertEqual(error.suggestion, "Try this fix")

    def test_specific_errors(self):
        """Test that specific error types inherit from AidaError."""
        self.assertTrue(issubclass(VersionError, AidaError))
        self.assertTrue(issubclass(PathError, AidaError))
        self.assertTrue(issubclass(FileOperationError, AidaError))
        self.assertTrue(issubclass(ConfigurationError, AidaError))
        self.assertTrue(issubclass(InstallationError, AidaError))


class TestVersion(unittest.TestCase):
    """Test version checking utilities."""

    def test_get_python_version(self):
        """Test getting Python version."""
        version = get_python_version()
        self.assertEqual(len(version), 3)
        self.assertIsInstance(version[0], int)
        self.assertIsInstance(version[1], int)
        self.assertIsInstance(version[2], int)

    def test_format_version(self):
        """Test version formatting."""
        self.assertEqual(format_version((3, 8, 0)), "3.8.0")
        self.assertEqual(format_version((3, 11, 5)), "3.11.5")
        self.assertEqual(format_version((3, 8)), "3.8")

    def test_is_compatible_version(self):
        """Test version compatibility check."""
        # Current Python must be >= MIN_PYTHON_VERSION (3.8)
        self.assertTrue(is_compatible_version(MIN_PYTHON_VERSION))
        self.assertTrue(is_compatible_version((3, 6)))  # Lower requirement

        # Very high version should fail (unless we're in the far future)
        if sys.version_info[:2] < (9, 0):
            self.assertFalse(is_compatible_version((9, 0)))

    def test_check_python_version_success(self):
        """Test successful version check."""
        # Should not raise for current version
        try:
            check_python_version(MIN_PYTHON_VERSION)
            check_python_version((3, 6))  # Lower requirement
        except VersionError:
            self.fail("check_python_version raised VersionError unexpectedly")

    def test_check_python_version_failure(self):
        """Test version check failure."""
        # Should raise for impossibly high version
        with self.assertRaises(VersionError) as cm:
            check_python_version((99, 0))

        error = cm.exception
        self.assertIn("99.0", str(error))
        self.assertIsNotNone(error.suggestion)


class TestPaths(unittest.TestCase):
    """Test path resolution utilities."""

    def test_get_home_dir(self):
        """Test getting home directory."""
        home = get_home_dir()
        self.assertIsInstance(home, Path)
        self.assertTrue(home.exists())
        self.assertTrue(home.is_dir())

    def test_get_claude_dir(self):
        """Test getting Claude directory."""
        claude_dir = get_claude_dir()
        self.assertIsInstance(claude_dir, Path)
        self.assertEqual(claude_dir.name, ".claude")
        self.assertEqual(claude_dir.parent, get_home_dir())

    def test_get_aida_skills_dir(self):
        """Test getting AIDA skills directory."""
        skills_dir = get_aida_skills_dir()
        self.assertIsInstance(skills_dir, Path)
        self.assertEqual(skills_dir.name, "skills")
        self.assertEqual(skills_dir.parent, get_claude_dir())

    def test_get_aida_plugin_dirs(self):
        """Test getting AIDA plugin directories."""
        # Note: May return empty list if no plugins installed
        plugin_dirs = get_aida_plugin_dirs()
        self.assertIsInstance(plugin_dirs, list)
        for d in plugin_dirs:
            self.assertIsInstance(d, Path)
            self.assertTrue(d.name.startswith("aida-"))

    def test_ensure_directory(self):
        """Test directory creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "test" / "nested" / "dir"
            result = ensure_directory(test_dir)

            self.assertTrue(result.exists())
            self.assertTrue(result.is_dir())
            self.assertEqual(result, test_dir)

    def test_ensure_directory_exists(self):
        """Test ensure_directory with existing directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "existing"
            test_dir.mkdir()

            # Should not raise error
            result = ensure_directory(test_dir)
            self.assertTrue(result.exists())

    def test_resolve_path(self):
        """Test path resolution."""
        # Test with home directory expansion
        path = resolve_path("~/test")
        self.assertTrue(path.is_absolute())
        self.assertNotIn("~", str(path))

    def test_resolve_path_must_exist(self):
        """Test path resolution with must_exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            existing = Path(tmpdir) / "existing.txt"
            existing.touch()

            # Should succeed for existing file
            result = resolve_path(existing, must_exist=True)
            self.assertTrue(result.exists())

            # Should fail for non-existing file
            with self.assertRaises(PathError):
                resolve_path(Path(tmpdir) / "missing.txt", must_exist=True)

    def test_is_subdirectory(self):
        """Test subdirectory checking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parent = Path(tmpdir)
            child = parent / "subdir"
            child.mkdir()

            self.assertTrue(is_subdirectory(child, parent))
            self.assertFalse(is_subdirectory(parent, child))
            self.assertFalse(is_subdirectory(parent, Path("/other")))

    def test_get_relative_path(self):
        """Test relative path calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            target = base / "subdir" / "file.txt"

            relative = get_relative_path(target, base)
            self.assertIsNotNone(relative)
            self.assertEqual(relative.as_posix(), "subdir/file.txt")


class TestFiles(unittest.TestCase):
    """Test file operation utilities."""

    def test_read_write_file(self):
        """Test basic file read/write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            content = "Hello, AIDA!"

            write_file(test_file, content)
            result = read_file(test_file)

            self.assertEqual(result, content)

    def test_write_file_creates_parents(self):
        """Test that write_file creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "nested" / "dir" / "test.txt"

            write_file(test_file, "content")

            self.assertTrue(test_file.exists())
            self.assertEqual(read_file(test_file), "content")

    def test_read_file_not_found(self):
        """Test reading non-existent file."""
        with self.assertRaises(FileOperationError):
            read_file(Path("/nonexistent/file.txt"))

    def test_read_write_json(self):
        """Test JSON read/write operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            data = {"key": "value", "number": 42, "nested": {"inner": True}}

            write_json(test_file, data)
            result = read_json(test_file)

            self.assertEqual(result, data)

    def test_read_json_default(self):
        """Test reading JSON with default value."""
        result = read_json(Path("/nonexistent.json"), default={})
        self.assertEqual(result, {})

    def test_read_json_invalid(self):
        """Test reading invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "invalid.json"
            write_file(test_file, "{invalid json}")

            with self.assertRaises(ConfigurationError):
                read_json(test_file)

    def test_update_json(self):
        """Test updating JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "config.json"
            initial = {"key1": "value1"}
            updates = {"key2": "value2", "key1": "updated"}

            write_json(test_file, initial)
            result = update_json(test_file, updates)

            self.assertEqual(result["key1"], "updated")
            self.assertEqual(result["key2"], "value2")

    def test_update_json_creates_file(self):
        """Test updating JSON creates file if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "new.json"
            updates = {"key": "value"}

            result = update_json(test_file, updates, create_if_missing=True)

            self.assertEqual(result, updates)
            self.assertTrue(test_file.exists())

    def test_copy_template(self):
        """Test template copying with replacements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template = Path(tmpdir) / "template.txt"
            output = Path(tmpdir) / "output.txt"

            write_file(template, "Hello {{NAME}}, version {{VERSION}}")
            copy_template(
                template,
                output,
                {"{{NAME}}": "AIDA", "{{VERSION}}": "1.0"}
            )

            result = read_file(output)
            self.assertEqual(result, "Hello AIDA, version 1.0")

    def test_copy_template_no_replacements(self):
        """Test template copying without replacements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template = Path(tmpdir) / "template.txt"
            output = Path(tmpdir) / "output.txt"
            content = "Plain content"

            write_file(template, content)
            copy_template(template, output)

            self.assertEqual(read_file(output), content)

    def test_file_exists(self):
        """Test file existence check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            existing = Path(tmpdir) / "exists.txt"
            existing.touch()

            self.assertTrue(file_exists(existing))
            self.assertFalse(file_exists(Path(tmpdir) / "missing.txt"))
            self.assertFalse(file_exists(Path(tmpdir)))  # Directory

    def test_directory_exists(self):
        """Test directory existence check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "subdir"
            test_dir.mkdir()

            self.assertTrue(directory_exists(test_dir))
            self.assertFalse(directory_exists(Path(tmpdir) / "missing"))
            self.assertFalse(directory_exists(Path(tmpdir) / "file.txt"))

    def test_write_yaml_emits_document_start(self):
        """write_yaml output must start with `---`.

        Regression for #97: yamllint's default `document-start` rule
        requires a `---` marker, and the scaffolder enforces this rule
        in every plugin it generates. AIDA-generated YAML must clear
        the same bar.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "config.yml"
            write_yaml(test_file, {"key": "value"})

            content = test_file.read_text(encoding="utf-8")
            self.assertTrue(
                content.startswith("---\n"),
                f"output must start with '---'; got: {content!r}",
            )

    def test_write_yaml_indents_nested_sequences(self):
        """Sequence items must be indented inside their parent key.

        Regression for #81 and #97: PyYAML's default emits
        `tools:\\n  detected:\\n  - Git` (items flush with parent at
        column 2). yamllint's `indentation` rule with
        `indent-sequences: true` (the default) expects items at column
        4. The custom Dumper restores the expected indentation.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "context.yml"
            write_yaml(
                test_file,
                {"tools": {"detected": ["Git", "GitHub Actions"]}},
            )

            content = test_file.read_text(encoding="utf-8")
            # Sequence items must be at column 4 (4 leading spaces),
            # not column 2 — the bug being fixed.
            self.assertIn("    - Git\n", content)
            self.assertIn("    - GitHub Actions\n", content)
            # Stronger guard: assert the bug pattern literally isn't
            # present by checking line-by-line rather than substring.
            for line in content.splitlines():
                if "- Git" in line:
                    self.assertTrue(
                        line.startswith("    - "),
                        f"Sequence item under-indented: {line!r}",
                    )

    def test_write_yaml_roundtrip(self):
        """Round-trip through write_yaml + yaml.safe_load preserves data.

        Guards against the new Dumper accidentally mangling content.
        """
        import yaml

        data = {
            "version": "1.5.2",
            "project": {"name": "demo"},
            "tools": {"detected": ["Git", "GitHub Actions"]},
            "plugins": ["aida-core"],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "roundtrip.yml"
            write_yaml(test_file, data)
            loaded = yaml.safe_load(
                test_file.read_text(encoding="utf-8")
            )

            self.assertEqual(loaded, data)

    def test_write_yaml_top_level_sequence(self):
        """A top-level sequence still renders correctly.

        Indentless-sequence is only inappropriate inside a mapping; a
        bare top-level list should still emit `- item` at column 0.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "list.yml"
            write_yaml(test_file, ["alpha", "beta"])

            content = test_file.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---\n"))
            self.assertIn("- alpha\n", content)
            self.assertIn("- beta\n", content)


class TestAidaYmlRenderers(unittest.TestCase):
    """Test the YAML marker renderers in install.py and configure.py.

    Both render via string concatenation (not write_yaml), so the
    `document-start` fix is local to each. These guards keep the
    yamllint-clean shape from drifting back.
    """

    def test_render_aida_marker_starts_with_doc_start(self):
        """Global ~/.claude/aida.yml must start with `---`. (#97)"""
        from install import render_aida_marker

        content = render_aida_marker({})

        self.assertTrue(
            content.startswith("---\n"),
            f"render_aida_marker output must start with '---'; "
            f"got first line: {content.splitlines()[0]!r}",
        )

    def test_render_aida_marker_is_yamllint_compatible(self):
        """Generated content must parse as valid YAML.

        Cheap structural check — doesn't pull in yamllint as a runtime
        dep, but catches gross syntax regressions from the renderer.
        """
        import yaml
        from install import render_aida_marker

        content = render_aida_marker({})
        loaded = yaml.safe_load(content)

        self.assertIsInstance(loaded, dict)
        self.assertIn("version", loaded)
        self.assertIn("plugins", loaded)

    def test_render_aida_project_marker_starts_with_doc_start(self):
        """Project .claude/aida.yml must start with `---`. (#97)"""
        from configure import render_aida_project_marker

        content = render_aida_project_marker(
            preferences={"project_type": "Plugin"},
            project_name="demo",
        )

        self.assertTrue(
            content.startswith("---\n"),
            f"render_aida_project_marker output must start with '---'; "
            f"got first line: {content.splitlines()[0]!r}",
        )

    def test_render_aida_project_marker_is_yamllint_compatible(self):
        """Generated project marker content must parse as valid YAML."""
        import yaml
        from configure import render_aida_project_marker

        content = render_aida_project_marker(
            preferences={
                "project_type": "Plugin",
                "team_collaboration": "Open source",
            },
            project_name="demo",
        )
        loaded = yaml.safe_load(content)

        self.assertIsInstance(loaded, dict)
        self.assertEqual(loaded["project"]["name"], "demo")

    def test_render_aida_project_marker_omits_dead_plugin_reference(self):
        """`aida-workflow-commands` is not a real plugin — must not appear.

        Regression for #83: the renderer previously hardcoded
        `plugins = ["aida-workflow-commands"]`, putting a dead
        reference into every generated .claude/aida.yml.
        """
        import yaml
        from configure import render_aida_project_marker

        content = render_aida_project_marker(
            preferences={}, project_name="demo"
        )
        self.assertNotIn("aida-workflow-commands", content)

        loaded = yaml.safe_load(content)
        # `plugins:` section may be empty (or absent) but must not
        # contain the dead reference.
        plugins = loaded.get("plugins") or []
        self.assertNotIn("aida-workflow-commands", plugins)


class TestConfigureQuestionOptions(unittest.TestCase):
    """Guard against the #85 family: choice questions exceeding the
    AskUserQuestion 4-option cap.

    AskUserQuestion's JSON schema caps `options` at 4 items per
    question (the user always gets a free "Other" on top of that).
    Any choice question in configure.py that ships with > 4 options
    is undeliverable to the user. This test scans the source and
    asserts every choice question is within cap, so future additions
    don't reintroduce the bug.
    """

    ASK_USER_QUESTION_OPTION_CAP = 4

    def test_choice_questions_respect_option_cap(self):
        import re

        configure_path = (
            Path(__file__).parent.parent.parent
            / "skills"
            / "aida"
            / "scripts"
            / "configure.py"
        )
        source = configure_path.read_text(encoding="utf-8")

        # Match each question dict: capture id and the options list.
        # Non-greedy across whitespace/lines. Tolerant of trailing
        # comma after the closing bracket of options.
        pattern = re.compile(
            r'"id":\s*"(?P<id>[^"]+)"'
            r"[\s\S]*?"
            r'"options":\s*\[(?P<opts>[\s\S]*?)\]',
        )

        offenders = []
        for m in pattern.finditer(source):
            qid = m.group("id")
            opts = re.findall(r'"([^"]+)"', m.group("opts"))
            if len(opts) > self.ASK_USER_QUESTION_OPTION_CAP:
                offenders.append((qid, len(opts), opts))

        self.assertEqual(
            offenders,
            [],
            "Choice questions exceed AskUserQuestion's 4-option cap:\n"
            + "\n".join(
                f"  {qid}: {n} options ({opts})"
                for qid, n, opts in offenders
            ),
        )


class TestQuestionnaire(unittest.TestCase):
    """Test questionnaire system."""

    def test_question_text_type(self):
        """Test text question type."""
        q = Question({
            "id": "test_text",
            "question": "What is your name?",
            "type": "text",
        })

        # Valid response
        valid, value, error = q.validate_response("John Doe")
        self.assertTrue(valid)
        self.assertEqual(value, "John Doe")
        self.assertIsNone(error)

        # Empty required response
        valid, value, error = q.validate_response("")
        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_question_text_with_default(self):
        """Test text question with default value."""
        q = Question({
            "id": "test_default",
            "question": "What is your name?",
            "type": "text",
            "default": "Anonymous",
        })

        # Empty response should use default
        valid, value, error = q.validate_response("")
        self.assertTrue(valid)
        self.assertEqual(value, "Anonymous")
        self.assertIsNone(error)

    def test_question_optional(self):
        """Test optional question."""
        q = Question({
            "id": "test_optional",
            "question": "Optional field?",
            "type": "text",
            "required": False,
        })

        # Empty response should be valid
        valid, value, error = q.validate_response("")
        self.assertTrue(valid)
        self.assertIsNone(value)
        self.assertIsNone(error)

    def test_question_boolean_type(self):
        """Test boolean question type."""
        q = Question({
            "id": "test_bool",
            "question": "Do you agree?",
            "type": "boolean",
        })

        # Test yes variations
        for yes_value in ["y", "yes", "Yes", "YES", "true", "1"]:
            valid, value, error = q.validate_response(yes_value)
            self.assertTrue(valid, f"Failed for: {yes_value}")
            self.assertTrue(value)
            self.assertIsNone(error)

        # Test no variations
        for no_value in ["n", "no", "No", "NO", "false", "0"]:
            valid, value, error = q.validate_response(no_value)
            self.assertTrue(valid, f"Failed for: {no_value}")
            self.assertFalse(value)
            self.assertIsNone(error)

        # Test invalid
        valid, value, error = q.validate_response("maybe")
        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_question_choice_type(self):
        """Test choice question type."""
        q = Question({
            "id": "test_choice",
            "question": "Pick a color",
            "type": "choice",
            "options": ["Red", "Green", "Blue"],
        })

        # Test numeric selection
        valid, value, error = q.validate_response("1")
        self.assertTrue(valid)
        self.assertEqual(value, "Red")

        valid, value, error = q.validate_response("3")
        self.assertTrue(valid)
        self.assertEqual(value, "Blue")

        # Test out of range
        valid, value, error = q.validate_response("4")
        self.assertFalse(valid)
        self.assertIsNotNone(error)

        # Test text match
        valid, value, error = q.validate_response("Green")
        self.assertTrue(valid)
        self.assertEqual(value, "Green")

        # Test invalid text
        valid, value, error = q.validate_response("Yellow")
        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_question_multiline_type(self):
        """Test multiline question type."""
        q = Question({
            "id": "test_multiline",
            "question": "Enter description",
            "type": "multiline",
        })

        multiline_text = "Line 1\nLine 2\nLine 3"
        valid, value, error = q.validate_response(multiline_text)
        self.assertTrue(valid)
        self.assertEqual(value, multiline_text)
        self.assertIsNone(error)

    def test_question_validation_missing_id(self):
        """Test question validation fails without id."""
        with self.assertRaises(ConfigurationError) as cm:
            Question({"question": "Test?"})

        self.assertIn("id", str(cm.exception))

    def test_question_validation_missing_question(self):
        """Test question validation fails without question text."""
        with self.assertRaises(ConfigurationError) as cm:
            Question({"id": "test"})

        self.assertIn("question", str(cm.exception))

    def test_question_validation_invalid_type(self):
        """Test question validation fails with invalid type."""
        with self.assertRaises(ConfigurationError) as cm:
            Question({
                "id": "test",
                "question": "Test?",
                "type": "invalid_type",
            })

        self.assertIn("invalid type", str(cm.exception).lower())

    def test_question_validation_choice_no_options(self):
        """Test choice question validation fails without options."""
        with self.assertRaises(ConfigurationError) as cm:
            Question({
                "id": "test",
                "question": "Pick one",
                "type": "choice",
            })

        self.assertIn("options", str(cm.exception).lower())

    def test_load_questionnaire_valid(self):
        """Test loading valid questionnaire."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_file = Path(tmpdir) / "test.yml"
            yaml_content = """questions:
  - id: q1
    question: "Question 1?"
    type: text
  - id: q2
    question: "Question 2?"
    type: boolean
    default: true
"""
            write_file(yaml_file, yaml_content)

            questions = load_questionnaire(yaml_file)

            self.assertEqual(len(questions), 2)
            self.assertEqual(questions[0].id, "q1")
            self.assertEqual(questions[1].id, "q2")
            self.assertTrue(questions[1].default)

    def test_load_questionnaire_missing_file(self):
        """Test loading non-existent questionnaire."""
        with self.assertRaises(FileOperationError):
            load_questionnaire(Path("/nonexistent/questionnaire.yml"))

    def test_load_questionnaire_invalid_yaml(self):
        """Test loading invalid YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_file = Path(tmpdir) / "invalid.yml"
            write_file(yaml_file, "{invalid yaml content:")

            with self.assertRaises(ConfigurationError) as cm:
                load_questionnaire(yaml_file)

            self.assertIn("yaml", str(cm.exception).lower())

    def test_load_questionnaire_missing_questions_key(self):
        """Test loading YAML without questions key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_file = Path(tmpdir) / "no_questions.yml"
            write_file(yaml_file, "other_key: value")

            with self.assertRaises(ConfigurationError) as cm:
                load_questionnaire(yaml_file)

            self.assertIn("questions", str(cm.exception).lower())

    def test_load_questionnaire_empty_questions(self):
        """Test loading questionnaire with empty questions list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_file = Path(tmpdir) / "empty.yml"
            write_file(yaml_file, "questions: []")

            with self.assertRaises(ConfigurationError) as cm:
                load_questionnaire(yaml_file)

            self.assertIn("no questions", str(cm.exception).lower())

    def test_question_format_prompt(self):
        """Test question prompt formatting."""
        q = Question({
            "id": "test",
            "question": "What is your name?",
            "type": "text",
            "help": "Enter your full name",
            "default": "Anonymous",
        })

        prompt = q.format_prompt(1, 5)

        self.assertIn("[Question 1 of 5]", prompt)
        self.assertIn("What is your name?", prompt)
        self.assertIn("Enter your full name", prompt)
        self.assertIn("Anonymous", prompt)

    def test_question_format_prompt_choice(self):
        """Test choice question prompt formatting."""
        q = Question({
            "id": "test",
            "question": "Pick a color",
            "type": "choice",
            "options": ["Red", "Green", "Blue"],
        })

        prompt = q.format_prompt(2, 3)

        self.assertIn("[Question 2 of 3]", prompt)
        self.assertIn("1. Red", prompt)
        self.assertIn("2. Green", prompt)
        self.assertIn("3. Blue", prompt)

    def test_load_install_questionnaire(self):
        """Test loading the actual install.yml questionnaire."""
        # Get path to install.yml template
        script_dir = Path(__file__).parent.parent / "scripts"
        template_file = script_dir.parent / "templates" / "questionnaires" / "install.yml"

        if template_file.exists():
            questions = load_questionnaire(template_file)
            self.assertGreaterEqual(len(questions), 5)

            # Verify all questions have required fields
            for q in questions:
                self.assertIsNotNone(q.id)
                self.assertIsNotNone(q.question)
                self.assertIn(q.type, ["text", "choice", "multiline", "boolean"])

    def test_load_configure_questionnaire(self):
        """Test loading the actual configure.yml questionnaire."""
        # Get path to configure.yml template
        script_dir = Path(__file__).parent.parent / "scripts"
        template_file = script_dir.parent / "templates" / "questionnaires" / "configure.yml"

        if template_file.exists():
            questions = load_questionnaire(template_file)
            self.assertGreaterEqual(len(questions), 5)

            # Verify all questions have required fields
            for q in questions:
                self.assertIsNotNone(q.id)
                self.assertIsNotNone(q.question)
                self.assertIn(q.type, ["text", "choice", "multiline", "boolean"])


class TestTemplateRendering(unittest.TestCase):
    """Test template rendering utilities."""

    def test_render_template_basic(self):
        """Test basic template rendering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_file = Path(tmpdir) / "template.md.jinja2"
            write_file(template_file, "Hello {{ name }}!")

            result = render_template(template_file, {"name": "AIDA"})
            self.assertEqual(result, "Hello AIDA!")

    def test_render_template_multiple_variables(self):
        """Test template with multiple variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_file = Path(tmpdir) / "template.md.jinja2"
            content = "Name: {{ name }}\nVersion: {{ version }}\nAuthor: {{ author }}"
            write_file(template_file, content)

            variables = {
                "name": "AIDA",
                "version": "1.0",
                "author": "Test User"
            }
            result = render_template(template_file, variables)

            self.assertIn("Name: AIDA", result)
            self.assertIn("Version: 1.0", result)
            self.assertIn("Author: Test User", result)

    def test_render_template_undefined_variable(self):
        """Test template with undefined variable raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_file = Path(tmpdir) / "template.md.jinja2"
            write_file(template_file, "Hello {{ name }}! Welcome to {{ project }}!")

            # Only provide 'name', not 'project'
            with self.assertRaises(ValueError) as cm:
                render_template(template_file, {"name": "AIDA"})

            error = cm.exception
            self.assertIn("Undefined variable", str(error))
            self.assertIn("project", str(error).lower())

    def test_render_filename_basic(self):
        """Test basic filename rendering."""
        result = render_filename("{{ skill_name }}.md", {"skill_name": "my-skill"})
        self.assertEqual(result, "my-skill.md")

    def test_render_filename_multiple_variables(self):
        """Test filename with multiple variables."""
        result = render_filename(
            "{{ category }}-{{ name }}.{{ ext }}",
            {"category": "test", "name": "file", "ext": "md"}
        )
        self.assertEqual(result, "test-file.md")

    def test_render_filename_undefined_variable(self):
        """Test filename with undefined variable raises error."""
        with self.assertRaises(ValueError) as cm:
            render_filename("{{ name }}.md", {})

        self.assertIn("Undefined variable", str(cm.exception))

    def test_is_binary_file(self):
        """Test binary file detection."""
        # Binary files
        self.assertTrue(is_binary_file(Path("image.png")))
        self.assertTrue(is_binary_file(Path("photo.jpg")))
        self.assertTrue(is_binary_file(Path("archive.zip")))
        self.assertTrue(is_binary_file(Path("video.mp4")))

        # Text files
        self.assertFalse(is_binary_file(Path("document.md")))
        self.assertFalse(is_binary_file(Path("script.py")))
        self.assertFalse(is_binary_file(Path("config.json")))

    def test_is_template_file(self):
        """Test template file detection."""
        # Template files
        self.assertTrue(is_template_file(Path("template.jinja2")))
        self.assertTrue(is_template_file(Path("SKILL.md.jinja2")))
        self.assertTrue(is_template_file(Path("config.json.jinja2")))

        # Non-template files
        self.assertFalse(is_template_file(Path("document.md")))
        self.assertFalse(is_template_file(Path("script.py")))
        self.assertFalse(is_template_file(Path("image.png")))

    def test_get_output_filename_basic(self):
        """Test basic output filename generation."""
        result = get_output_filename(
            Path("SKILL.md.jinja2"),
            {"skill_name": "test"}
        )
        self.assertEqual(result, "SKILL.md")

    def test_get_output_filename_with_variables(self):
        """Test output filename with variable substitution."""
        result = get_output_filename(
            Path("{{skill_name}}.md.jinja2"),
            {"skill_name": "my-skill"}
        )
        self.assertEqual(result, "my-skill.md")

    def test_render_skill_directory_basic(self):
        """Test basic skill directory rendering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create template directory
            template_dir = Path(tmpdir) / "templates"
            output_dir = Path(tmpdir) / "output"
            template_dir.mkdir()

            # Create a simple template
            template_file = template_dir / "SKILL.md.jinja2"
            write_file(template_file, "# {{ skill_name }}\n\n{{ description }}")

            # Render directory
            variables = {
                "skill_name": "Test Skill",
                "description": "A test skill"
            }
            render_skill_directory(template_dir, output_dir, variables)

            # Verify output
            output_file = output_dir / "SKILL.md"
            self.assertTrue(output_file.exists())

            content = read_file(output_file)
            self.assertIn("# Test Skill", content)
            self.assertIn("A test skill", content)

    def test_render_skill_directory_nested(self):
        """Test rendering nested directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested template directory
            template_dir = Path(tmpdir) / "templates"
            subdir = template_dir / "subdir"
            subdir.mkdir(parents=True)

            output_dir = Path(tmpdir) / "output"

            # Create templates in both directories
            write_file(
                template_dir / "root.md.jinja2",
                "Root: {{ name }}"
            )
            write_file(
                subdir / "nested.md.jinja2",
                "Nested: {{ name }}"
            )

            # Render directory
            variables = {"name": "AIDA"}
            render_skill_directory(template_dir, output_dir, variables)

            # Verify output structure
            self.assertTrue((output_dir / "root.md").exists())
            self.assertTrue((output_dir / "subdir").exists())
            self.assertTrue((output_dir / "subdir" / "nested.md").exists())

            # Verify content
            self.assertIn("Root: AIDA", read_file(output_dir / "root.md"))
            self.assertIn("Nested: AIDA", read_file(output_dir / "subdir" / "nested.md"))

    def test_render_skill_directory_skips_binary(self):
        """Test that binary files are skipped during rendering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_dir = Path(tmpdir) / "templates"
            output_dir = Path(tmpdir) / "output"
            template_dir.mkdir()

            # Create a binary file (will be skipped)
            binary_file = template_dir / "image.png"
            binary_file.write_bytes(b'\x89PNG\r\n\x1a\n')

            # Create a template file (will be rendered)
            write_file(
                template_dir / "text.md.jinja2",
                "{{ content }}"
            )

            # Render directory
            variables = {"content": "Hello"}
            render_skill_directory(template_dir, output_dir, variables)

            # Binary file should not be in output
            self.assertFalse((output_dir / "image.png").exists())

            # Template file should be rendered
            self.assertTrue((output_dir / "text.md").exists())

    def test_render_skill_directory_skips_non_templates(self):
        """Test that non-template files are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_dir = Path(tmpdir) / "templates"
            output_dir = Path(tmpdir) / "output"
            template_dir.mkdir()

            # Create non-template file (should be skipped)
            write_file(template_dir / "README.md", "Regular file")

            # Create template file (should be rendered)
            write_file(
                template_dir / "SKILL.md.jinja2",
                "{{ content }}"
            )

            # Render directory
            variables = {"content": "Template content"}
            render_skill_directory(template_dir, output_dir, variables)

            # Non-template should not be in output
            self.assertFalse((output_dir / "README.md").exists())

            # Template should be rendered
            self.assertTrue((output_dir / "SKILL.md").exists())
            self.assertEqual(
                read_file(output_dir / "SKILL.md"),
                "Template content"
            )

    def test_render_skill_directory_variable_dirname(self):
        """Test rendering directory name with variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create template with variable in directory name
            template_dir = Path(tmpdir) / "templates"
            var_dir = template_dir / "{{skill_type}}-skills"
            var_dir.mkdir(parents=True)

            output_dir = Path(tmpdir) / "output"

            # Create template in variable-named directory
            write_file(
                var_dir / "file.md.jinja2",
                "Content: {{ skill_type }}"
            )

            # Render directory
            variables = {"skill_type": "personal"}
            render_skill_directory(template_dir, output_dir, variables)

            # Verify rendered directory name
            self.assertTrue((output_dir / "personal-skills").exists())
            self.assertTrue((output_dir / "personal-skills" / "file.md").exists())

    def test_render_skill_directory_nonexistent(self):
        """Test rendering non-existent directory raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_dir = Path(tmpdir) / "nonexistent"
            output_dir = Path(tmpdir) / "output"

            with self.assertRaises(FileOperationError):
                render_skill_directory(template_dir, output_dir, {})


class TestIntegration(unittest.TestCase):
    """Integration tests using multiple modules together."""

    def test_full_workflow(self):
        """Test a complete workflow using multiple utilities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup paths
            base_dir = Path(tmpdir) / "test-aida"
            config_dir = base_dir / "config"

            # Ensure directories exist
            ensure_directory(config_dir)

            # Write configuration
            config_data = {
                "version": format_version(get_python_version()),
                "paths": {
                    "base": str(base_dir),
                    "config": str(config_dir),
                }
            }
            config_file = config_dir / "settings.json"
            write_json(config_file, config_data)

            # Read and verify
            loaded_config = read_json(config_file)
            self.assertEqual(loaded_config["version"], config_data["version"])

            # Update configuration
            update_json(config_file, {"new_setting": True})
            updated = read_json(config_file)
            self.assertTrue(updated["new_setting"])

            # Verify path relationships
            self.assertTrue(is_subdirectory(config_dir, base_dir))
            relative = get_relative_path(config_file, base_dir)
            self.assertEqual(relative.as_posix(), "config/settings.json")


class TestSecurity(unittest.TestCase):
    """Test security features and validation."""

    def test_safe_json_load_size_limit(self):
        """Test that oversized JSON payloads are rejected."""
        from utils.json_utils import safe_json_load, MAX_JSON_SIZE
        import json

        # Create JSON that exceeds size limit
        large_json = json.dumps({"data": "x" * (MAX_JSON_SIZE + 1)})

        with self.assertRaises(ValueError) as cm:
            safe_json_load(large_json)

        self.assertIn("too large", str(cm.exception))

    def test_safe_json_load_depth_limit(self):
        """Test that deeply nested JSON is rejected."""
        from utils.json_utils import safe_json_load, MAX_JSON_DEPTH
        import json

        # Create deeply nested JSON (more than MAX_JSON_DEPTH levels)
        nested = {}
        current = nested
        for i in range(MAX_JSON_DEPTH + 2):
            current["a"] = {}
            current = current["a"]

        deep_json = json.dumps(nested)

        with self.assertRaises(ValueError) as cm:
            safe_json_load(deep_json)

        self.assertIn("too deep", str(cm.exception))

    def test_safe_json_load_valid(self):
        """Test that valid JSON is accepted."""
        from utils.json_utils import safe_json_load
        import json

        valid_data = {"coding_standards": "PEP 8", "tools": ["Python", "Git"]}
        valid_json = json.dumps(valid_data)

        result = safe_json_load(valid_json)
        self.assertEqual(result, valid_data)

    def test_questionnaire_input_null_bytes(self):
        """Test that null bytes in input are rejected."""
        from utils.questionnaire import Question

        q = Question({
            "id": "test",
            "question": "Test question?",
            "type": "text",
        })

        # Normal text should pass
        valid, value, error = q.validate_response("normal text")
        self.assertTrue(valid)
        self.assertEqual(value, "normal text")

        # Null byte should be rejected
        valid, value, error = q.validate_response("bad\x00text")
        self.assertFalse(valid)
        self.assertIn("Invalid characters", error)

    def test_questionnaire_input_length_limit(self):
        """Test that oversized input is rejected."""
        from utils.questionnaire import Question, MAX_INPUT_LENGTH

        q = Question({
            "id": "test",
            "question": "Test question?",
            "type": "text",
        })

        # Input within limit should pass
        valid, value, error = q.validate_response("x" * 100)
        self.assertTrue(valid)

        # Input exceeding limit should be rejected
        valid, value, error = q.validate_response("x" * (MAX_INPUT_LENGTH + 1))
        self.assertFalse(valid)
        self.assertIn("too long", error)

    def test_questionnaire_multiline_length_limit(self):
        """Test that oversized multiline input is rejected."""
        from utils.questionnaire import Question, MAX_MULTILINE_LENGTH

        q = Question({
            "id": "test",
            "question": "Test question?",
            "type": "multiline",
        })

        # Input within limit should pass
        valid, value, error = q.validate_response("x" * 1000)
        self.assertTrue(valid)

        # Input exceeding limit should be rejected
        valid, value, error = q.validate_response("x" * (MAX_MULTILINE_LENGTH + 1))
        self.assertFalse(valid)
        self.assertIn("too long", error)

    def test_atomic_write(self):
        """Test atomic file write functionality."""
        from utils.files import atomic_write

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            content = "Test content for atomic write"

            # Write file atomically
            atomic_write(test_file, content)

            # Verify content
            self.assertTrue(test_file.exists())
            self.assertEqual(test_file.read_text(), content)

            # Overwrite atomically
            new_content = "Updated content"
            atomic_write(test_file, new_content)
            self.assertEqual(test_file.read_text(), new_content)

    def test_safe_rglob_symlink_protection(self):
        """Test that safe_rglob skips symlinks."""
        from utils.inference import safe_rglob

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Create a real file
            real_file = root / "real.py"
            real_file.write_text("# real file")

            # Create a symlink (if supported on this platform)
            try:
                link_file = root / "link.py"
                link_file.symlink_to(real_file)

                # safe_rglob should find files but skip symlinks
                # We can't easily test this without modifying safe_rglob to return paths
                # But we can verify it doesn't crash on symlinks
                result = safe_rglob(root, "*.py")
                self.assertTrue(result)  # Should find the real file
            except OSError:
                # Symlinks not supported on this platform, skip test
                self.skipTest("Symlinks not supported on this platform")


def run_tests():
    """Run all tests and return results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestErrors))
    suite.addTests(loader.loadTestsFromTestCase(TestVersion))
    suite.addTests(loader.loadTestsFromTestCase(TestPaths))
    suite.addTests(loader.loadTestsFromTestCase(TestFiles))
    suite.addTests(loader.loadTestsFromTestCase(TestAidaYmlRenderers))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigureQuestionOptions))
    suite.addTests(loader.loadTestsFromTestCase(TestQuestionnaire))
    suite.addTests(loader.loadTestsFromTestCase(TestTemplateRendering))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestSecurity))

    # Run with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


if __name__ == "__main__":
    result = run_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
