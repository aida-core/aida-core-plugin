#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 The AIDA Core Authors
# SPDX-License-Identifier: MPL-2.0

"""AIDA Doctor Script

Run comprehensive health check and diagnostics.

Usage:
    python doctor.py

Exit codes:
    0 - All healthy
    1 - Issues found
"""

import os
import sys
import subprocess
from pathlib import Path

import _paths  # noqa: F401
from shared.bootstrap import VENV_DIR, STAMP_FILE, is_aida_environment_ready

def check_python_version():
    """Check if Python 3.8+ is installed."""
    version = sys.version_info
    print("Checking Python version...")
    if version >= (3, 8):
        print(f"✓ Python version: {version.major}.{version.minor}.{version.micro} (>= 3.8 required)")
        return True
    else:
        print(f"✗ Python version: {version.major}.{version.minor}.{version.micro}")
        print("  → Install Python 3.8+ from https://www.python.org/downloads/")
        return False

def check_directory(path, name, should_exist=True):
    """Check if directory exists and is writable."""
    print(f"Checking {name}...")
    if path.exists():
        if path.is_dir():
            # Check if writable
            test_file = path / ".test_write"
            try:
                test_file.touch()
                test_file.unlink()
                print(f"✓ {name}: {path} (exists, writable)")
                return True
            except (OSError, PermissionError):
                print(f"✗ {name}: {path} (exists, not writable)")
                print(f"  → Fix permissions: chmod u+w {path}")
                return False
        else:
            print(f"✗ {name}: {path} (exists but not a directory)")
            return False
    else:
        if should_exist:
            print(f"✗ {name}: {path} (not found)")
            print("  → Run /aida config to create")
            return False
        else:
            print(f"• {name}: Not configured (optional)")
            return True

