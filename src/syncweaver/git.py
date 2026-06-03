"""Git command helpers shared across syncweaver modules."""

from __future__ import annotations

import pathlib
import subprocess


def run_git(args: list[str], cwd: pathlib.Path | None = None) -> str:
    """Run a git command and return stdout, raising RuntimeError on failure."""
    command = ["git", *args]
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        cmd = " ".join(command)
        raise RuntimeError(f"Git command failed: {cmd}\n{stderr}")
    return result.stdout.strip()
