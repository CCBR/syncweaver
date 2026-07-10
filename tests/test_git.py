"""Tests for shared git helper utilities."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from syncweaver.git import (
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

    with patch("syncweaver.git.subprocess.run", return_value=fake_result):
        with pytest.raises(RuntimeError, match="git ls-remote failed"):
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

    with patch("syncweaver.git.subprocess.run", return_value=fake_result):
        with pytest.raises(ValueError, match="unable to resolve source_ref"):
            resolve_remote_ref_to_git_sha(
                repository="https://github.com/CCBR/package1",
                source_ref="main",
            )


def test_resolve_remote_ref_to_git_sha_propagates_timeout() -> None:
    """Verify resolver surfaces subprocess timeout from git ls-remote.

    Returns:
        None: Assertions validate function behavior.
    """
    with patch(
        "syncweaver.git.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="git ls-remote", timeout=30),
    ):
        with pytest.raises(subprocess.TimeoutExpired):
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
