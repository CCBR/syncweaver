"""Tests for the syncweaver remove subcommand."""

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


def _init_git_repo(path: pathlib.Path) -> None:
    """Initialize a git repository with one committed file."""
    _run(["git", "init", "-b", "main"], cwd=path)
    _run(["git", "config", "user.email", "test@example.com"], cwd=path)
    _run(["git", "config", "user.name", "Test User"], cwd=path)

    (path / "README.md").write_text("# test repo\n")
    _run(["git", "add", "README.md"], cwd=path)
    _run(["git", "commit", "--no-verify", "-m", "init"], cwd=path)


def test_remove_deletes_vendored_tree_and_lockfile_entry(tmp_path, monkeypatch):
    """Verify `remove` deletes the vendored tree and clears lockfile metadata."""
    source_repo = tmp_path / "source"
    source_repo.mkdir()
    _init_git_repo(source_repo)
    (source_repo / "pkg.py").write_text("VALUE = 1\n")
    _run(["git", "add", "pkg.py"], cwd=source_repo)
    _run(["git", "commit", "--no-verify", "-m", "add package file"], cwd=source_repo)

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
        ],
    )
    assert add_result.exit_code == 0

    (host_repo / "code/package1/pkg.py").write_text("VALUE = 2\n")
    patch_result = runner.invoke(
        cli,
        [
            "patch",
            "create",
            "--path",
            "code/package1",
            "--repo-url",
            str(source_repo),
        ],
    )
    assert patch_result.exit_code == 0

    remove_result = runner.invoke(
        cli,
        [
            "remove",
            "--path",
            "code/package1",
        ],
    )

    assert remove_result.exit_code == 0
    assert not (host_repo / "code/package1").exists()
    assert not (host_repo / "code/package1/.syncweaver/code-package1.diff").exists()

    lock_data = json.loads((host_repo / ".syncweaver-lock.json").read_text())
    assert "code/package1" not in lock_data["sources"]
