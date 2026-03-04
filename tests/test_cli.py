"""Tests for CLI entry point and version."""
import subprocess
import sys


def test_module_runnable():
    """snatch.cli should be importable without hanging."""
    result = subprocess.run(
        [sys.executable, "-c", "from snatch.constants import VERSION; print(VERSION)"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "2.0.0" in result.stdout


def test_cli_help():
    """snatch.cli --help should print usage info."""
    result = subprocess.run(
        [sys.executable, "-m", "snatch.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    # --help should succeed (exit code 0)
    assert result.returncode == 0
    assert "snatch" in result.stdout.lower() or "usage" in result.stdout.lower()
