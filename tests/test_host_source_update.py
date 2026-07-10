"""Tests for update-host-source-direct workflow helper functions."""

from __future__ import annotations

import json
import subprocess

import pytest

from syncweaver.host_source_update import (
    build_source_update_branch_name,
    format_source_paths_markdown,
    resolve_app_owner,
    resolve_source_paths_for_host_update,
    select_source_paths_for_update,
)
import syncweaver.host_source_update as host_source_update


@pytest.fixture(autouse=True)
def _mock_source_ref_sha_resolution(monkeypatch) -> None:
    """Keep host-source-update tests offline by default.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Resolver is patched for test isolation.
    """

    monkeypatch.setattr(
        host_source_update,
        "resolve_remote_ref_to_git_sha",
        lambda repository, source_ref: source_ref,
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
        "host": "NIDAP/MOSuite-create",
        "orchestrator": "CCBR/syncweaver-orchestrator",
        "syncweaver_version": "0.0.1-dev",
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

    assert branch_name == "syncweaver/update/https-github.com-CCBR-package1"


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
        "host": "NIDAP/MOSuite-create",
        "orchestrator": "CCBR/syncweaver-orchestrator",
        "syncweaver_version": "0.0.1-dev",
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
        lambda entry_script, repository, release_tag, previous_tag, remote_subdir=None, functracer_backend=None, functracer_image_tag=None: (
            False
        ),
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
        "host": "NIDAP/MOSuite-create",
        "orchestrator": "CCBR/syncweaver-orchestrator",
        "syncweaver_version": "0.0.1-dev",
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

    def _record_release_impact(
        entry_script,
        repository,
        release_tag,
        previous_tag,
        remote_subdir=None,
        functracer_backend=None,
        functracer_image_tag=None,
    ):
        del remote_subdir
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
        "host": "NIDAP/MOSuite-create",
        "orchestrator": "CCBR/syncweaver-orchestrator",
        "syncweaver_version": "0.0.1-dev",
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

    def _record_release_impact(
        entry_script,
        repository,
        release_tag,
        previous_tag,
        remote_subdir=None,
        functracer_backend=None,
        functracer_image_tag=None,
    ):
        del remote_subdir
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
        "host": "NIDAP/MOSuite-create",
        "orchestrator": "CCBR/syncweaver-orchestrator",
        "syncweaver_version": "0.0.1-dev",
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
        "host": "NIDAP/MOSuite-create",
        "orchestrator": "CCBR/syncweaver-orchestrator",
        "syncweaver_version": "0.0.1-dev",
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


def test_select_source_paths_for_update_uses_resolved_git_shas_for_analysis(
    tmp_path, monkeypatch
) -> None:
    """Verify gating analysis compares resolved and previous commit SHAs.

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

    previous_sha = "1111111111111111111111111111111111111111"
    candidate_sha = "2222222222222222222222222222222222222222"
    lock_data = {
        "host": "NIDAP/MOSuite-create",
        "orchestrator": "CCBR/syncweaver-orchestrator",
        "syncweaver_version": "0.0.1-dev",
        "sources": {
            "code/package1": {
                "repo_url": "https://github.com/CCBR/package1",
                "ref": "main",
                "git_sha": previous_sha,
                "remote_subdir": "modules/package1",
            }
        },
    }
    lockfile_path = host_repo / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    monkeypatch.setattr(
        host_source_update,
        "resolve_remote_ref_to_git_sha",
        lambda repository, source_ref: candidate_sha,
    )

    observed_release_tag = ""
    observed_previous_tag = ""
    observed_remote_subdir = ""

    def _record_release_impact(
        entry_script,
        repository,
        release_tag,
        previous_tag,
        remote_subdir=None,
        functracer_backend=None,
        functracer_image_tag=None,
    ):
        del (
            entry_script,
            repository,
            functracer_backend,
            functracer_image_tag,
        )
        nonlocal observed_release_tag, observed_previous_tag
        nonlocal observed_remote_subdir
        observed_release_tag = release_tag
        observed_previous_tag = previous_tag
        if remote_subdir is not None:
            observed_remote_subdir = remote_subdir
        return True

    monkeypatch.setattr(
        host_source_update,
        "run_functracer_release_impact",
        _record_release_impact,
    )

    selected, skipped = select_source_paths_for_update(
        source_paths=["code/package1"],
        lockfile_path=lockfile_path,
        source_ref_input="main",
        host_repo_path=host_repo,
        functracer_entry_scripts_input="main.R",
        functracer_source_paths_input="",
    )

    assert selected == ["code/package1"]
    assert skipped == []
    assert observed_release_tag == candidate_sha
    assert observed_previous_tag == previous_sha
    assert observed_remote_subdir == "modules/package1"


def test_select_source_paths_for_update_skips_when_target_sha_matches_current(
    tmp_path, monkeypatch
) -> None:
    """Verify updates are skipped when source_ref resolves to current git_sha.

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

    unchanged_sha = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    lock_data = {
        "host": "NIDAP/MOSuite-create",
        "orchestrator": "CCBR/syncweaver-orchestrator",
        "syncweaver_version": "0.0.1-dev",
        "sources": {
            "code/package1": {
                "repo_url": "https://github.com/CCBR/package1",
                "ref": "main",
                "git_sha": unchanged_sha,
            }
        },
    }
    lockfile_path = host_repo / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    monkeypatch.setattr(
        host_source_update,
        "resolve_remote_ref_to_git_sha",
        lambda repository, source_ref: unchanged_sha,
    )

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
        source_ref_input="main",
        host_repo_path=host_repo,
        functracer_entry_scripts_input="main.R",
        functracer_source_paths_input="",
    )

    assert selected == []
    assert skipped == ["code/package1"]


