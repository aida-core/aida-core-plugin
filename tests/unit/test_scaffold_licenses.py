# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""Unit tests for plugin-manager license operations."""

import sys
import unittest
from pathlib import Path

# Add scripts directories to path
_project_root = Path(__file__).parent.parent.parent
_plugin_scripts = _project_root / "skills" / "plugin-manager" / "scripts"
sys.path.insert(0, str(_project_root / "scripts"))
sys.path.insert(0, str(_plugin_scripts))

# Clear cached operations modules to avoid cross-manager conflicts in pytest
for _mod_name in list(sys.modules):
    if _mod_name == "operations" or _mod_name.startswith("operations."):
        del sys.modules[_mod_name]
sys.modules.pop("_paths", None)

from operations.scaffold_ops.licenses import (  # noqa: E402
    get_license_text,
    is_valid_license_id,
    LICENSES,
    PROMPT_LICENSE_OPTIONS,
    SUPPORTED_LICENSES,
)

_ops_snapshot = {
    k: v for k, v in sys.modules.items()
    if k == "operations" or k.startswith("operations.")
}


class TestGetLicenseText(unittest.TestCase):
    """Test license text generation."""

    def test_mit_license(self):
        text = get_license_text("MIT", "2026", "Test Author")
        self.assertIn("MIT License", text)
        self.assertIn("2026", text)
        self.assertIn("Test Author", text)

    def test_apache_license(self):
        text = get_license_text("Apache-2.0", "2026", "Test Author")
        self.assertIn("Apache License", text)
        self.assertIn("2026", text)
        self.assertIn("Test Author", text)

    def test_isc_license(self):
        text = get_license_text("ISC", "2026", "Test Author")
        self.assertIn("ISC License", text)
        self.assertIn("2026", text)
        self.assertIn("Test Author", text)

    def test_gpl_license(self):
        text = get_license_text("GPL-3.0", "2026", "Test Author")
        self.assertIn("GNU GENERAL PUBLIC LICENSE", text)
        self.assertIn("2026", text)
        self.assertIn("Test Author", text)

    def test_agpl_license(self):
        text = get_license_text("AGPL-3.0", "2026", "Test Author")
        self.assertIn("GNU AFFERO GENERAL PUBLIC LICENSE", text)
        self.assertIn("2026", text)
        self.assertIn("Test Author", text)

    def test_unlicensed(self):
        text = get_license_text("UNLICENSED", "2026", "Test Author")
        self.assertIn("All rights reserved", text)
        self.assertIn("2026", text)
        self.assertIn("Test Author", text)

    def test_all_supported_licenses(self):
        """Every supported license should render without error."""
        for license_id in SUPPORTED_LICENSES:
            text = get_license_text(license_id, "2026", "Author")
            self.assertTrue(len(text) > 0, f"License {license_id} produced empty text")
            self.assertIn("2026", text)
            self.assertIn("Author", text)

    def test_year_author_substitution(self):
        """Year and author should be properly substituted."""
        text = get_license_text("MIT", "2099", "Jane Doe")
        self.assertIn("2099", text)
        self.assertIn("Jane Doe", text)
        self.assertNotIn("{year}", text)
        self.assertNotIn("{author_name}", text)

    def test_supported_licenses_list(self):
        """SUPPORTED_LICENSES should match LICENSES dict keys."""
        self.assertEqual(set(SUPPORTED_LICENSES), set(LICENSES.keys()))

    def test_licenses_count(self):
        """Should have exactly 6 fully-bundled licenses."""
        self.assertEqual(len(SUPPORTED_LICENSES), 6)

    def test_prompt_option_cap(self):
        """Interactive prompt options must fit AskUserQuestion's
        4-option cap (#85, #111).
        """
        self.assertLessEqual(len(PROMPT_LICENSE_OPTIONS), 4)
        # Sanity: every prompt option must be either a fully-bundled
        # license or a recognized placeholder.
        for opt in PROMPT_LICENSE_OPTIONS:
            self.assertTrue(
                is_valid_license_id(opt),
                f"PROMPT_LICENSE_OPTIONS contains an invalid id: {opt}",
            )

    def test_format_string_injection_safe(self):
        """Author names with format-like patterns should not cause errors."""
        # This should not raise KeyError or other format-related errors
        text = get_license_text("MIT", "2026", "Author {with} {curly} braces")
        self.assertIn("Author {with} {curly} braces", text)


class TestIsValidLicenseId(unittest.TestCase):
    """Test the loose SPDX-id validator that gates scaffold input."""

    def test_known_license_is_valid(self):
        for lic in ("MIT", "Apache-2.0", "GPL-3.0", "ISC", "AGPL-3.0"):
            self.assertTrue(is_valid_license_id(lic))

    def test_placeholder_is_valid(self):
        # UNLICENSED + friends are valid scaffold input even though
        # they're not real SPDX ids — downstream they suppress the
        # License-Identifier header.
        for lic in ("UNLICENSED", "Proprietary", "PROPRIETARY"):
            self.assertTrue(is_valid_license_id(lic))

    def test_other_spdx_id_is_valid(self):
        # Real SPDX ids we don't bundle text for must still validate.
        for lic in (
            "MPL-2.0",
            "BSD-3-Clause",
            "LGPL-3.0-or-later",
            "GPL-3.0-only",
            "0BSD",
            "Unlicense",
        ):
            self.assertTrue(
                is_valid_license_id(lic),
                f"Real SPDX id {lic!r} should validate",
            )

    def test_empty_or_whitespace_rejected(self):
        for lic in ("", " ", "  ", "\t"):
            self.assertFalse(is_valid_license_id(lic))

    def test_shell_metacharacters_rejected(self):
        # Defense in depth — license_id flows into file content but
        # could end up in a shell context (e.g., next-steps printing).
        for bad in (
            "MIT; rm -rf /",
            "MIT && evil",
            "MIT $(whoami)",
            "MIT`evil`",
            "MIT|pipe",
            "MIT\nnewline",
        ):
            self.assertFalse(
                is_valid_license_id(bad),
                f"Suspicious id should be rejected: {bad!r}",
            )


class TestGetLicenseTextOther(unittest.TestCase):
    """Test the 'Other' SPDX id path — unknown ids get a placeholder
    LICENSE instead of an error (#111).
    """

    def test_unknown_spdx_id_writes_placeholder(self):
        # MPL-2.0 is a real SPDX id but we don't bundle the full text.
        # The scaffold should still succeed and write a placeholder.
        text = get_license_text("MPL-2.0", "2026", "Test Author")
        self.assertIn("MPL-2.0", text)
        self.assertIn("Test Author", text)
        self.assertIn("2026", text)
        # Placeholder should explicitly point at the SPDX license list
        # so authors know how to fill it in.
        self.assertIn("spdx.org/licenses/", text)

    def test_invalid_identifier_still_raises(self):
        # An id that fails is_valid_license_id (whitespace, shell
        # metacharacters) must still raise — defense in depth.
        with self.assertRaises(ValueError):
            get_license_text("MIT; rm -rf /", "2026", "Author")

    def test_unlicensed_placeholder_uses_attribution_text(self):
        """All NON_SPDX_PLACEHOLDERS render as proprietary attribution.
        """
        for placeholder in ("UNLICENSED", "Proprietary", "PROPRIETARY"):
            text = get_license_text(placeholder, "2026", "Author")
            self.assertIn("All rights reserved", text)
            self.assertIn("2026", text)
            self.assertIn("Author", text)


if __name__ == "__main__":
    unittest.main()
