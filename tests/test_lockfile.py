"""Tests for lockfile helper functions."""

from __future__ import annotations

import json

import pytest

from syncweaver.lockfile import (
    resolve_source_path_from_lockfile,
    resolve_source_paths_from_lockfile,
)


def test_resolve_source_path_uses_explicit_input(tmp_path):
    """Verify explicit source_path is returned as-is after trimming whitespace.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    lockfile_path = tmp_path / ".syncweaver-lock.json"
    lockfile_path.write_text("{}\n")

    resolved = resolve_source_path_from_lockfile(lockfile_path, "  code/package1  ")

    assert resolved == "code/package1"


def test_resolve_source_path_fails_when_lockfile_missing(tmp_path):
    """Verify missing lockfile raises a readable error when source_path is omitted.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    lockfile_path = tmp_path / ".syncweaver-lock.json"

    with pytest.raises(
        ValueError,
        match="lockfile does not exist and source_path was not provided",
    ):
        resolve_source_path_from_lockfile(lockfile_path, "")


def test_resolve_source_path_fails_when_no_sources(tmp_path):
    """Verify omitted source_path fails when lockfile has no tracked sources.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    lock_data = {
        "host": "CCBR/host-repo1",
        "orchestrator": "CCBR/syncweaver",
        "syncweaver_version": "0.0.1-dev",
        "sources": {},
    }
    lockfile_path = tmp_path / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    with pytest.raises(
        ValueError,
        match="no tracked sources found in lockfile and source_path was not provided",
    ):
        resolve_source_path_from_lockfile(lockfile_path, None)


def test_resolve_source_path_uses_single_tracked_source(tmp_path):
    """Verify omitted source_path resolves automatically for single-source lockfiles.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
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
            }
        },
    }
    lockfile_path = tmp_path / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    resolved = resolve_source_path_from_lockfile(lockfile_path, "")

    assert resolved == "code/package1"


def test_resolve_source_path_fails_when_multiple_sources(tmp_path):
    """Verify omitted source_path fails when multiple tracked sources exist.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
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
            },
            "code/package2": {
                "repo_url": "https://github.com/CCBR/package2",
                "ref": "main",
                "git_sha": "4b2f2d49a7a0e8e3db7a9d3b2ea73ff77d1f9b11",
            },
        },
    }
    lockfile_path = tmp_path / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    with pytest.raises(
        ValueError,
        match="lockfile tracks multiple sources",
    ):
        resolve_source_path_from_lockfile(lockfile_path, None)


def test_resolve_source_path_uses_repo_url_match(tmp_path):
    """Verify repo_url resolves source_path when multiple tracked sources exist.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
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
            },
            "code/package2": {
                "repo_url": "https://github.com/CCBR/package2",
                "ref": "main",
                "git_sha": "4b2f2d49a7a0e8e3db7a9d3b2ea73ff77d1f9b11",
            },
        },
    }
    lockfile_path = tmp_path / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    resolved = resolve_source_path_from_lockfile(
        lockfile_path,
        source_path="",
        repo_url="git@github.com:CCBR/package2.git",
    )

    assert resolved == "code/package2"


def test_resolve_source_path_uses_owner_repo_match(tmp_path):
    """Verify OWNER/REPO shorthand resolves against lockfile URL entries.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
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
            },
            "code/package2": {
                "repo_url": "https://github.com/CCBR/package2",
                "ref": "main",
                "git_sha": "4b2f2d49a7a0e8e3db7a9d3b2ea73ff77d1f9b11",
            },
        },
    }
    lockfile_path = tmp_path / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    resolved = resolve_source_path_from_lockfile(
        lockfile_path,
        source_path="",
        repo_url="CCBR/package2",
    )

    assert resolved == "code/package2"


def test_resolve_source_path_fails_when_repo_url_has_no_matches(tmp_path):
    """Verify repo_url lookup fails with a readable error when no sources match.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
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
            }
        },
    }
    lockfile_path = tmp_path / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    with pytest.raises(
        ValueError,
        match="no tracked sources matched repo_url",
    ):
        resolve_source_path_from_lockfile(
            lockfile_path,
            source_path=None,
            repo_url="https://github.com/CCBR/unknown",
        )


def test_resolve_source_path_fails_when_repo_url_matches_multiple(tmp_path):
    """Verify repo_url lookup fails when multiple source paths share same repo.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
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
            },
            "code/package1-alt": {
                "repo_url": "https://github.com/CCBR/package1",
                "ref": "main",
                "git_sha": "4b2f2d49a7a0e8e3db7a9d3b2ea73ff77d1f9b11",
            },
        },
    }
    lockfile_path = tmp_path / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    with pytest.raises(
        ValueError,
        match="multiple tracked sources matched repo_url",
    ):
        resolve_source_path_from_lockfile(
            lockfile_path,
            source_path="",
            repo_url="https://github.com/CCBR/package1",
        )


def test_resolve_source_paths_returns_all_repo_url_matches(tmp_path):
    """Verify multi-path resolver returns all paths matching repository URL.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
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
            },
            "code/package1-alt": {
                "repo_url": "git@github.com:CCBR/package1.git",
                "ref": "main",
                "git_sha": "4b2f2d49a7a0e8e3db7a9d3b2ea73ff77d1f9b11",
            },
            "code/package2": {
                "repo_url": "https://github.com/CCBR/package2",
                "ref": "main",
                "git_sha": "5c3f2d49a7a0e8e3db7a9d3b2ea73ff77d1f9b12",
            },
        },
    }
    lockfile_path = tmp_path / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    resolved = resolve_source_paths_from_lockfile(
        lockfile=lockfile_path,
        source_path="",
        repo_url="CCBR/package1",
    )

    assert resolved == ["code/package1", "code/package1-alt"]
