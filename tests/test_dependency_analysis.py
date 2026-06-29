"""Tests for dependency analysis helpers."""

from __future__ import annotations

import pathlib

import pytest

import syncweaver.dependency_analysis as dependency_analysis
from syncweaver.dependency_analysis import (
    analyze_source_dependencies,
    detect_source_type,
    discover_host_entry_scripts,
    find_host_scripts_calling_source,
    is_r_package_source,
)


def test_is_r_package_source_detects_description_and_r_dir(
    tmp_path: pathlib.Path,
) -> None:
    """Verify R package detection requires DESCRIPTION and R directory.

    Args:
        tmp_path (pathlib.Path): Temporary directory fixture.

    Returns:
        None: Assertions validate helper behavior.
    """
    host_repo_path = tmp_path / "host-repo"
    host_repo_path.mkdir()
    source_root = host_repo_path / "code" / "package1"
    source_root.mkdir(parents=True)
    (source_root / "DESCRIPTION").write_text("Package: package1\n", encoding="utf-8")
    (source_root / "R").mkdir()

    detected = is_r_package_source(
        host_repo_path=host_repo_path, source_path="code/package1"
    )

    assert detected is True


def test_detect_source_type_returns_python_package(tmp_path: pathlib.Path) -> None:
    """Verify source type detection supports Python package identification.

    Args:
        tmp_path (pathlib.Path): Temporary directory fixture.

    Returns:
        None: Assertions validate helper behavior.
    """
    host_repo_path = tmp_path / "host-repo"
    host_repo_path.mkdir()
    source_root = host_repo_path / "code" / "py-package"
    source_root.mkdir(parents=True)
    (source_root / "pyproject.toml").write_text(
        "[project]\nname='py-package'\n", encoding="utf-8"
    )
    (source_root / "module.py").write_text(
        "def run():\n    return 1\n", encoding="utf-8"
    )

    detected = detect_source_type(
        host_repo_path=host_repo_path, source_path="code/py-package"
    )

    assert detected == "python_package"


def test_find_host_scripts_calling_source_discovers_scripts(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify host R script discovery and package call detection integration.

    Args:
        tmp_path (pathlib.Path): Temporary directory fixture.
        monkeypatch (pytest.MonkeyPatch): Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate helper behavior.
    """
    host_repo_path = tmp_path / "host-repo"
    host_repo_path.mkdir()

    source_root = host_repo_path / "code" / "package1"
    source_root.mkdir(parents=True)
    (source_root / "DESCRIPTION").write_text("Package: package1\n", encoding="utf-8")
    (source_root / "R").mkdir()
    (source_root / "R" / "core.R").write_text(
        "core_fn <- function(x) x\n", encoding="utf-8"
    )

    main_script = host_repo_path / "main.R"
    main_script.write_text("run <- function() core_fn(1)\n", encoding="utf-8")
    unrelated_script = host_repo_path / "other.R"
    unrelated_script.write_text("x <- 1\n", encoding="utf-8")

    monkeypatch.setattr(
        dependency_analysis,
        "_script_calls_r_package",
        lambda entry_script, package_dir, functracer_image_tag=None: (
            entry_script.name == "main.R"
        ),
    )

    detected = find_host_scripts_calling_source(
        host_repo_path=host_repo_path,
        source_path="code/package1",
        candidate_scripts=None,
    )

    assert detected == ["main.R"]


def test_discover_host_entry_scripts_prefers_code_main_r(
    tmp_path: pathlib.Path,
) -> None:
    """Verify host entry discovery prefers code/main.R when present.

    Args:
        tmp_path (pathlib.Path): Temporary directory fixture.

    Returns:
        None: Assertions validate helper behavior.
    """
    host_repo_path = tmp_path / "host-repo"
    host_repo_path.mkdir()

    preferred_script = host_repo_path / "code" / "main.R"
    preferred_script.parent.mkdir(parents=True)
    preferred_script.write_text("run <- function() 1\n", encoding="utf-8")

    fallback_script = host_repo_path / "main.R"
    fallback_script.write_text("run <- function() 2\n", encoding="utf-8")

    detected = discover_host_entry_scripts(
        host_repo_path=host_repo_path,
        source_paths=["code/package1"],
        candidate_scripts=None,
    )

    assert detected == ["code/main.R"]


def test_discover_host_entry_scripts_honors_explicit_override(
    tmp_path: pathlib.Path,
) -> None:
    """Verify host entry discovery respects explicit script overrides.

    Args:
        tmp_path (pathlib.Path): Temporary directory fixture.

    Returns:
        None: Assertions validate helper behavior.
    """
    host_repo_path = tmp_path / "host-repo"
    host_repo_path.mkdir()

    preferred_script = host_repo_path / "code" / "main.R"
    preferred_script.parent.mkdir(parents=True)
    preferred_script.write_text("run <- function() 1\n", encoding="utf-8")

    override_script = host_repo_path / "custom-entry.R"
    override_script.write_text("run <- function() 3\n", encoding="utf-8")

    detected = discover_host_entry_scripts(
        host_repo_path=host_repo_path,
        source_paths=["code/package1"],
        candidate_scripts=["custom-entry.R"],
    )

    assert detected == ["custom-entry.R"]


def test_analyze_source_dependencies_reports_release_impact(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify unified analyzer response includes release impact script buckets.

    Args:
        tmp_path (pathlib.Path): Temporary directory fixture.
        monkeypatch (pytest.MonkeyPatch): Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate helper behavior.
    """
    host_repo_path = tmp_path / "host-repo"
    host_repo_path.mkdir()

    source_root = host_repo_path / "code" / "package1"
    source_root.mkdir(parents=True)
    (source_root / "DESCRIPTION").write_text("Package: package1\n", encoding="utf-8")
    (source_root / "R").mkdir()

    script_path = host_repo_path / "main.R"
    script_path.write_text("run <- function() core_fn(1)\n", encoding="utf-8")

    monkeypatch.setattr(
        dependency_analysis,
        "find_host_scripts_calling_source",
        lambda host_repo_path, source_path, candidate_scripts=None, functracer_image_tag=None: [
            "main.R"
        ],
    )
    monkeypatch.setattr(
        dependency_analysis,
        "run_functracer_release_impact",
        lambda entry_script, repository, release_tag, previous_tag, functracer_image_tag=None: (
            True
        ),
    )

    result = analyze_source_dependencies(
        host_repo_path=host_repo_path,
        source_path="code/package1",
        source_type_input="auto",
        entry_scripts=None,
        repository="https://github.com/CCBR/package1",
        release_tag="v1.1.0",
        previous_tag="v1.0.0",
        package_name="",
    )

    assert result["source_type"] == "r_package"
    assert result["analysis_engine"] == "functracer"
    assert result["entry_scripts"] == ["main.R"]
    assert result["impacted_scripts"] == ["main.R"]
    assert result["release_impact_available"] is True
