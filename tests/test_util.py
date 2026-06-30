"""Tests for shared syncweaver utilities."""

from __future__ import annotations

import subprocess

from syncweaver.util import format_subprocess_error


def test_format_subprocess_error_includes_stdout_and_stderr():
    """Verify subprocess formatting preserves captured output."""
    error = subprocess.CalledProcessError(
        returncode=1,
        cmd=["Rscript", "script.R"],
        output="helper stdout",
        stderr="helper stderr",
    )

    message = format_subprocess_error(error)

    assert "returned non-zero exit status 1" in message
    assert "stderr:\nhelper stderr" in message
    assert "stdout:\nhelper stdout" in message
