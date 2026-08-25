"""Module boundary tests — enforce allowed dependency directions.

Blueprint: §25 — Module Boundaries & Dependency Rules.

This test runs the same checks as the CI script but as a pytest test,
so boundary violations fail the test suite directly.
"""
from __future__ import annotations


import subprocess
import sys
from pathlib import Path


def test_ci_gates_script_exists():
    """The CI gates script must exist."""
    script = Path(__file__).resolve().parent.parent.parent / "scripts" / "ci_copilot_gates.py"
    assert script.exists(), f"CI gates script not found at {script}"


def test_ci_gates_pass():
    """Run the CI gates script and assert zero violations."""
    script = Path(__file__).resolve().parent.parent.parent / "scripts" / "ci_copilot_gates.py"

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(script.parent.parent),
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, f"CI gates failed with code {result.returncode}:\n{output}"
