# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""AIDA environment bootstrap.

Ensures Python dependencies are available in an AIDA-managed virtual
environment at ``~/.aida/venv/``.  Call :func:`ensure_aida_environment`
early in any script that needs third-party packages (jinja2, PyYAML,
jsonschema, etc.).

The bootstrap is designed to:
  1. Create the venv lazily on first use.
  2. Install/update dependencies only when ``requirements.txt`` changes.
  3. Inject the venv's ``site-packages`` into ``sys.path`` so the
     calling script does not need to be run under the venv's interpreter.
"""

import hashlib
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

from .paths import AIDA_DIR, STAMP_FILE, VENV_DIR  # noqa: E402

# Re-exports kept for backwards compatibility with existing call sites that
# import these names from `bootstrap`. The canonical definitions live in
# `paths.py`.
__all__ = ["AIDA_DIR", "STAMP_FILE", "VENV_DIR"]

_IS_WINDOWS = platform.system() == "Windows"
_BIN_DIR = "Scripts" if _IS_WINDOWS else "bin"
_PYTHON_NAME = "python.exe" if _IS_WINDOWS else "python3"
_PIP_NAME = "pip.exe" if _IS_WINDOWS else "pip"


def _find_requirements_txt() -> Path:
    """Locate the plugin's ``requirements.txt``.

    Walks up from this file's location to find the project root
    (contains ``.claude-plugin/``), then returns the
    ``requirements.txt`` inside it.
    """
    current = Path(__file__).resolve().parent
    for ancestor in [current] + list(current.parents):
        if (ancestor / ".claude-plugin").is_dir() and (ancestor / "requirements.txt").is_file():
            return ancestor / "requirements.txt"
    raise FileNotFoundError(
        "Could not locate requirements.txt in the AIDA core plugin tree."
    )


def _hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _venv_python() -> Path:
    """Path to the venv's Python interpreter."""
    return VENV_DIR / _BIN_DIR / _PYTHON_NAME


def _venv_pip() -> Path:
    """Path to the venv's pip."""
    return VENV_DIR / _BIN_DIR / _PIP_NAME


def _find_site_packages() -> Optional[Path]:
    """Find the venv's ``site-packages`` directory."""
    if _IS_WINDOWS:
        sp = VENV_DIR / "Lib" / "site-packages"
        if sp.is_dir():
            return sp
    else:
        lib_dir = VENV_DIR / "lib"
        if lib_dir.is_dir():
            matches = sorted(lib_dir.glob("python*/site-packages"))
            if matches:
                return matches[-1]
    return None


def _add_site_packages_to_path() -> None:
    """Insert the venv's ``site-packages`` into ``sys.path``."""
    sp = _find_site_packages()
    if sp and str(sp) not in sys.path:
        sys.path.insert(0, str(sp))


def _create_venv() -> None:
    """Create the AIDA managed virtual environment."""
    AIDA_DIR.mkdir(parents=True, exist_ok=True)

    print("Setting up AIDA environment...", file=sys.stderr)
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(VENV_DIR)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "ensurepip" in stderr or "No module named" in stderr:
            raise RuntimeError(
                "Failed to create virtual environment.\n"
                "The 'venv' module is not available. On Debian/Ubuntu, install it with:\n"
                "  sudo apt install python3-venv"
            )
        raise RuntimeError(
            f"Failed to create virtual environment:\n{stderr}"
        )


def _install_deps(requirements: Path) -> None:
    """Install dependencies from ``requirements.txt`` into the venv."""
    pip = _venv_pip()
    print("Installing AIDA dependencies...", file=sys.stderr)
    result = subprocess.run(
        [str(pip), "install", "-q", "-r", str(requirements)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to install dependencies:\n{result.stderr.strip()}"
        )

    # Write stamp so we skip next time
    req_hash = _hash_file(requirements)
    STAMP_FILE.write_text(req_hash + "\n")


def _deps_up_to_date(requirements: Path) -> bool:
    """Check if installed deps match the current ``requirements.txt``."""
    if not STAMP_FILE.exists():
        return False
    current_hash = _hash_file(requirements)
    stamp_hash = STAMP_FILE.read_text().strip()
    return current_hash == stamp_hash


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ensure_aida_environment() -> None:
    """Ensure the AIDA venv exists with current dependencies.

    Safe to call multiple times -- fast-paths when everything is
    already set up.

    Raises:
        RuntimeError: If venv creation or dependency installation fails.
        FileNotFoundError: If ``requirements.txt`` cannot be located.
    """
    requirements = _find_requirements_txt()

    # Fast path: venv exists and deps are current
    if _venv_python().exists() and _deps_up_to_date(requirements):
        _add_site_packages_to_path()
        return

    # Create venv if missing
    if not _venv_python().exists():
        _create_venv()

    # Install or update deps
    _install_deps(requirements)
    _add_site_packages_to_path()


def is_aida_environment_ready() -> bool:
    """Check if the AIDA environment is set up and current.

    Returns:
        True if the venv exists and dependencies are up to date.
    """
    if not _venv_python().exists():
        return False
    try:
        requirements = _find_requirements_txt()
    except FileNotFoundError:
        return False
    return _deps_up_to_date(requirements)