def check_git():
    """Check if Git is installed."""
    print("Checking Git...")
    try:
        result = subprocess.run(['git', '--version'],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✓ {version}")
            return True
        else:
            print("✗ Git: not working")
            return False
    except FileNotFoundError:
        print("✗ Git: not found")
        print("  → Install: https://git-scm.com/downloads")
        return False
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        print(f"✗ Git: error checking ({e})")
        return False

def check_github_cli():
    """Check if GitHub CLI (gh) is installed."""
    print("Checking GitHub CLI...")
    try:
        result = subprocess.run(['gh', '--version'],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version = result.stdout.strip().split('\n')[0]
            print(f"✓ {version}")

            # Check if authenticated
            auth_result = subprocess.run(['gh', 'auth', 'status'],
                                         capture_output=True, text=True, timeout=5)
            if auth_result.returncode == 0:
                print("✓ GitHub CLI: authenticated")
            else:
                print("⚠ GitHub CLI: not authenticated")
                print("  → Run: gh auth login")
            return True
        else:
            print("✗ GitHub CLI: not working")
            return False
    except FileNotFoundError:
        print("⚠ GitHub CLI: not found (optional for feedback)")
        print("  → Install: brew install gh (macOS)")
        return True  # Not required, just warning
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        print(f"⚠ GitHub CLI: error checking ({e})")
        return True  # Not required

def check_aida_venv():
    """Check if the AIDA managed virtual environment is healthy."""
    print("Checking AIDA virtual environment...")

    if not VENV_DIR.exists():
        print("• AIDA venv: not created yet (will be created on first use)")
        return True  # Not an error, lazy init

    # Check venv Python interpreter
    bin_dir = VENV_DIR / "bin"
    venv_python = bin_dir / "python3"
    if not venv_python.exists():
        print("✗ AIDA venv: corrupted (missing python3 interpreter)")
        print(f"  → Remove and let AIDA recreate: rm -rf {VENV_DIR}")
        return False

    # Check pip
    venv_pip = bin_dir / "pip"
    if not venv_pip.exists():
        print("✗ AIDA venv: corrupted (missing pip)")
        print(f"  → Remove and let AIDA recreate: rm -rf {VENV_DIR}")
        return False

    # Check if deps are up to date
    if is_aida_environment_ready():
        print(f"✓ AIDA venv: {VENV_DIR} (healthy, deps up to date)")
    else:
        if STAMP_FILE.exists():
            print("⚠ AIDA venv: exists but dependencies are outdated")
            print("  → Dependencies will update automatically on next script run")
        else:
            print("⚠ AIDA venv: exists but no stamp file")
            print("  → Dependencies will install automatically on next script run")

    # Check installed packages
    try:
        result = subprocess.run(
            [str(venv_pip), "list", "--format=columns"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            installed = result.stdout
            required = [
                "jinja2",
                "pyyaml",
                "jsonschema",
                # knowledge-sync HTTP fetcher (#143)
                "requests",
                "beautifulsoup4",
                "markdownify",
            ]
            for pkg in required:
                if pkg.lower() in installed.lower():
                    print(f"  ✓ {pkg}: installed")
                else:
                    print(f"  ✗ {pkg}: missing")
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        print("  ⚠ Could not verify installed packages")

    # knowledge-sync cache directory health
    from shared.paths import KNOWLEDGE_SYNC_CACHE_DIR

    if KNOWLEDGE_SYNC_CACHE_DIR.exists():
        if os.access(KNOWLEDGE_SYNC_CACHE_DIR, os.W_OK):
            print(
                f"✓ Knowledge-sync cache: {KNOWLEDGE_SYNC_CACHE_DIR} "
                "(writable)"
            )
        else:
            print(
                f"⚠ Knowledge-sync cache: {KNOWLEDGE_SYNC_CACHE_DIR} "
                "exists but is not writable"
            )
    else:
        # Not an error — created lazily on first HTTP source fetch.
        print(
            f"  ℹ Knowledge-sync cache will be created at "
            f"{KNOWLEDGE_SYNC_CACHE_DIR} on first HTTP source sync"
        )

    return True


def validate_yaml_file(path, name):
    """Validate a YAML file."""
    if not path.exists():
        return True  # Not an error if doesn't exist yet

    try:
        import yaml
        with open(path, 'r') as f:
            yaml.safe_load(f)
        return True
    except (FileNotFoundError, PermissionError):
        return False
    except yaml.YAMLError as e:
        print(f"✗ {name}: Invalid YAML - {e}")
        return False

def validate_config_files():
    """Validate configuration files."""
    print("Checking configuration files...")

    all_valid = True

    # Global config
    global_config = Path.home() / ".claude" / "config" / "settings.yaml"
    if global_config.exists():
        if validate_yaml_file(global_config, "Global config"):
            print("✓ Global config: valid YAML")
        else:
            all_valid = False

    # Project config
    project_config = Path.cwd() / ".claude" / "config" / "project-settings.yaml"
    if project_config.exists():
        if validate_yaml_file(project_config, "Project config"):
            print("✓ Project config: valid YAML")
        else:
            all_valid = False

    if all_valid:
        print("✓ Configuration files: valid")

    return all_valid

def count_and_validate_skills(claude_dir, name):
    """Count and validate skills."""
    skills_dir = claude_dir / "skills"
    if not skills_dir.exists():
        return True

    total = 0
    valid = 0

    for item in skills_dir.iterdir():
        if item.is_dir():
            skill_file = item / "SKILL.md"
            if skill_file.exists():
                total += 1
                # Basic validation - file exists and readable
                try:
                    with open(skill_file, 'r') as f:
                        content = f.read()
                        if len(content) > 0:
                            valid += 1
                except (FileNotFoundError, PermissionError, UnicodeDecodeError):
                    # Can't read skill file - skip it
                    pass

    if total > 0:
        print(f"✓ {name} skills: {valid}/{total} valid")
        return valid == total
    return True

def main():
    print("AIDA Health Check")
    print("=" * 40)
    print()

    issues = []
    warnings = []

    # Run all checks
    if not check_python_version():
        issues.append("Python version")

    print()

    claude_dir = Path.home() / ".claude"
    if not check_directory(claude_dir, "AIDA directory", should_exist=False):
        warnings.append("AIDA not installed")

    print()

    if not check_git():
        issues.append("Git")

    print()

    if not check_github_cli():
        # gh is optional, already handles its own messaging
        pass

    print()

    if not check_aida_venv():
        issues.append("AIDA virtual environment")

    print()

    if not validate_config_files():
        issues.append("Configuration files")

    print()

    if claude_dir.exists():
        if not count_and_validate_skills(claude_dir, "Global"):
            issues.append("Global skills")

    project_claude = Path.cwd() / ".claude"
    if project_claude.exists():
        if not count_and_validate_skills(project_claude, "Project"):
            issues.append("Project skills")

    # Summary
    print()
    print("=" * 40)
    print("Summary")
    print("=" * 40)

    if not issues and not warnings:
        print("✓ All checks passed!")
        print()
        print("AIDA is healthy and ready to use. 🚀")
        return 0
    elif issues:
        print(f"✗ {len(issues)} issue(s) found:")
        for issue in issues:
            print(f"  • {issue}")
        print()
        print("Recommendation: Address issues above")
        print("Need help? Run /aida bug to report issues")
        return 1
    else:
        print(f"⚠ {len(warnings)} warning(s):")
        for warning in warnings:
            print(f"  • {warning}")
        print()
        print("AIDA is functional but has warnings.")
        print("Run /aida config to complete setup")
        return 0

if __name__ == "__main__":
    sys.exit(main())
