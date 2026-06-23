"""Dependency analysis helpers for host/source integration workflows."""

from __future__ import annotations

from importlib import resources
import pathlib
import subprocess
from typing import Any


def parse_path_list(raw_input: str | None) -> list[str]:
    """Parse comma/newline separated path input into unique values.

    Args:
        raw_input (str | None): Raw input text from CLI/workflow options.

    Returns:
        list[str]: De-duplicated values in input order.
    """
    values: list[str] = []
    normalized_input = ""
    if raw_input is not None:
        normalized_input = raw_input.strip()
    if normalized_input:
        normalized_text = normalized_input.replace(",", "\n")
        for raw_value in normalized_text.splitlines():
            value = raw_value.strip()
            if value and value not in values:
                values.append(value)
    return values


def _path_is_within(path: pathlib.Path, parent: pathlib.Path) -> bool:
    """Check whether a path is contained within a parent path.

    Args:
        path (pathlib.Path): Candidate path.
        parent (pathlib.Path): Potential parent path.

    Returns:
        bool: True when candidate path is inside parent path.
    """
    is_within = False
    try:
        path.relative_to(parent)
        is_within = True
    except ValueError:
        is_within = False
    return is_within


def is_r_package_source(host_repo_path: pathlib.Path, source_path: str) -> bool:
    """Check whether a source path in host repo appears to be an R package.

    Args:
        host_repo_path (pathlib.Path): Host repository root path.
        source_path (str): Tracked source path in host repository.

    Returns:
        bool: True when DESCRIPTION and R/ are present.
    """
    source_root = host_repo_path / pathlib.Path(source_path)
    has_description = (source_root / "DESCRIPTION").is_file()
    has_r_dir = (source_root / "R").is_dir()
    is_r_package = has_description and has_r_dir
    return is_r_package


def _is_python_package_source(host_repo_path: pathlib.Path, source_path: str) -> bool:
    """Check whether a source path in host repo appears to be a Python package.

    Args:
        host_repo_path (pathlib.Path): Host repository root path.
        source_path (str): Tracked source path in host repository.

    Returns:
        bool: True when pyproject/setup metadata and Python files are present.
    """
    source_root = host_repo_path / pathlib.Path(source_path)
    has_build_metadata = (source_root / "pyproject.toml").is_file() or (
        source_root / "setup.py"
    ).is_file()
    has_python_sources = bool(list(source_root.rglob("*.py")))
    is_python_package = has_build_metadata and has_python_sources
    return is_python_package


def detect_source_type(host_repo_path: pathlib.Path, source_path: str) -> str:
    """Detect source package type for dependency analysis routing.

    Args:
        host_repo_path (pathlib.Path): Host repository root path.
        source_path (str): Tracked source path in host repository.

    Returns:
        str: Source type identifier.
    """
    source_type = "unknown"
    if is_r_package_source(host_repo_path, source_path):
        source_type = "r_package"
    elif _is_python_package_source(host_repo_path, source_path):
        source_type = "python_package"
    return source_type


def _run_functracer_boolean_script(script_name: str, args: list[str]) -> bool:
    """Execute a packaged R helper script and parse true/false stdout output.

    Args:
        script_name (str): Data script filename located in syncweaver/data.
        args (list[str]): Positional arguments passed to Rscript.

    Returns:
        bool: Parsed boolean result emitted by helper script.

    Raises:
        ValueError: If script output is not a boolean token.
        FileNotFoundError: If Rscript executable is unavailable.
        subprocess.CalledProcessError: If R process exits non-zero.
    """
    script_resource = resources.files("syncweaver").joinpath(f"data/{script_name}")
    with resources.as_file(script_resource) as script_path:
        command = ["Rscript", str(script_path), *args]
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    output_text = completed.stdout.strip().lower()
    if output_text not in {"true", "false"}:
        raise ValueError("unexpected analyzer output; expected true or false")
    parsed_result = output_text == "true"
    return parsed_result


def run_functracer_release_impact(
    entry_script: pathlib.Path,
    repository: str,
    release_tag: str,
    previous_tag: str,
    package_name: str,
) -> bool:
    """Run functracer release impact analysis for an entry script.

    Args:
        entry_script (pathlib.Path): Host entry script to analyze.
        repository (str): Source repository URL.
        release_tag (str): Candidate release tag/ref.
        previous_tag (str): Previously tracked source ref.
        package_name (str): Optional package name override.

    Returns:
        bool: True when entry script is affected by dependency changes.
    """
    result = _run_functracer_boolean_script(
        script_name="functracer_release_impact.R",
        args=[
            str(entry_script),
            repository,
            release_tag,
            previous_tag,
            package_name,
        ],
    )
    return result


def _script_calls_r_package(
    entry_script: pathlib.Path, package_dir: pathlib.Path
) -> bool:
    """Evaluate whether a host entry script depends on functions from R package.

    Args:
        entry_script (pathlib.Path): Candidate host script path.
        package_dir (pathlib.Path): Local R package root path.

    Returns:
        bool: True when functracer detects dependencies from package_dir.
    """
    result = _run_functracer_boolean_script(
        script_name="functracer_script_calls_package.R",
        args=[str(entry_script), str(package_dir)],
    )
    return result


