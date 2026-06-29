"""Tests for update-host-source-direct workflow helper functions."""

from __future__ import annotations

import json

import pytest

from syncweaver.host_source_update import (
    build_source_update_branch_name,
    format_source_paths_markdown,
    resolve_app_owner,
    resolve_source_paths_for_host_update,
    select_source_paths_for_update,
)
import syncweaver.host_source_update as host_source_update


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


def test_select_source_paths_for_update_skips_unaffected_r_package(
    tmp_path, monkeypatch
) -> None:
    """Verify unaffected R package paths are skipped when functracer says false.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    host_repo = tmp_path / "host-repo"
    host_repo.mkdir()

    source_root = host_repo / "code" / "package1"
    source_root.mkdir(parents=True)
    (source_root / "DESCRIPTION").write_text("Package: package1\n")
    (source_root / "R").mkdir()

    entry_script = host_repo / "main.R"
    entry_script.write_text("run <- function() package1_fn()\n")

    lock_data = {
        "name": "NIDAP/MOSuite-create",
        "homePage": "https://github.com/NIDAP/MOSuite-create",
        "sources": {
            "code/package1": {
                "repo_url": "https://github.com/CCBR/package1",
                "ref": "v1.0.0",
                "git_sha": "1111111111111111111111111111111111111111",
            }
        },
    }
    lockfile_path = host_repo / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    monkeypatch.setattr(
        host_source_update,
        "run_functracer_release_impact",
        lambda entry_script, repository, release_tag, previous_tag: False,
    )

    selected, skipped = select_source_paths_for_update(
        source_paths=["code/package1"],
        lockfile_path=lockfile_path,
        source_ref_input="v1.1.0",
        host_repo_path=host_repo,
        functracer_entry_scripts_input="main.R",
        functracer_source_paths_input="",
    )

    assert selected == []
    assert skipped == ["code/package1"]


def test_select_source_paths_for_update_prefers_code_main_r(
    tmp_path, monkeypatch
) -> None:
    """Verify functracer defaults to code/main.R when no override is given.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    host_repo = tmp_path / "host-repo"
    host_repo.mkdir()

    source_root = host_repo / "code" / "package1"
    source_root.mkdir(parents=True)
    (source_root / "DESCRIPTION").write_text("Package: package1\n")
    (source_root / "R").mkdir()

    preferred_script = host_repo / "code" / "main.R"
    preferred_script.parent.mkdir(parents=True, exist_ok=True)
    preferred_script.write_text("run <- function() package1_fn()\n")

    lock_data = {
        "name": "NIDAP/MOSuite-create",
        "homePage": "https://github.com/NIDAP/MOSuite-create",
        "sources": {
            "code/package1": {
                "repo_url": "https://github.com/CCBR/package1",
                "ref": "v1.0.0",
                "git_sha": "1111111111111111111111111111111111111111",
            }
        },
    }
    lockfile_path = host_repo / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    called_scripts: list[str] = []

    def _record_release_impact(entry_script, repository, release_tag, previous_tag):
        called_scripts.append(entry_script.relative_to(host_repo).as_posix())
        return False

    monkeypatch.setattr(
        host_source_update,
        "run_functracer_release_impact",
        _record_release_impact,
    )

    selected, skipped = select_source_paths_for_update(
        source_paths=["code/package1"],
        lockfile_path=lockfile_path,
        source_ref_input="v1.1.0",
        host_repo_path=host_repo,
        functracer_entry_scripts_input="",
        functracer_source_paths_input="",
    )

    assert selected == []
    assert skipped == ["code/package1"]
    assert called_scripts == ["code/main.R"]


