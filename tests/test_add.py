"""Tests for the syncweaver add subcommand."""

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


def test_add_vendors_repository_and_updates_lockfile(tmp_path, monkeypatch):
    """Verify `add` vendors source files and records lockfile metadata.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    source_sha = "abc123"

    host_repo = tmp_path / "host-repo"
    host_repo.mkdir()
    _init_git_repo(host_repo, remote_url="https://github.com/CCBR/host-repo1.git")
    monkeypatch.chdir(host_repo)
    original_run_git = add_module.run_git

    def _fake_run_git(args, cwd=None, env=None, redacted_values=None):
        output = ""
        if args[:1] == ["clone"]:
            temp_repo = pathlib.Path(args[4])
            temp_repo.mkdir(parents=True, exist_ok=True)
            (temp_repo / "pkg.py").write_text("VALUE = 1\n")
        elif len(args) >= 3 and args[0] == "-C" and args[2] in {"fetch", "checkout"}:
            output = ""
        elif args[-2:] == ["rev-parse", "HEAD"]:
            output = source_sha
        else:
            output = original_run_git(
                args,
                cwd=cwd,
                env=env,
                redacted_values=redacted_values,
            )
        return output

    monkeypatch.setattr(add_module, "run_git", _fake_run_git)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "add",
            "--path",
            "code/package1",
            "--repo-url",
            "https://github.com/CCBR/package1",
            "--ref",
            "main",
        ],
    )

    assert result.exit_code == 0
    assert (host_repo / "code/package1/pkg.py").exists()

    lockfile = json.loads((host_repo / ".syncweaver-lock.json").read_text())
    assert lockfile["host"] == "CCBR/host-repo1"
    assert lockfile["orchestrator"] == "CCBR/syncweaver-orchestrator"
    assert lockfile["syncweaver_version"] == "0.0.1-dev"
    source_entry = lockfile["sources"]["code/package1"]
    assert source_entry["repo_url"] == "https://github.com/CCBR/package1"
    assert source_entry["ref"] == "main"
    assert source_entry["git_sha"] == source_sha
    assert "patch" not in source_entry
    assert "patches" not in source_entry

    gitattributes_lines = (host_repo / ".gitattributes").read_text().splitlines()
    assert "code/package1 linguist-vendored" in gitattributes_lines


def test_add_refuses_to_overwrite_existing_destination(tmp_path, monkeypatch):
    """Verify `add` refuses to replace an existing destination by default.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
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
            "https://github.com/CCBR/package1",
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
    host_repo = tmp_path / "host-repo"
    host_repo.mkdir()
    _init_git_repo(host_repo)
    monkeypatch.chdir(host_repo)

    def _fake_run_git(args, cwd=None, env=None, redacted_values=None):
        del cwd
        del env
        del redacted_values
        output = ""
        if args[:1] == ["clone"]:
            temp_repo = pathlib.Path(args[4])
            (temp_repo / "subprojects/package1").mkdir(parents=True, exist_ok=True)
            (temp_repo / "subprojects/package1/pkg.py").write_text("VALUE = 1\n")
            (temp_repo / "root-only.txt").write_text("do not vendor\n")
        elif args[-2:] == ["rev-parse", "HEAD"]:
            output = "abc123"
        return output

    monkeypatch.setattr(add_module, "run_git", _fake_run_git)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "add",
            "--path",
            "code/package1",
            "--repo-url",
            "https://github.com/CCBR/package1",
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


def test_add_rejects_local_repo_path(tmp_path, monkeypatch):
    """Verify `add` rejects local filesystem paths for --repo-url.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    source_repo = tmp_path / "source"
    source_repo.mkdir()

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
        ],
    )

    assert result.exit_code != 0
    assert "must not be a local filesystem path" in result.output


def test_add_accepts_owner_repo_shorthand(tmp_path, monkeypatch):
    """Verify `add --repo OWNER/REPO` resolves to a GitHub clone URL.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    host_repo = tmp_path / "host-repo"
    host_repo.mkdir()
    _init_git_repo(host_repo)
    (host_repo / ".syncweaver-lock.json").write_text(
        json.dumps(
            {
                "host": "NIDAP/host-repo",
                "orchestrator": "CCBR/syncweaver-orchestrator",
                "syncweaver_version": "0.0.1-dev",
                "sources": {},
            },
            indent=2,
        )
        + "\n"
    )
    monkeypatch.chdir(host_repo)

    clone_url_seen = {"value": ""}

    def _fake_run_git(args, cwd=None, env=None, redacted_values=None):
        del cwd
        del env
        del redacted_values
        output = ""
        if args[:1] == ["clone"]:
            clone_url_seen["value"] = args[3]
            temp_repo = pathlib.Path(args[4])
            temp_repo.mkdir(parents=True, exist_ok=True)
            (temp_repo / "pkg.py").write_text("VALUE = 1\n")
        elif args[-2:] == ["rev-parse", "HEAD"]:
            output = "abc123"
        return output

    monkeypatch.setattr(add_module, "run_git", _fake_run_git)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "add",
            "--path",
            "code/package1",
            "--repo",
            "CCBR/package1",
            "--ref",
            "main",
        ],
    )

    assert result.exit_code == 0, result.output
    assert clone_url_seen["value"] == "https://github.com/CCBR/package1.git"

    lockfile = json.loads((host_repo / ".syncweaver-lock.json").read_text())
    source_entry = lockfile["sources"]["code/package1"]
    assert source_entry["repo_url"] == "https://github.com/CCBR/package1"


def test_add_does_not_duplicate_existing_gitattributes_entry(tmp_path, monkeypatch):
    """Verify `add` does not duplicate an existing linguist-vendored entry.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    host_repo = tmp_path / "host-repo"
    host_repo.mkdir()
    _init_git_repo(host_repo)
    (host_repo / ".gitattributes").write_text(
        "code/package1 linguist-vendored\n*.md text\n"
    )
    monkeypatch.chdir(host_repo)

    def _fake_run_git(args, cwd=None, env=None, redacted_values=None):
        del cwd
        del env
        del redacted_values
        output = ""
        if args[:1] == ["clone"]:
            temp_repo = pathlib.Path(args[4])
            temp_repo.mkdir(parents=True, exist_ok=True)
            (temp_repo / "pkg.py").write_text("VALUE = 1\n")
        elif args[-2:] == ["rev-parse", "HEAD"]:
            output = "abc123"
        return output

    monkeypatch.setattr(add_module, "run_git", _fake_run_git)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "add",
            "--path",
            "code/package1",
            "--repo-url",
            "https://github.com/CCBR/package1",
            "--ref",
            "main",
        ],
    )

    assert result.exit_code == 0, result.output
    gitattributes_lines = (host_repo / ".gitattributes").read_text().splitlines()
    assert gitattributes_lines.count("code/package1 linguist-vendored") == 1