def _collect_candidate_r_scripts(
    host_repo_path: pathlib.Path,
    source_root: pathlib.Path,
    candidate_scripts: list[str] | None,
) -> list[pathlib.Path]:
    """Build candidate host R scripts for dependency discovery.

    Args:
        host_repo_path (pathlib.Path): Host repository root path.
        source_root (pathlib.Path): Source root that should be excluded.
        candidate_scripts (list[str] | None): Optional relative script overrides.

    Returns:
        list[pathlib.Path]: Candidate script paths.
    """
    resolved_candidates: list[pathlib.Path] = []
    if candidate_scripts is not None:
        for candidate_script in candidate_scripts:
            candidate_path = host_repo_path / pathlib.Path(candidate_script)
            has_r_suffix = candidate_path.suffix.lower() == ".r"
            is_file = candidate_path.is_file()
            if has_r_suffix and is_file:
                resolved_candidates.append(candidate_path)
    else:
        for script_path in sorted(host_repo_path.rglob("*.R")):
            is_within_source = _path_is_within(script_path, source_root)
            if (not is_within_source) and script_path.is_file():
                resolved_candidates.append(script_path)
    return resolved_candidates


def find_host_scripts_calling_source(
    host_repo_path: pathlib.Path,
    source_path: str,
    candidate_scripts: list[str] | None = None,
) -> list[str]:
    """Find host repository scripts that depend on functions from a source path.

    Args:
        host_repo_path (pathlib.Path): Host repository root path.
        source_path (str): Tracked source path in host repository.
        candidate_scripts (list[str] | None): Optional list of relative script
            paths to evaluate. When omitted, all host-side *.R scripts are tested.

    Returns:
        list[str]: Relative script paths that call functions from source package.
    """
    calling_scripts: list[str] = []
    source_root = host_repo_path / pathlib.Path(source_path)
    source_is_r_package = is_r_package_source(host_repo_path, source_path)
    if source_is_r_package:
        candidates = _collect_candidate_r_scripts(
            host_repo_path=host_repo_path,
            source_root=source_root,
            candidate_scripts=candidate_scripts,
        )
        for entry_script in candidates:
            if _script_calls_r_package(
                entry_script=entry_script, package_dir=source_root
            ):
                relative_path = entry_script.relative_to(host_repo_path).as_posix()
                calling_scripts.append(relative_path)
    return calling_scripts


def analyze_source_dependencies(
    host_repo_path: pathlib.Path,
    source_path: str,
    source_type_input: str,
    entry_scripts: list[str] | None,
    repository: str | None,
    release_tag: str | None,
    previous_tag: str | None,
    package_name: str | None,
) -> dict[str, Any]:
    """Analyze source dependencies with language-aware and extensible metadata.

    Args:
        host_repo_path (pathlib.Path): Host repository root path.
        source_path (str): Tracked source path in host repository.
        source_type_input (str): Source type override; use "auto" to detect.
        entry_scripts (list[str] | None): Optional host entry script list.
        repository (str | None): Optional repository URL for release impact checks.
        release_tag (str | None): Optional candidate release tag/ref.
        previous_tag (str | None): Optional baseline release tag/ref.
        package_name (str | None): Optional package name override.

    Returns:
        dict[str, Any]: Analysis summary suitable for CLI JSON output.
    """
    normalized_source_type = source_type_input.strip().lower()
    resolved_source_type = normalized_source_type
    if normalized_source_type == "auto":
        resolved_source_type = detect_source_type(host_repo_path, source_path)

    normalized_entry_scripts: list[str] = []
    if entry_scripts is not None:
        for entry_script in entry_scripts:
            script_value = entry_script.strip()
            if script_value:
                normalized_entry_scripts.append(script_value)

    language = "unknown"
    if resolved_source_type == "r_package":
        language = "r"
    elif resolved_source_type == "python_package":
        language = "python"

    resolved_scripts: list[str] = []
    if resolved_source_type == "r_package":
        if normalized_entry_scripts:
            resolved_scripts = normalized_entry_scripts
        else:
            resolved_scripts = find_host_scripts_calling_source(
                host_repo_path=host_repo_path,
                source_path=source_path,
                candidate_scripts=None,
            )

    normalized_repository = ""
    if repository is not None:
        normalized_repository = repository.strip()
    normalized_release_tag = ""
    if release_tag is not None:
        normalized_release_tag = release_tag.strip()
    normalized_previous_tag = ""
    if previous_tag is not None:
        normalized_previous_tag = previous_tag.strip()
    normalized_package_name = ""
    if package_name is not None:
        normalized_package_name = package_name.strip()

    impacted_scripts: list[str] = []
    unaffected_scripts: list[str] = []
    can_run_release_impact = bool(
        resolved_source_type == "r_package"
        and resolved_scripts
        and normalized_repository
        and normalized_release_tag
        and normalized_previous_tag
    )
    if can_run_release_impact:
        for script_path in resolved_scripts:
            entry_script_path = host_repo_path / pathlib.Path(script_path)
            script_affected = run_functracer_release_impact(
                entry_script=entry_script_path,
                repository=normalized_repository,
                release_tag=normalized_release_tag,
                previous_tag=normalized_previous_tag,
                package_name=normalized_package_name,
            )
            if script_affected:
                impacted_scripts.append(script_path)
            else:
                unaffected_scripts.append(script_path)

    release_impact_available = bool(can_run_release_impact)
    analysis_engine = "none"
    if resolved_source_type == "r_package":
        analysis_engine = "functracer"
    elif resolved_source_type == "python_package":
        analysis_engine = "python-not-implemented"

    result: dict[str, Any] = {
        "source_path": source_path,
        "source_type": resolved_source_type,
        "language": language,
        "analysis_engine": analysis_engine,
        "entry_scripts": resolved_scripts,
        "release_impact_available": release_impact_available,
        "impacted_scripts": impacted_scripts,
        "unaffected_scripts": unaffected_scripts,
    }
    return result
