"""Helpers for loading and filtering syncweaver host repository registry files."""

from __future__ import annotations

import pathlib

import yaml


def build_host_matrix_from_registry(
    registry_path: pathlib.Path,
    source_repository: str,
) -> list[dict[str, str]]:
    """Build host-dispatch matrix entries from a host repository registry file.

    Args:
        registry_path (pathlib.Path): Path to `.github/host-repositories.yml`.
        source_repository (str): Source repository in OWNER/REPO format used to
            filter host entries with `source_repository` constraints.

    Returns:
        list[dict[str, str]]: Matrix rows for workflow fan-out dispatch.
            Each host item is read from a mapping that must provide
            `repository` in OWNER/REPO format. Optional keys:
            `source_repository`, `lockfile`, and `remote_subdir`.

    Raises:
        FileNotFoundError: If the registry file does not exist.
        ValueError: If the registry file structure is invalid.
    """
    if not registry_path.exists():
        raise FileNotFoundError(f"host repository registry not found: {registry_path}")

    registry_data = yaml.safe_load(registry_path.read_text()) or {}
    hosts = registry_data.get("hosts", [])
    if not isinstance(hosts, list):
        raise ValueError(
            ".github/host-repositories.yml must define a list under 'hosts'."
        )

    normalized_source_repository = source_repository.strip()

    matrix_hosts: list[dict[str, str]] = []
    for host in hosts:
        include_host = isinstance(host, dict)
        host_repository = ""
        host_source_repository = ""
        lockfile = ".syncweaver-lock.json"
        remote_subdir = ""

        if include_host:
            host_repository = str(host.get("repository", "")).strip()
            include_host = bool(host_repository)

        if include_host:
            host_source_repository = str(host.get("source_repository", "")).strip()
            include_host = (
                not host_source_repository
                or host_source_repository == normalized_source_repository
            )

        if include_host:
            lockfile = str(host.get("lockfile", ".syncweaver-lock.json")).strip()
            if not lockfile:
                lockfile = ".syncweaver-lock.json"
            remote_subdir = str(host.get("remote_subdir", "")).strip()
            matrix_hosts.append(
                {
                    "repository": host_repository,
                    "lockfile": lockfile,
                    "remote_subdir": remote_subdir,
                }
            )

    return matrix_hosts
