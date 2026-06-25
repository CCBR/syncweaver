"""Tests for the syncweaver update subcommand."""

from __future__ import annotations

import json
import pathlib
import subprocess

from click.testing import CliRunner

import syncweaver.cli.add as add_module
from syncweaver.cli import cli


def _run(command: list[str], cwd: pathlib.Path) -> None:
    """Run a subprocess command and fail the test when it does not succeed."""
    subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)


def _init_git_repo(path: pathlib.Path, remote_url: str | None = None) -> None:
    """Initialize a git repository with one committed file."""
    _run(["git", "init", "-b", "main"], cwd=path)
    _run(["git", "config", "user.email", "test@example.com"], cwd=path)
    _run(["git", "config", "user.name", "Test User"], cwd=path)
    if remote_url:
        _run(["git", "remote", "add", "origin", remote_url], cwd=path)

    (path / "README.md").write_text("# test repo\n")
    _run(["git", "add", "README.md"], cwd=path)
    _run(["git", "commit", "--no-verify", "-m", "init"], cwd=path)


def test_update_refreshes_tracked_subdir_and_lockfile(tmp_path, monkeypatch):
    """Verify `update` refreshes vendored files and git_sha for remote_subdir.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    source_repo = tmp_path / "source"
    source_repo.mkdir()
    _init_git_repo(source_repo)

    package_root = source_repo / "subprojects/package1"
    package_root.mkdir(parents=True)
    (package_root / "pkg.py").write_text("VALUE = 1\n")
    _run(["git", "add", "subprojects/package1/pkg.py"], cwd=source_repo)
    _run(["git", "commit", "--no-verify", "-m", "add nested package"], cwd=source_repo)

    host_repo = tmp_path / "host"
    host_repo.mkdir()
    _init_git_repo(host_repo)
    monkeypatch.chdir(host_repo)
    monkeypatch.setattr(
        add_module,
        "_resolve_repo_url_input",
        lambda _repo_url, _cwd: (str(source_repo), str(source_repo)),
    )

    runner = CliRunner()
    add_result = runner.invoke(
        cli,
        [
            "add",
            "--path",
            "code/package1",
            "--repo-url",
            str(source_repo),
            "--ref",
            "main",
            "--remote-subdir",
            "subprojects/package1",
        ],
    )
    assert add_result.exit_code == 0

    old_lock = json.loads((host_repo / ".syncweaver-lock.json").read_text())
    old_sha = old_lock["sources"]["code/package1"]["git_sha"]

    (package_root / "pkg.py").write_text("VALUE = 2\n")
    _run(["git", "add", "subprojects/package1/pkg.py"], cwd=source_repo)
    _run(
        ["git", "commit", "--no-verify", "-m", "update nested package"], cwd=source_repo
    )

    update_result = runner.invoke(
        cli,
        [
            "update",
            "--path",
            "code/package1",
        ],
    )

    assert update_result.exit_code == 0
    assert (host_repo / "code/package1/pkg.py").read_text() == "VALUE = 2\n"

    new_lock = json.loads((host_repo / ".syncweaver-lock.json").read_text())
    source_entry = new_lock["sources"]["code/package1"]
    assert source_entry["git_sha"] != old_sha
    assert source_entry["remote_subdir"] == "subprojects/package1"


def test_update_allows_remote_subdir_override(tmp_path, monkeypatch):
    """Verify `update --remote-subdir` can switch tracked subdirectory.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    source_repo = tmp_path / "source"
    source_repo.mkdir()
    _init_git_repo(source_repo)

    old_root = source_repo / "old-subdir"
    new_root = source_repo / "new-subdir"
    old_root.mkdir(parents=True)
    new_root.mkdir(parents=True)
    (old_root / "pkg.py").write_text("VALUE = 1\n")
    (new_root / "pkg.py").write_text("VALUE = 99\n")
    _run(["git", "add", "old-subdir/pkg.py", "new-subdir/pkg.py"], cwd=source_repo)
    _run(["git", "commit", "--no-verify", "-m", "add two subdirs"], cwd=source_repo)

    host_repo = tmp_path / "host"
    host_repo.mkdir()
    _init_git_repo(host_repo)
    monkeypatch.chdir(host_repo)
    monkeypatch.setattr(
        add_module,
        "_resolve_repo_url_input",
        lambda _repo_url, _cwd: (str(source_repo), str(source_repo)),
    )

    runner = CliRunner()
    add_result = runner.invoke(
        cli,
        [
            "add",
            "--path",
            "code/package1",
            "--repo-url",
            str(source_repo),
            "--ref",
            "main",
            "--remote-subdir",
            "old-subdir",
        ],
    )
    assert add_result.exit_code == 0
    assert (host_repo / "code/package1/pkg.py").read_text() == "VALUE = 1\n"

    update_result = runner.invoke(
        cli,
        [
            "update",
            "--path",
            "code/package1",
            "--remote-subdir",
            "new-subdir",
        ],
    )

    assert update_result.exit_code == 0
    assert (host_repo / "code/package1/pkg.py").read_text() == "VALUE = 99\n"

    lock_data = json.loads((host_repo / ".syncweaver-lock.json").read_text())
    assert lock_data["sources"]["code/package1"]["remote_subdir"] == "new-subdir"
