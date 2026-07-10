"""Tests for orchestrator initialization helpers and CLI command."""

from __future__ import annotations

import pathlib

from click.testing import CliRunner

from syncweaver.cli import cli
from syncweaver.init_orchestrator import init_orchestrator_in_directory


def test_init_orchestrator_in_directory_copies_files(tmp_path):
    """Verify orchestrator template files are copied into destination directory.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    copied_files = init_orchestrator_in_directory(destination_dir=tmp_path)
    copied_relpaths = sorted(
        path.relative_to(tmp_path).as_posix() for path in copied_files
    )

    assert copied_relpaths == [
        ".github/.gitkeep",
        ".github/host-repositories.yml",
        ".github/workflows/syncweaver-update-hosts.yml",
        "LICENSE.md",
        "README.md",
    ]
    assert (tmp_path / "LICENSE.md").is_file()
    assert (tmp_path / "README.md").is_file()
    assert (tmp_path / ".github" / "host-repositories.yml").is_file()
    assert (
        tmp_path / ".github" / "workflows" / "syncweaver-update-hosts.yml"
    ).is_file()


def test_init_orch_cli_local_copy(tmp_path):
    """Verify `syncweaver init orch` copies files into current working directory.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    runner = CliRunner()
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["init", "orch"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "Copied" in result.output
        assert pathlib.Path("README.md").is_file()
        assert pathlib.Path("LICENSE.md").is_file()


def test_init_orch_cli_repo_mode(monkeypatch):
    """Verify repo mode resolves token and delegates to remote initializer.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    observed: dict[str, str] = {}

    def _stub_resolve_github_token(token: str) -> str:
        observed["token_input"] = token
        result = "resolved-token"
        return result

    def _stub_init_orchestrator_in_repository(
        repo_slug: str,
        github_token: str,
        *,
        branch_name: str,
        base_ref: str,
        overwrite: bool,
        create_if_missing: bool,
        private: bool,
        pr_title: str,
        pr_body: str,
    ) -> dict[str, str | bool]:
        observed["repo_slug"] = repo_slug
        observed["github_token"] = github_token
        observed["branch_name"] = branch_name
        observed["base_ref"] = base_ref
        observed["overwrite"] = str(overwrite)
        observed["create_if_missing"] = str(create_if_missing)
        observed["private"] = str(private)
        observed["pr_title"] = pr_title
        observed["pr_body"] = pr_body
        result = {
            "repository": repo_slug,
            "base_ref": "main",
            "branch": branch_name,
            "created_repo": False,
            "pr_url": "https://github.com/OWNER/REPO/pull/1",
        }
        return result

    monkeypatch.setattr(
        "syncweaver.cli.init.resolve_github_token",
        _stub_resolve_github_token,
    )
    monkeypatch.setattr(
        "syncweaver.cli.init.init_orchestrator_in_repository",
        _stub_init_orchestrator_in_repository,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "init",
            "orch",
            "--repo",
            "OWNER/REPO",
            "--token",
            "raw-token",
            "--branch",
            "custom/init-branch",
            "--base-ref",
            "develop",
            "--create-repo",
            "--private",
            "--title",
            "Custom title",
            "--body",
            "Custom body",
        ],
    )

    assert result.exit_code == 0
    assert observed["token_input"] == "raw-token"
    assert observed["repo_slug"] == "OWNER/REPO"
    assert observed["github_token"] == "resolved-token"
    assert observed["branch_name"] == "custom/init-branch"
    assert observed["base_ref"] == "develop"
    assert observed["create_if_missing"] == "True"
    assert observed["private"] == "True"
    assert "Pull request:" in result.output
