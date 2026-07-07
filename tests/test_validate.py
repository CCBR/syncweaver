"""Tests for the syncweaver validate command."""

from __future__ import annotations

import json

from click.testing import CliRunner

from syncweaver.cli import cli


def test_validate_accepts_new_lockfile_shape(tmp_path, monkeypatch):
    """Verify validate succeeds for the new top-level sources shape.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    lock_data = {
        "host": "CCBR/host-repo1",
        "orchestrator": "CCBR/syncweaver",
        "syncweaver_version": "0.0.1-dev",
        "sources": {
            "code/package1": {
                "repo_url": "https://github.com/CCBR/package1",
                "ref": "main",
                "git_sha": "3a1f2d49a7a0e8e3db7a9d3b2ea73ff77d1f9b10",
                "remote_subdir": "modules/package1",
                "patch": "code/package1/.syncweaver/code-package1.diff",
            }
        },
    }
    lockfile_path = tmp_path / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["validate"])

    assert result.exit_code == 0
    assert "Lockfile is valid" in result.output


def test_validate_rejects_legacy_lockfile_shape(tmp_path, monkeypatch):
    """Verify validate fails for the legacy lockfile shape with repos/sources nesting.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    lock_data = {
        "host": "CCBR/host-repo1",
        "orchestrator": "CCBR/syncweaver",
        "syncweaver_version": "0.0.1-dev",
        "repos": {
            "https://github.com/CCBR/package1": {
                "sources": {
                    "code/package1": {
                        "branch": "main",
                        "git_sha": "3a1f2d49a7a0e8e3db7a9d3b2ea73ff77d1f9b10",
                    }
                }
            }
        },
    }
    lockfile_path = tmp_path / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["validate"])

    assert result.exit_code != 0
    assert "Lockfile does not match schema" in result.output
    assert "sources" in result.output
