"""Tests for shared git helper utilities."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from syncweaver.git import (
    git_commit_exists,
    is_full_git_sha,
    remote_ref_has_path_changes,
    resolve_remote_ref_to_git_sha,
)


def test_is_full_git_sha_accepts_valid_40_char_sha() -> None:
    """Verify full-length hexadecimal SHAs are recognized.

    Returns:
        None: Assertions validate function behavior.
    """
    value = "a" * 40

    assert is_full_git_sha(value)


def test_is_full_git_sha_rejects_short_sha() -> None:
    """Verify short SHA values are rejected.

    Returns:
        None: Assertions validate function behavior.
    """
    value = "abc123"

    assert not is_full_git_sha(value)


def test_is_full_git_sha_rejects_non_hex_characters() -> None:
    """Verify non-hexadecimal values are rejected.

    Returns:
        None: Assertions validate function behavior.
    """
    value = "z" * 40

    assert not is_full_git_sha(value)


def test_resolve_remote_ref_to_git_sha_returns_input_for_full_sha() -> None:
    """Verify resolver normalizes and returns full SHA inputs directly.

    Returns:
        None: Assertions validate function behavior.
    """
    source_sha = "ABCDEFABCDEFABCDEFABCDEFABCDEFABCDEFABCD"

    resolved_sha = resolve_remote_ref_to_git_sha(
        repository="https://github.com/CCBR/package1",
        source_ref=source_sha,
    )

    assert resolved_sha == source_sha.lower()


def test_resolve_remote_ref_to_git_sha_resolves_from_ls_remote() -> None:
    """Verify git ls-remote output is parsed into a commit SHA.

    Returns:
        None: Assertions validate function behavior.
    """
    expected_sha = "1" * 40
    fake_result = MagicMock(returncode=0, stdout=f"{expected_sha}\trefs/tags/v1.2.3\n")

    with patch("syncweaver.git.subprocess.run", return_value=fake_result):
        resolved_sha = resolve_remote_ref_to_git_sha(
            repository="https://github.com/CCBR/package1",
            source_ref="v1.2.3",
        )

    assert resolved_sha == expected_sha


def test_resolve_remote_ref_to_git_sha_raises_on_ls_remote_failure() -> None:
    """Verify non-zero git ls-remote exits raise RuntimeError.

    Returns:
        None: Assertions validate function behavior.
    """
    fake_result = MagicMock(returncode=128, stdout="")

    with (
        patch("syncweaver.git.subprocess.run", return_value=fake_result),
        pytest.raises(RuntimeError, match="git ls-remote failed"),
    ):
        resolve_remote_ref_to_git_sha(
            repository="https://github.com/CCBR/package1",
            source_ref="main",
        )


def test_resolve_remote_ref_to_git_sha_raises_when_output_has_no_sha() -> None:
    """Verify resolver fails when git ls-remote output does not contain SHA.

    Returns:
        None: Assertions validate function behavior.
    """
    fake_result = MagicMock(returncode=0, stdout="")

    with (
        patch("syncweaver.git.subprocess.run", return_value=fake_result),
        pytest.raises(ValueError, match="unable to resolve source_ref"),
    ):
        resolve_remote_ref_to_git_sha(
            repository="https://github.com/CCBR/package1",
            source_ref="main",
        )


def test_resolve_remote_ref_to_git_sha_propagates_timeout() -> None:
    """Verify resolver surfaces subprocess timeout from git ls-remote.

    Returns:
        None: Assertions validate function behavior.
    """
    with (
        patch(
            "syncweaver.git.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git ls-remote", timeout=30),
        ),
        pytest.raises(subprocess.TimeoutExpired),
    ):
        resolve_remote_ref_to_git_sha(
            repository="https://github.com/CCBR/package1",
            source_ref="main",
        )


def test_remote_ref_has_path_changes_returns_false_for_same_sha() -> None:
    """Verify path-change helper short-circuits for identical SHAs.

    Returns:
        None: Assertions validate function behavior.
    """
    unchanged_sha = "a" * 40

    has_changes = remote_ref_has_path_changes(
        repository="https://github.com/CCBR/package1",
        previous_git_sha=unchanged_sha,
        target_git_sha=unchanged_sha,
        remote_subdir="modules/hello",
    )

    assert not has_changes


def test_remote_ref_has_path_changes_scopes_diff_to_remote_subdir() -> None:
    """Verify helper reports changes using remote_subdir-scoped diff output.

    Returns:
        None: Assertions validate function behavior.
    """
    previous_sha = "1" * 40
    target_sha = "2" * 40
    observed_calls: list[list[str]] = []

    def _fake_run_git(args, cwd=None, env=None, redacted_values=None):
        del cwd, env, redacted_values
        observed_calls.append(args)
        output = ""
        if "diff" in args:
            output = "modules/hello/R/hello.R"
        return output

    with patch("syncweaver.git.run_git", side_effect=_fake_run_git):
        has_changes = remote_ref_has_path_changes(
            repository="https://github.com/CCBR/package1",
            previous_git_sha=previous_sha,
            target_git_sha=target_sha,
            remote_subdir="modules/hello",
        )

    assert has_changes
    assert any("diff" in call for call in observed_calls)
    diff_calls = [call for call in observed_calls if "diff" in call]
    assert diff_calls
    assert diff_calls[0][-1] == "modules/hello"


def test_remote_ref_has_path_changes_returns_true_when_previous_sha_unfetchable() -> (
    None
):
    """Verify helper reports changes without raising when previous_git_sha is gone.

    Simulates a previously tracked commit that is no longer reachable from any
    ref on the remote (e.g. its branch was rebased, force-pushed, or deleted),
    so fetching it directly fails. The diff should be skipped and the helper
    should conservatively report changes instead of raising.

    Returns:
        None: Assertions validate function behavior.
    """
    previous_sha = "1" * 40
    target_sha = "2" * 40
    observed_calls: list[list[str]] = []

    def _fake_run_git(args, cwd=None, env=None, redacted_values=None):
        del cwd, env, redacted_values
        observed_calls.append(args)
        if "fetch" in args and previous_sha in args:
            raise RuntimeError("Git command failed: fatal: no such remote ref")
        return ""

    with patch("syncweaver.git.run_git", side_effect=_fake_run_git):
        has_changes = remote_ref_has_path_changes(
            repository="https://github.com/CCBR/package1",
            previous_git_sha=previous_sha,
            target_git_sha=target_sha,
            remote_subdir="modules/hello",
        )

    assert has_changes
    assert not any("diff" in call for call in observed_calls)
    assert not any("fetch" in call and target_sha in call for call in observed_calls)


def test_git_commit_exists_returns_true_for_known_commit(tmp_path) -> None:
    """Verify commit-existence check succeeds for a commit present locally.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True
    )
    (repo_dir / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True)
    subprocess.run(
        ["git", "commit", "--no-verify", "-m", "init"], cwd=repo_dir, check=True
    )
    commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert git_commit_exists(repo_dir, commit_sha)


def test_git_commit_exists_returns_false_for_unknown_commit(tmp_path) -> None:
    """Verify commit-existence check fails for a commit absent locally.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True)

    assert not git_commit_exists(repo_dir, "f" * 40)
