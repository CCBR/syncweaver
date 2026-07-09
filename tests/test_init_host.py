"""Tests for host initialization helpers and CLI command."""

from __future__ import annotations

import json
import pathlib
import subprocess

from click.testing import CliRunner

from syncweaver.cli import cli
from syncweaver.init_host import _upsert_host_registry_entry


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

    (path / "README.md").write_text("# host repo\n")
    _run(["git", "add", "README.md"], cwd=path)
    _run(["git", "commit", "--no-verify", "-m", "init"], cwd=path)


def test_init_host_cli_local_copy_without_registration(tmp_path, monkeypatch):
    """Verify `syncweaver init host --no-register` writes boilerplate files.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    host_repo = tmp_path / "host-repo"
    host_repo.mkdir()
    _init_git_repo(host_repo, remote_url="https://github.com/NIDAP-Community/host-repo")
    monkeypatch.chdir(host_repo)

    runner = CliRunner()
    result = runner.invoke(cli, ["init", "host", "--no-register"])

    assert result.exit_code == 0, result.output
    assert (host_repo / ".syncweaver-lock.json").is_file()
    assert (
        host_repo / ".github" / "workflows" / "syncweaver-host-update.yml"
    ).is_file()
    assert (
        host_repo / ".github" / "workflows" / "syncweaver-host-contribute-patch.yml"
    ).is_file()

    lock_data = json.loads((host_repo / ".syncweaver-lock.json").read_text())
    assert lock_data["host"] == "NIDAP-Community/host-repo"
    assert lock_data["orchestrator"] == "NIDAP-Community/syncweaver-orchestrator"
    assert isinstance(lock_data["sources"], dict)


def test_init_host_cli_registers_host_in_orchestrator(monkeypatch, tmp_path):
    """Verify `syncweaver init host` resolves token and registers host repo.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    observed: dict[str, str] = {}

    host_repo = tmp_path / "host-repo"
    host_repo.mkdir()
    _init_git_repo(host_repo, remote_url="https://github.com/NIDAP-Community/host-repo")
    monkeypatch.chdir(host_repo)

    def _stub_resolve_github_token(token: str) -> str:
        observed["token_input"] = token
        resolved = "resolved-token"
        return resolved

    def _stub_register_host_with_orchestrator_repository(
        *,
        orchestrator_repo: str,
        host_repo: str,
        lockfile_path: str,
        github_token: str,
        host_registry_path: pathlib.Path,
        branch_name: str,
        base_ref: str,
        pr_title: str,
        pr_body: str,
    ) -> dict[str, str | bool]:
        observed["orchestrator_repo"] = orchestrator_repo
        observed["host_repo"] = host_repo
        observed["lockfile_path"] = lockfile_path
        observed["github_token"] = github_token
        observed["host_registry_path"] = host_registry_path.as_posix()
        observed["branch_name"] = branch_name
        observed["base_ref"] = base_ref
        observed["pr_title"] = pr_title
        observed["pr_body"] = pr_body
        result = {
            "orchestrator_repository": orchestrator_repo,
            "host_repository": host_repo,
            "lockfile": lockfile_path,
            "branch": "syncweaver/init-host/host-repo",
            "base_ref": "main",
            "created_pr": True,
            "pr_url": "https://github.com/NIDAP-Community/syncweaver-orchestrator/pull/1",
        }
        return result

    monkeypatch.setattr(
        "syncweaver.cli.init.resolve_github_token",
        _stub_resolve_github_token,
    )
    monkeypatch.setattr(
        "syncweaver.cli.init.register_host_with_orchestrator_repository",
        _stub_register_host_with_orchestrator_repository,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "init",
            "host",
            "--token",
            "raw-token",
            "--registry-path",
            ".github/host-repositories.yml",
        ],
    )

    assert result.exit_code == 0, result.output
    assert observed["token_input"] == "raw-token"
    assert observed["github_token"] == "resolved-token"
    assert observed["host_repo"] == "NIDAP-Community/host-repo"
    assert observed["orchestrator_repo"] == "NIDAP-Community/syncweaver-orchestrator"
    assert observed["lockfile_path"] == ".syncweaver-lock.json"
    assert "Pull request:" in result.output


def test_upsert_host_registry_omits_default_lockfile_for_new_host() -> None:
    """Verify new host entries omit lockfile when path is default."""
    host_entries: list[dict[str, str]] = []

    changed = _upsert_host_registry_entry(
        host_entries=host_entries,
        host_repo="NIDAP-Community/host-repo",
        lockfile_path=".syncweaver-lock.json",
    )

    assert changed is True
    assert host_entries == [{"repository": "NIDAP-Community/host-repo"}]


def test_upsert_host_registry_keeps_non_default_lockfile_for_new_host() -> None:
    """Verify new host entries preserve explicit non-default lockfile path."""
    host_entries: list[dict[str, str]] = []

    changed = _upsert_host_registry_entry(
        host_entries=host_entries,
        host_repo="NIDAP-Community/host-repo",
        lockfile_path="config/lock.json",
    )

    assert changed is True
    assert host_entries == [
        {
            "repository": "NIDAP-Community/host-repo",
            "lockfile": "config/lock.json",
        }
    ]


def test_upsert_host_registry_removes_redundant_default_lockfile() -> None:
    """Verify existing entries drop explicit default lockfile values."""
    host_entries: list[dict[str, str]] = [
        {
            "repository": "NIDAP-Community/host-repo",
            "lockfile": ".syncweaver-lock.json",
        }
    ]

    changed = _upsert_host_registry_entry(
        host_entries=host_entries,
        host_repo="NIDAP-Community/host-repo",
        lockfile_path=".syncweaver-lock.json",
    )

    assert changed is True
    assert host_entries == [{"repository": "NIDAP-Community/host-repo"}]
