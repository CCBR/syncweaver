"""Basic tests for the bin/syncweaver CLI wrapper."""

import pathlib
import re
import subprocess


def _run_bin_syncweaver(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ./bin/syncweaver with subprocess.

    Args:
        *args: Command-line arguments to pass to the wrapper script.

    Returns:
        subprocess.CompletedProcess[str]: Completed subprocess result.
    """
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    command = ["./bin/syncweaver", *args]
    result = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result


def test_bin_syncweaver_help() -> None:
    """Validate that ./bin/syncweaver --help executes successfully."""
    result = _run_bin_syncweaver("--help")
    assert result.returncode == 0, result.stderr
    assert "syncweaver" in result.stdout
    assert "update" in result.stdout
    assert "remove" in result.stdout


def test_bin_syncweaver_version() -> None:
    """Validate that ./bin/syncweaver --version executes successfully."""
    result = _run_bin_syncweaver("--version")
    assert result.returncode == 0, result.stderr
    assert re.search(r".+, version\s+\S+", result.stdout) is not None