def test_select_source_paths_for_update_skips_when_tracked_subdir_unchanged(
    tmp_path, monkeypatch
) -> None:
    """Verify updates are skipped when the tracked remote_subdir has no changes.

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

    previous_sha = "1111111111111111111111111111111111111111"
    candidate_sha = "2222222222222222222222222222222222222222"
    lock_data = {
        "host": "NIDAP/MOSuite-create",
        "orchestrator": "CCBR/syncweaver-orchestrator",
        "syncweaver_version": "0.0.1-dev",
        "sources": {
            "code/package1": {
                "repo_url": "https://github.com/CCBR/package1",
                "ref": "main",
                "git_sha": previous_sha,
                "remote_subdir": "modules/package1",
            }
        },
    }
    lockfile_path = host_repo / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    monkeypatch.setattr(
        host_source_update,
        "resolve_remote_ref_to_git_sha",
        lambda repository, source_ref: candidate_sha,
    )
    monkeypatch.setattr(
        host_source_update,
        "remote_ref_has_path_changes",
        lambda repository, previous_git_sha, target_git_sha, remote_subdir: False,
    )

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
        source_ref_input="plot-heatmap",
        host_repo_path=host_repo,
        functracer_entry_scripts_input="main.R",
        functracer_source_paths_input="",
    )

    assert selected == []
    assert skipped == ["code/package1"]


def test_select_source_paths_for_update_warns_and_keeps_path_on_analysis_failure(
    tmp_path, monkeypatch, capsys
) -> None:
    """Verify analysis failures emit warnings and keep path selected.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.
        capsys: Pytest stdout/stderr capture fixture.

    Returns:
        None: Assertions validate warning visibility and fallback behavior.
    """
    host_repo = tmp_path / "host-repo"
    host_repo.mkdir()

    source_root = host_repo / "code" / "hello"
    source_root.mkdir(parents=True)
    (source_root / "DESCRIPTION").write_text("Package: hello\n")
    (source_root / "R").mkdir()

    entry_script = host_repo / "code" / "main.R"
    entry_script.parent.mkdir(parents=True, exist_ok=True)
    entry_script.write_text("hello::hello_message('world')\n")

    previous_sha = "0" * 40
    candidate_sha = "1" * 40
    lock_data = {
        "host": "demo-syncweaver-host-capsule",
        "orchestrator": "CCBR/syncweaver-orchestrator",
        "syncweaver_version": "0.0.1-dev",
        "sources": {
            "code/hello": {
                "repo_url": "https://github.com/NIDAP-Community/demo-syncweaver-source-monorepo",
                "ref": "v0.2.0",
                "git_sha": previous_sha,
                "remote_subdir": "modules/hello",
            }
        },
    }
    lockfile_path = host_repo / ".syncweaver-lock.json"
    lockfile_path.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    monkeypatch.setattr(
        host_source_update,
        "resolve_remote_ref_to_git_sha",
        lambda repository, source_ref: candidate_sha,
    )
    monkeypatch.setattr(
        host_source_update,
        "remote_ref_has_path_changes",
        lambda repository, previous_git_sha, target_git_sha, remote_subdir: True,
    )

    def _raise_subprocess_error(*args, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=["Rscript", "functracer_release_impact.R"],
            stderr="functracer failed in analysis",
            output="",
        )

    monkeypatch.setattr(
        host_source_update,
        "run_functracer_release_impact",
        _raise_subprocess_error,
    )

    selected, skipped = select_source_paths_for_update(
        source_paths=["code/hello"],
        lockfile_path=lockfile_path,
        source_ref_input="plot-heatmap",
        host_repo_path=host_repo,
        functracer_entry_scripts_input="code/main.R",
        functracer_source_paths_input="",
    )
    captured = capsys.readouterr()

    assert selected == ["code/hello"]
    assert skipped == []
    assert "::warning::functracer analysis failed for source_path=code/hello" in (
        captured.out
    )
    assert "functracer failed in analysis" in captured.out
    assert "Warning: functracer analysis failed for source_path=code/hello" in (
        captured.err
    )
