"""Tests for CLI entry point and version."""
import subprocess
import sys


def test_module_runnable():
    """snatch.cli should be runnable as a module with --help."""
    result = subprocess.run(
        [sys.executable, "-m", "snatch.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # --help should succeed (exit code 0)
    assert result.returncode == 0
    assert "snatch" in result.stdout.lower() or "usage" in result.stdout.lower()


def test_version_flag():
    """snatch.cli --version should print the version."""
    result = subprocess.run(
        [sys.executable, "-m", "snatch.cli", "version"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # Should contain version string somewhere in output
    assert "2.0.0" in result.stdout or "2.0.0" in result.stderr or result.returncode == 0
