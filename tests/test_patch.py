"""Tests for the syncweaver patch subcommands."""

from __future__ import annotations

import json
import pathlib
import subprocess

import pytest
from click.testing import CliRunner

from syncweaver.cli import cli
from syncweaver.patch import _validate_patch_structure


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

    (path / "README.md").write_text("# test repo\n")
    _run(["git", "add", "README.md"], cwd=path)
    _run(["git", "commit", "--no-verify", "-m", "init"], cwd=path)


def _setup_source_and_host(tmp_path, monkeypatch):
    """Create source and host git repos and vendor source into host."""
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
    return source_repo, host_repo


def test_patch_create_generates_file_and_updates_lockfile(tmp_path, monkeypatch):
    """Verify patch creation writes diff content and lockfile patch metadata.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    source_repo, host_repo = _setup_source_and_host(tmp_path, monkeypatch)
    vendored_file = host_repo / "code/package1/pkg.py"
    vendored_file.write_text("VALUE = 2\n")

    runner = CliRunner()
    result = runner.invoke(
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

    assert result.exit_code == 0
    patch_file = host_repo / "code/package1/.syncweaver/code-package1.diff"
    assert patch_file.exists()
    patch_text = patch_file.read_text()
    assert "--- a/pkg.py" in patch_text
    assert "+++ b/pkg.py" in patch_text
    assert "+VALUE = 2" in patch_text

    lock_data = json.loads((host_repo / ".syncweaver-lock.json").read_text())
    source_entry = lock_data["sources"]["code/package1"]
    assert source_entry["repo_url"] == str(source_repo)
    assert source_entry["patch"] == "code/package1/.syncweaver/code-package1.diff"
    audit = source_entry["patch_audit"]["code/package1/.syncweaver/code-package1.diff"]
    assert audit["status"] == "local"
    assert "pr_url" not in audit
    assert "reason" not in audit


def test_patch_list_shows_tracked_patch_for_source_path(tmp_path, monkeypatch):
    """Verify patch listing prints tracked patch rows for a source path.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    source_repo, host_repo = _setup_source_and_host(tmp_path, monkeypatch)
    (host_repo / "code/package1/pkg.py").write_text("VALUE = 2\n")

    runner = CliRunner()
    create_result = runner.invoke(
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
    assert create_result.exit_code == 0

    list_result = runner.invoke(
        cli,
        [
            "patch",
            "list",
            "--path",
            "code/package1",
        ],
    )

    assert list_result.exit_code == 0
    assert str(source_repo) in list_result.output
    assert "code/package1/.syncweaver/code-package1.diff" in list_result.output


def test_patch_annotate_rejected_stores_audit_metadata(tmp_path, monkeypatch):
    """Verify rejected patch annotation is persisted in lockfile audit metadata.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    source_repo, host_repo = _setup_source_and_host(tmp_path, monkeypatch)
    (host_repo / "code/package1/pkg.py").write_text("VALUE = 2\n")

    runner = CliRunner()
    create_result = runner.invoke(
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
    assert create_result.exit_code == 0

    annotate_result = runner.invoke(
        cli,
        [
            "patch",
            "annotate-rejected",
            "--patch",
            "code/package1/.syncweaver/code-package1.diff",
            "--pr-url",
            "https://github.com/ccbr/source/pull/42",
            "--reason",
            "upstream declined behavior change",
        ],
    )

    assert annotate_result.exit_code == 0
    lock_data = json.loads((host_repo / ".syncweaver-lock.json").read_text())
    source_entry = lock_data["sources"]["code/package1"]
    audit = source_entry["patch_audit"]["code/package1/.syncweaver/code-package1.diff"]
    assert audit["status"] == "rejected"
    assert audit["pr_url"] == "https://github.com/ccbr/source/pull/42"
    assert audit["reason"] == "upstream declined behavior change"
    assert "annotated_at" in audit


def test_patch_mark_status_records_accepted_metadata(tmp_path, monkeypatch):
    """Verify generic status marking records accepted patch metadata.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    source_repo, host_repo = _setup_source_and_host(tmp_path, monkeypatch)
    (host_repo / "code/package1/pkg.py").write_text("VALUE = 2\n")

    runner = CliRunner()
    create_result = runner.invoke(
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
    assert create_result.exit_code == 0

    mark_result = runner.invoke(
        cli,
        [
            "patch",
            "mark-status",
            "--patch",
            "code/package1/.syncweaver/code-package1.diff",
            "--status",
            "accepted",
            "--pr-url",
            "https://github.com/ccbr/source/pull/42",
        ],
    )

    assert mark_result.exit_code == 0
    lock_data = json.loads((host_repo / ".syncweaver-lock.json").read_text())
    source_entry = lock_data["sources"]["code/package1"]
    audit = source_entry["patch_audit"]["code/package1/.syncweaver/code-package1.diff"]
    assert audit["status"] == "accepted"
    assert audit["pr_url"] == "https://github.com/ccbr/source/pull/42"
    assert "reason" not in audit


def test_patch_mark_status_rejected_requires_reason(tmp_path, monkeypatch):
    """Verify rejected status enforces a free-text reason.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    source_repo, _host_repo = _setup_source_and_host(tmp_path, monkeypatch)
    (pathlib.Path.cwd() / "code/package1/pkg.py").write_text("VALUE = 2\n")

    runner = CliRunner()
    create_result = runner.invoke(
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
    assert create_result.exit_code == 0

    mark_result = runner.invoke(
        cli,
        [
            "patch",
            "mark-status",
            "--patch",
            "code/package1/.syncweaver/code-package1.diff",
            "--status",
            "rejected",
            "--pr-url",
            "https://github.com/ccbr/source/pull/42",
        ],
    )

    assert mark_result.exit_code != 0
    assert "requires a non-empty reason" in mark_result.output


def test_patch_structure_validation_rejects_missing_plus_header():
    """Verify patch validation rejects file sections missing `+++` headers.

    Returns:
        None: Assertions validate function behavior.
    """
    bad_patch = "--- a/pkg.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
    with pytest.raises(RuntimeError, match=r"missing matching '\+\+\+ '"):
        _validate_patch_structure(bad_patch)


def test_patch_structure_validation_rejects_missing_hunk():
    """Verify patch validation rejects file sections without hunks.

    Returns:
        None: Assertions validate function behavior.
    """
    bad_patch = "--- a/pkg.py\n+++ b/pkg.py\n"
    with pytest.raises(RuntimeError, match="missing '@@' hunks"):
        _validate_patch_structure(bad_patch)


def test_patch_create_reports_validation_failure(tmp_path, monkeypatch):
    """Verify CLI surfaces structural validation failures during patch creation.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    source_repo, host_repo = _setup_source_and_host(tmp_path, monkeypatch)
    (host_repo / "code/package1/pkg.py").write_text("VALUE = 2\n")

    import syncweaver.patch as patch_module

    def _bad_structure(_patch_text: str) -> None:
        raise RuntimeError("Generated patch has invalid structure: synthetic failure")

    monkeypatch.setattr(patch_module, "_validate_patch_structure", _bad_structure)

    runner = CliRunner()
    result = runner.invoke(
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

    assert result.exit_code != 0
    assert "Generated patch has invalid structure" in result.output


def test_patch_create_uses_remote_subdir_baseline(tmp_path, monkeypatch):
    """Verify patch creation compares vendored files to tracked remote_subdir.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    source_repo = tmp_path / "source"
    source_repo.mkdir()
    _init_git_repo(source_repo)
    package_root = source_repo / "subprojects/package1"
    package_root.mkdir(parents=True)
    (package_root / "pkg.py").write_text("VALUE = 1\n")
    _run(["git", "add", "subprojects/package1/pkg.py"], cwd=source_repo)
    _run(["git", "commit", "--no-verify", "-m", "add nested package"], cwd=source_repo)

    host_repo = tmp_path / "host"
    host_repo.mkdir()
    _init_git_repo(host_repo)
    monkeypatch.chdir(host_repo)

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
            "--remote-subdir",
            "subprojects/package1",
        ],
    )
    assert add_result.exit_code == 0

    (host_repo / "code/package1/pkg.py").write_text("VALUE = 2\n")
    create_result = runner.invoke(
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

    assert create_result.exit_code == 0
    patch_file = host_repo / "code/package1/.syncweaver/code-package1.diff"
    patch_text = patch_file.read_text()
    assert "--- a/pkg.py" in patch_text
    assert "+++ b/pkg.py" in patch_text
    assert "+VALUE = 2" in patch_text
