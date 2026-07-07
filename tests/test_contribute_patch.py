"""Tests for contribute-patch metadata resolution and patch contribution."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from syncweaver.contribute_patch import (
    contribute_patch,
    resolve_contribute_patch_metadata,
)
from syncweaver.git import resolve_github_token, run_git


def test_resolve_github_token_uses_explicit_token():
    """Verify explicit token argument is returned directly.

    Returns:
        None: Assertions validate function behavior.
    """
    result = resolve_github_token("ghp_explicit")
    assert result == "ghp_explicit"


def test_resolve_github_token_falls_back_to_env(monkeypatch):
    """Verify GITHUB_TOKEN env var is used when no explicit token is given.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_from_env")
    result = resolve_github_token("")
    assert result == "ghp_from_env"


def test_resolve_github_token_falls_back_to_gh_cli(monkeypatch):
    """Verify gh auth token output is used when env var is absent.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    fake_result = MagicMock(returncode=0, stdout="ghp_from_gh\n")
    with patch("syncweaver.git.subprocess.run", return_value=fake_result):
        result = resolve_github_token("")
    assert result == "ghp_from_gh"


def test_resolve_github_token_raises_when_nothing_available(monkeypatch):
    """Verify RuntimeError is raised when no token source is available.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    fake_result = MagicMock(returncode=1, stdout="")
    with patch("syncweaver.git.subprocess.run", return_value=fake_result):
        with pytest.raises(RuntimeError, match="No GitHub token found"):
            resolve_github_token("")


def test_resolve_github_token_raises_when_gh_not_installed(monkeypatch):
    """Verify RuntimeError is raised when gh binary is not installed.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch("syncweaver.git.subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match="No GitHub token found"):
            resolve_github_token("")


def _write_lockfile(tmp_path, lock_data: dict) -> None:
    """Write lockfile JSON fixture to a temp directory."""
    lockfile_path = tmp_path / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")


def _default_lock_data() -> dict:
    """Build a minimal valid lockfile payload with one tracked source."""
    lock_data = {
        "host": "CCBR/host-repo",
        "orchestrator": "CCBR/syncweaver-orchestrator",
        "syncweaver_version": "0.0.1-dev",
        "sources": {
            "code/pkg": {
                "repo_url": "https://github.com/CCBR/package1",
                "ref": "main",
                "git_sha": "3a1f2d49a7a0e8e3db7a9d3b2ea73ff77d1f9b10",
                "patch": "code/pkg/.syncweaver/code-pkg.diff",
            }
        },
    }
    return lock_data


def test_resolve_contribute_patch_from_lockfile_defaults(tmp_path):
    """Verify defaults resolve source repository and patch from lockfile fields."""
    lock_data = _default_lock_data()
    _write_lockfile(tmp_path, lock_data)

    patch_file = tmp_path / "code/pkg/.syncweaver/code-pkg.diff"
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    patch_file.write_text(
        "--- a/pkg.py\n+++ b/pkg.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
    )

    result = resolve_contribute_patch_metadata(
        lockfile=tmp_path / ".syncweaver-lock.json",
        host_cwd=tmp_path,
        source_path="code/pkg",
        repo_url="",
        source_repository="",
        patch_path="",
        source_base_ref="",
    )

    assert result["source_path"] == "code/pkg"
    assert result["repo_url"] == "https://github.com/CCBR/package1"
    assert result["source_repository"] == "CCBR/package1"
    assert result["patch_path"] == "code/pkg/.syncweaver/code-pkg.diff"
    assert result["source_base_ref"] == "main"


def test_resolve_contribute_patch_uses_patch_override(tmp_path):
    """Verify explicit patch_path input overrides lockfile patch metadata."""
    lock_data = _default_lock_data()
    _write_lockfile(tmp_path, lock_data)

    patch_file = tmp_path / "custom/override.diff"
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    patch_file.write_text(
        "--- a/pkg.py\n+++ b/pkg.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
    )

    result = resolve_contribute_patch_metadata(
        lockfile=tmp_path / ".syncweaver-lock.json",
        host_cwd=tmp_path,
        source_path="code/pkg",
        repo_url="",
        source_repository="",
        patch_path="custom/override.diff",
        source_base_ref="release",
    )

    assert result["patch_path"] == "custom/override.diff"
    assert result["source_base_ref"] == "release"


def test_resolve_contribute_patch_fails_without_patch(tmp_path):
    """Verify missing patch metadata raises a readable error."""
    lock_data = _default_lock_data()
    lock_data["sources"]["code/pkg"].pop("patch")
    _write_lockfile(tmp_path, lock_data)

    with pytest.raises(ValueError, match="no patch path was provided"):
        resolve_contribute_patch_metadata(
            lockfile=tmp_path / ".syncweaver-lock.json",
            host_cwd=tmp_path,
            source_path="code/pkg",
            repo_url="",
            source_repository="",
            patch_path="",
            source_base_ref="",
        )


def test_resolve_contribute_patch_fails_when_patch_missing_on_disk(tmp_path):
    """Verify resolved patch path must exist in the host repository checkout."""
    lock_data = _default_lock_data()
    _write_lockfile(tmp_path, lock_data)

    with pytest.raises(FileNotFoundError, match="resolved patch file does not exist"):
        resolve_contribute_patch_metadata(
            lockfile=tmp_path / ".syncweaver-lock.json",
            host_cwd=tmp_path,
            source_path="code/pkg",
            repo_url="",
            source_repository="",
            patch_path="",
            source_base_ref="",
        )


def test_resolve_contribute_patch_uses_repo_selector_for_source_resolution(tmp_path):
    """Verify source_repository input can disambiguate source_path resolution."""
    lock_data = {
        "host": "CCBR/host-repo",
        "orchestrator": "CCBR/syncweaver-orchestrator",
        "syncweaver_version": "0.0.1-dev",
        "sources": {
            "code/pkg1": {
                "repo_url": "https://github.com/CCBR/package1",
                "ref": "main",
                "git_sha": "3a1f2d49a7a0e8e3db7a9d3b2ea73ff77d1f9b10",
                "patch": "code/pkg1/.syncweaver/pkg1.diff",
            },
            "code/pkg2": {
                "repo_url": "https://github.com/CCBR/package2",
                "ref": "main",
                "git_sha": "4b2f2d49a7a0e8e3db7a9d3b2ea73ff77d1f9b11",
                "patch": "code/pkg2/.syncweaver/pkg2.diff",
            },
        },
    }
    _write_lockfile(tmp_path, lock_data)

    patch_file = tmp_path / "code/pkg2/.syncweaver/pkg2.diff"
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    patch_file.write_text(
        "--- a/pkg.py\n+++ b/pkg.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
    )

    result = resolve_contribute_patch_metadata(
        lockfile=tmp_path / ".syncweaver-lock.json",
        host_cwd=tmp_path,
        source_path="",
        repo_url="",
        source_repository="CCBR/package2",
        patch_path="",
        source_base_ref="",
    )

    assert result["source_path"] == "code/pkg2"
    assert result["source_repository"] == "CCBR/package2"


def test_contribute_patch_clones_applies_and_opens_pr(tmp_path):
    """Verify contribute_patch drives git operations and the GitHub API call.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    patch_file = tmp_path / "code/pkg/.syncweaver/code-pkg.diff"
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    patch_file.write_text(
        "--- a/pkg.py\n+++ b/pkg.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
    )

    resolved = {
        "source_path": "code/pkg",
        "repo_url": "https://github.com/CCBR/package1",
        "source_repository": "CCBR/package1",
        "patch_path": "code/pkg/.syncweaver/code-pkg.diff",
        "source_base_ref": "main",
    }

    git_calls: list[tuple[list[str], dict[str, str] | None]] = []

    def _fake_run_git(args: list[str], cwd=None, env=None, redacted_values=None) -> str:
        del cwd
        del redacted_values
        git_calls.append((args, env))
        if args[-1] == "diff" or "diff" in args:
            return "1 file changed"
        return ""

    fake_apply = MagicMock(return_value=MagicMock(returncode=0, stderr=""))

    fake_response = MagicMock()
    fake_response.ok = True
    fake_response.json.return_value = {
        "html_url": "https://github.com/CCBR/package1/pull/99"
    }

    with (
        patch("syncweaver.contribute_patch.run_git", side_effect=_fake_run_git),
        patch("subprocess.run", return_value=fake_apply.return_value),
        patch("requests.post", return_value=fake_response) as mock_post,
    ):
        pr_url = contribute_patch(
            resolved=resolved,
            host_cwd=tmp_path,
            github_token="ghp_testtoken",
        )

    assert pr_url == "https://github.com/CCBR/package1/pull/99"
    assert mock_post.called
    call_kwargs = mock_post.call_args
    assert "CCBR/package1" in call_kwargs.args[0]
    assert call_kwargs.kwargs["json"]["base"] == "main"
    assert "code/pkg" in call_kwargs.kwargs["json"]["title"]
    assert git_calls[0][0][3] == "https://github.com/CCBR/package1.git"
    assert all("ghp_testtoken" not in " ".join(args) for args, _env in git_calls)
    assert git_calls[0][1] is not None
    assert "GIT_CONFIG_COUNT" in git_calls[0][1]