def test_select_source_paths_for_update_honors_explicit_entry_script_override(
    tmp_path, monkeypatch
) -> None:
    """Verify explicit functracer entry scripts override the default main.R.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    host_repo = tmp_path / "host-repo"
    host_repo.mkdir()

    source_root = host_repo / "code" / "package1"
    source_root.mkdir(parents=True)
    (source_root / "DESCRIPTION").write_text("Package: package1\n")
    (source_root / "R").mkdir()

    preferred_script = host_repo / "code" / "main.R"
    preferred_script.parent.mkdir(parents=True, exist_ok=True)
    preferred_script.write_text("run <- function() package1_fn()\n")

    override_script = host_repo / "custom-entry.R"
    override_script.write_text("run <- function() package1_fn()\n")

    lock_data = {
        "name": "NIDAP/MOSuite-create",
        "homePage": "https://github.com/NIDAP/MOSuite-create",
        "sources": {
            "code/package1": {
                "repo_url": "https://github.com/CCBR/package1",
                "ref": "v1.0.0",
                "git_sha": "1111111111111111111111111111111111111111",
            }
        },
    }
    lockfile_path = host_repo / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    called_scripts: list[str] = []

    def _record_release_impact(entry_script, repository, release_tag, previous_tag):
        called_scripts.append(entry_script.relative_to(host_repo).as_posix())
        return False

    monkeypatch.setattr(
        host_source_update,
        "run_functracer_release_impact",
        _record_release_impact,
    )

    selected, skipped = select_source_paths_for_update(
        source_paths=["code/package1"],
        lockfile_path=lockfile_path,
        source_ref_input="v1.1.0",
        host_repo_path=host_repo,
        functracer_entry_scripts_input="custom-entry.R",
        functracer_source_paths_input="",
    )

    assert selected == []
    assert skipped == ["code/package1"]
    assert called_scripts == ["custom-entry.R"]


def test_select_source_paths_for_update_keeps_non_r_package_without_analysis(
    tmp_path,
) -> None:
    """Verify non-R sources are still selected when functracer inputs are present.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    host_repo = tmp_path / "host-repo"
    host_repo.mkdir()
    source_root = host_repo / "code" / "package1"
    source_root.mkdir(parents=True)
    (source_root / "README.md").write_text("not an R package\n")

    lock_data = {
        "name": "NIDAP/MOSuite-create",
        "homePage": "https://github.com/NIDAP/MOSuite-create",
        "sources": {
            "code/package1": {
                "repo_url": "https://github.com/CCBR/package1",
                "ref": "v1.0.0",
                "git_sha": "1111111111111111111111111111111111111111",
            }
        },
    }
    lockfile_path = host_repo / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    selected, skipped = select_source_paths_for_update(
        source_paths=["code/package1"],
        lockfile_path=lockfile_path,
        source_ref_input="v1.1.0",
        host_repo_path=host_repo,
        functracer_entry_scripts_input="main.R",
        functracer_source_paths_input="",
    )

    assert selected == ["code/package1"]
    assert skipped == []


def test_select_source_paths_for_update_skips_functracer_without_host_scripts(
    tmp_path, monkeypatch
) -> None:
    """Verify host-level gating bypasses functracer when no valid entry script exists.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate function behavior.
    """
    host_repo = tmp_path / "host-repo"
    host_repo.mkdir()

    source_root = host_repo / "code" / "package1"
    source_root.mkdir(parents=True)
    (source_root / "DESCRIPTION").write_text("Package: package1\n")
    (source_root / "R").mkdir()

    lock_data = {
        "name": "NIDAP/MOSuite-create",
        "homePage": "https://github.com/NIDAP/MOSuite-create",
        "sources": {
            "code/package1": {
                "repo_url": "https://github.com/CCBR/package1",
                "ref": "v1.0.0",
                "git_sha": "1111111111111111111111111111111111111111",
            }
        },
    }
    lockfile_path = host_repo / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    def _raise_if_called(*args, **kwargs):
        raise AssertionError("run_functracer_release_impact should not be called")

    monkeypatch.setattr(
        host_source_update,
        "run_functracer_release_impact",
        _raise_if_called,
    )

    selected, skipped = select_source_paths_for_update(
        source_paths=["code/package1"],
        lockfile_path=lockfile_path,
        source_ref_input="v1.1.0",
        host_repo_path=host_repo,
        functracer_entry_scripts_input="missing_entry.R",
        functracer_source_paths_input="",
    )

    assert selected == ["code/package1"]
    assert skipped == []
