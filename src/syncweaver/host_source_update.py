"""Helpers for the update-host-source-direct GitHub Action."""

from __future__ import annotations

import json
import pathlib
import re
import subprocess

from syncweaver.dependency_analysis import (
    discover_host_entry_scripts,
    is_r_package_source,
    run_functracer_release_impact,
)
from syncweaver.lockfile import resolve_source_paths_from_lockfile


def _parse_list_input(raw_input: str | None) -> list[str]:
    """Parse comma/newline separated workflow input into unique values.

    Args:
        raw_input (str | None): Raw input text from workflow input.

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


def select_source_paths_for_update(
    source_paths: list[str],
    lockfile_path: pathlib.Path,
    source_ref_input: str | None,
    host_repo_path: pathlib.Path,
    functracer_entry_scripts_input: str | None,
    functracer_source_paths_input: str | None,
) -> tuple[list[str], list[str]]:
    """Filter source paths for update with optional functracer impact checks.

    Non-R-package sources are always updated. R-package sources are analyzed with
    functracer when entry scripts are provided at host level. If analysis cannot be
    executed or no valid host entry scripts exist, the source path is updated
    conservatively.

    Args:
        source_paths (list[str]): Candidate source paths resolved from lockfile.
        lockfile_path (pathlib.Path): Host lockfile path.
        source_ref_input (str | None): Requested source ref to update to.
        host_repo_path (pathlib.Path): Host repository root path.
        functracer_entry_scripts_input (str | None): Comma/newline-separated
            host entry scripts to analyze.
        functracer_source_paths_input (str | None): Optional comma/newline list of
            source paths that should be functracer-gated.

    Returns:
        tuple[list[str], list[str]]: Source paths to update and source paths skipped.
    """
    entry_scripts_input = _parse_list_input(functracer_entry_scripts_input)
    selected_source_paths = _parse_list_input(functracer_source_paths_input)
    source_ref = ""
    if source_ref_input is not None:
        source_ref = source_ref_input.strip()

    # Discover or validate host-level entry R scripts
    host_entry_scripts = discover_host_entry_scripts(
        host_repo_path=host_repo_path,
        source_paths=source_paths,
        candidate_scripts=entry_scripts_input if entry_scripts_input else None,
    )

    lock_data = json.loads(lockfile_path.read_text(encoding="utf-8"))
    sources = lock_data.get("sources", {})
    source_entries: dict[str, dict] = {}
    if isinstance(sources, dict):
        source_entries = sources

    source_paths_to_update: list[str] = []
    skipped_source_paths: list[str] = []

    for source_path in source_paths:
        should_update = True
        should_analyze = False
        if selected_source_paths:
            should_analyze = source_path in selected_source_paths
        else:
            should_analyze = is_r_package_source(host_repo_path, source_path)

        if should_analyze and host_entry_scripts:
            source_entry = source_entries.get(source_path, {})
            repository = str(source_entry.get("repo_url", "")).strip()
            previous_tag = str(source_entry.get("ref", "")).strip()
            has_required_metadata = bool(repository and previous_tag and source_ref)
            if has_required_metadata:
                impacted = False
                analysis_failed = False
                for entry_script_input in host_entry_scripts:
                    entry_script_path = host_repo_path / pathlib.Path(
                        entry_script_input
                    )
                    if entry_script_path.is_file():
                        try:
                            script_affected = run_functracer_release_impact(
                                entry_script=entry_script_path,
                                repository=repository,
                                release_tag=source_ref,
                                previous_tag=previous_tag,
                            )
                            impacted = impacted or script_affected
                        except (
                            FileNotFoundError,
                            ValueError,
                            subprocess.CalledProcessError,
                        ):
                            analysis_failed = True
                    else:
                        analysis_failed = True
                if (not impacted) and (not analysis_failed):
                    should_update = False
            else:
                should_update = True

        if should_update:
            source_paths_to_update.append(source_path)
        else:
            skipped_source_paths.append(source_path)

    if not host_entry_scripts:
        source_paths_to_update = source_paths
        skipped_source_paths = []

    result = (source_paths_to_update, skipped_source_paths)
    return result


def resolve_app_owner(host_repository: str, app_owner_input: str | None) -> str:
    """Resolve GitHub App owner from optional input or OWNER/REPO host string.

    Args:
        host_repository (str): Host repository in OWNER/REPO format.
        app_owner_input (str | None): Optional app owner override.

    Returns:
        str: Resolved owner to pass to token generation.

    Raises:
        ValueError: If owner cannot be resolved.
    """
    resolved_owner = ""
    owner_override = ""
    host_repository_input = host_repository.strip()
    if app_owner_input is not None:
        owner_override = app_owner_input.strip()

    if owner_override:
        resolved_owner = owner_override
    else:
        if "/" not in host_repository_input:
            raise ValueError(
                "host_repository must be in OWNER/REPO format to derive app_owner"
            )
        resolved_owner = host_repository_input.split("/", 1)[0].strip()

    if not resolved_owner:
        raise ValueError("unable to resolve app_owner for GitHub App token")
    return resolved_owner


def resolve_source_paths_for_host_update(
    lockfile_path: pathlib.Path,
    source_path_input: str | None,
    source_repository_input: str,
) -> list[str]:
    """Resolve source paths to update for a host repository run.

    Args:
        lockfile_path (pathlib.Path): Path to host lockfile.
        source_path_input (str | None): Optional explicit source path override.
        source_repository_input (str): Source repository identifier.

    Returns:
        list[str]: Source paths that should be updated.

    Raises:
        ValueError: If no source path can be resolved.
    """
    resolved_source_paths = resolve_source_paths_from_lockfile(
        lockfile=lockfile_path,
        source_path=source_path_input,
        repo_url=source_repository_input,
    )
    return resolved_source_paths


def run_syncweaver_updates(
    source_paths: list[str],
    lockfile_input: str,
    source_ref: str | None,
    remote_subdir: str | None,
    host_repo_path: pathlib.Path,
) -> None:
    """Run syncweaver update for each resolved source path.

    Args:
        source_paths (list[str]): Source paths to update.
        lockfile_input (str): Lockfile path relative to host repo root.
        source_ref (str | None): Optional source reference override.
        remote_subdir (str | None): Optional remote subdirectory override.
        host_repo_path (pathlib.Path): Checked out host repository path.

    Returns:
        None: Raises on subprocess failure.
    """
    normalized_ref = ""
    normalized_remote_subdir = ""
    if source_ref is not None:
        normalized_ref = source_ref.strip()
    if remote_subdir is not None:
        normalized_remote_subdir = remote_subdir.strip()

    for source_path in source_paths:
        command = [
            "syncweaver",
            "update",
            "--path",
            str(source_path),
            "--lockfile",
            str(lockfile_input),
        ]
        if normalized_ref:
            command.extend(["--ref", normalized_ref])
        if normalized_remote_subdir:
            command.extend(["--remote-subdir", normalized_remote_subdir])
        subprocess.run(command, cwd=host_repo_path, check=True)


def format_source_paths_markdown(source_paths: list[str]) -> str:
    """Format source path list as markdown bullets for PR body rendering.

    Args:
        source_paths (list[str]): Resolved source path list.

    Returns:
        str: Markdown bullet list.
    """
    markdown = "\n".join(f"- `{source_path}`" for source_path in source_paths)
    return markdown


def build_source_update_branch_name(source_repository_input: str) -> str:
    """Build a deterministic branch name for source update pull requests.

    Args:
        source_repository_input (str): Source repository identifier.

    Returns:
        str: Sanitized branch name.
    """
    source_repository = source_repository_input.strip()
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", source_repository).strip("-.")
    if not sanitized:
        sanitized = "source"
    branch_name = f"syncweaver/update-source/{sanitized}"
    return branch_name