def test_contribute_patch_raises_when_no_diff(tmp_path):
    """Verify contribute_patch raises when patch introduces no changes.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    patch_file = tmp_path / "code/pkg/.syncweaver/code-pkg.diff"
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    patch_file.write_text(
        "--- a/pkg.py\n+++ b/pkg.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
    )

    resolved = {
        "source_path": "code/pkg",
        "repo_url": "https://github.com/CCBR/package1",
        "source_repository": "CCBR/package1",
        "patch_path": "code/pkg/.syncweaver/code-pkg.diff",
        "source_base_ref": "main",
    }

    def _fake_run_git(args: list[str], cwd=None, env=None, redacted_values=None) -> str:
        del cwd
        del env
        del redacted_values
        if "diff" in args:
            return ""
        return ""

    with (
        patch("syncweaver.contribute_patch.run_git", side_effect=_fake_run_git),
        patch(
            "subprocess.run",
            return_value=MagicMock(returncode=0, stderr=""),
        ),
    ):
        with pytest.raises(RuntimeError, match="no source changes"):
            contribute_patch(
                resolved=resolved,
                host_cwd=tmp_path,
                github_token="ghp_testtoken",
            )


def test_run_git_redacts_sensitive_values() -> None:
    """Verify git helper redacts sensitive substrings from raised errors.

    Returns:
        None: Assertions validate function behavior.
    """
    fake_result = MagicMock(returncode=1, stderr="fatal: token ghp_secret leaked")

    with patch("syncweaver.git.subprocess.run", return_value=fake_result):
        with pytest.raises(RuntimeError) as exc_info:
            run_git(["fetch", "origin"], redacted_values=["ghp_secret"])

    assert "ghp_secret" not in str(exc_info.value)
    assert "[REDACTED]" in str(exc_info.value)
