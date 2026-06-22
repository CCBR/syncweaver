"""Helpers for the update-host-source-direct GitHub Action."""

from __future__ import annotations

import pathlib
import re
import subprocess

from syncweaver.lockfile import resolve_source_paths_from_lockfile


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
