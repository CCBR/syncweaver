"""Tests for the syncweaver add subcommand."""

from __future__ import annotations

import json
import pathlib
import subprocess

from click.testing import CliRunner

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


def test_add_vendors_repository_and_updates_lockfile(tmp_path, monkeypatch):
    """Verify `add` vendors source files and records lockfile metadata.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    source_repo = tmp_path / "source"
    source_repo.mkdir()
    _init_git_repo(source_repo)
    (source_repo / "pkg.py").write_text("VALUE = 1\n")
    _run(["git", "add", "pkg.py"], cwd=source_repo)
    _run(["git", "commit", "--no-verify", "-m", "add package file"], cwd=source_repo)
    source_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    host_repo = tmp_path / "host-repo"
    host_repo.mkdir()
    _init_git_repo(host_repo, remote_url="https://github.com/CCBR/host-repo1.git")
    monkeypatch.chdir(host_repo)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "add",
            "--path",
            "code/package1",
            "--repo-url",
            str(source_repo),
            "--ref",
            "main",
        ],
    )

    assert result.exit_code == 0
    assert (host_repo / "code/package1/pkg.py").exists()

    lockfile = json.loads((host_repo / ".syncweaver-lock.json").read_text())
    assert lockfile["name"] == "CCBR/host-repo1"
    assert lockfile["homePage"] == "https://github.com/CCBR/host-repo1"
    source_entry = lockfile["sources"]["code/package1"]
    assert source_entry["repo_url"] == str(source_repo)
    assert source_entry["ref"] == "main"
    assert source_entry["git_sha"] == source_sha
    assert source_entry["installed_by"] == ["syncweaver"]
    assert "patch" not in source_entry
    assert "patches" not in source_entry


def test_add_refuses_to_overwrite_existing_destination(tmp_path, monkeypatch):
    """Verify `add` refuses to replace an existing destination by default.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    source_repo = tmp_path / "source"
    source_repo.mkdir()
    _init_git_repo(source_repo)

    host_repo = tmp_path / "host-repo"
    host_repo.mkdir()
    _init_git_repo(host_repo)
    existing = host_repo / "code/package1"
    existing.mkdir(parents=True)
    (existing / "old.txt").write_text("existing\n")

    monkeypatch.chdir(host_repo)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "add",
            "--path",
            "code/package1",
            "--repo-url",
            str(source_repo),
        ],
    )

    assert result.exit_code != 0
    assert "Destination already exists" in result.output


def test_add_with_remote_subdir_vendors_only_subdir_and_tracks_metadata(
    tmp_path, monkeypatch
):
    """Verify `add` vendors only a remote subdirectory and stores remote_subdir.

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
    (source_repo / "root-only.txt").write_text("do not vendor\n")
    _run(
        ["git", "add", "subprojects/package1/pkg.py", "root-only.txt"], cwd=source_repo
    )
    _run(["git", "commit", "--no-verify", "-m", "add nested package"], cwd=source_repo)

    host_repo = tmp_path / "host-repo"
    host_repo.mkdir()
    _init_git_repo(host_repo)
    monkeypatch.chdir(host_repo)

    runner = CliRunner()
    result = runner.invoke(
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

    assert result.exit_code == 0
    assert (host_repo / "code/package1/pkg.py").exists()
    assert not (host_repo / "code/package1/root-only.txt").exists()

    lockfile = json.loads((host_repo / ".syncweaver-lock.json").read_text())
    source_entry = lockfile["sources"]["code/package1"]
    assert source_entry["remote_subdir"] == "subprojects/package1"
