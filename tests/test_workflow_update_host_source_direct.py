"""Tests for update-host-source-direct workflow helper functions."""

from __future__ import annotations

import json

import pytest

from syncweaver.workflow_update_host_source_direct import (
    build_source_update_branch_name,
    format_source_paths_markdown,
    resolve_app_owner,
    resolve_source_paths_for_host_update,
)


def test_resolve_app_owner_prefers_explicit_owner() -> None:
    """Verify explicit app owner input takes precedence over host repository.

    Returns:
        None: Assertions validate function behavior.
    """
    owner = resolve_app_owner("NIDAP/MOSuite-create", "CCBR")

    assert owner == "CCBR"


def test_resolve_app_owner_derives_from_host_repository() -> None:
    """Verify app owner derives from OWNER/REPO when override is not provided.

    Returns:
        None: Assertions validate function behavior.
    """
    owner = resolve_app_owner("NIDAP/MOSuite-create", "")

    assert owner == "NIDAP"


def test_resolve_app_owner_fails_for_invalid_host_repository() -> None:
    """Verify invalid host repository input raises a readable error.

    Returns:
        None: Assertions validate function behavior.
    """
    with pytest.raises(ValueError, match="host_repository must be in OWNER/REPO"):
        resolve_app_owner("invalid-host", None)


def test_resolve_source_paths_for_host_update_matches_repo_url(tmp_path) -> None:
    """Verify workflow helper resolves all tracked paths for a source repository.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    lock_data = {
        "name": "NIDAP/MOSuite-create",
        "homePage": "https://github.com/NIDAP/MOSuite-create",
        "sources": {
            "code/package1": {
                "repo_url": "https://github.com/CCBR/package1",
                "ref": "main",
                "git_sha": "1111111111111111111111111111111111111111",
            },
            "code/package1-alt": {
                "repo_url": "git@github.com:CCBR/package1.git",
                "ref": "main",
                "git_sha": "2222222222222222222222222222222222222222",
            },
            "code/package2": {
                "repo_url": "https://github.com/CCBR/package2",
                "ref": "main",
                "git_sha": "3333333333333333333333333333333333333333",
            },
        },
    }
    lockfile_path = tmp_path / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    resolved = resolve_source_paths_for_host_update(
        lockfile_path=lockfile_path,
        source_path_input="",
        source_repository_input="CCBR/package1",
    )

    assert resolved == ["code/package1", "code/package1-alt"]


def test_resolve_source_paths_for_host_update_prefers_explicit_source_path(
    tmp_path,
) -> None:
    """Verify explicit source path bypasses lockfile repository matching.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    lockfile_path = tmp_path / ".syncweaver-lock.json"
    lockfile_path.write_text("{}\n")

    resolved = resolve_source_paths_for_host_update(
        lockfile_path=lockfile_path,
        source_path_input=" code/selected ",
        source_repository_input="CCBR/package1",
    )

    assert resolved == ["code/selected"]


def test_format_source_paths_markdown_renders_bullets() -> None:
    """Verify source path markdown formatter emits one bullet per source path.

    Returns:
        None: Assertions validate function behavior.
    """
    rendered = format_source_paths_markdown(["code/package1", "code/package2"])

    assert rendered == "- `code/package1`\n- `code/package2`"


def test_build_source_update_branch_name_sanitizes_repository() -> None:
    """Verify branch name helper sanitizes invalid branch characters.

    Returns:
        None: Assertions validate function behavior.
    """
    branch_name = build_source_update_branch_name("https://github.com/CCBR/package1")

    assert branch_name == "syncweaver/update-source/https-github.com-CCBR-package1"
