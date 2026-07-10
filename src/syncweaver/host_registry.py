"""Helpers for loading and filtering syncweaver host repository registry files."""

from __future__ import annotations

import json
import pathlib

import requests
import yaml

from syncweaver.constants import DEFAULT_LOCKFILE_PATH
from syncweaver.lockfile import _normalize_remote_url


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
        lockfile = DEFAULT_LOCKFILE_PATH
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
            lockfile = str(host.get("lockfile", DEFAULT_LOCKFILE_PATH)).strip()
            if not lockfile:
                lockfile = DEFAULT_LOCKFILE_PATH
            remote_subdir = str(host.get("remote_subdir", "")).strip()
            matrix_hosts.append(
                {
                    "repository": host_repository,
                    "lockfile": lockfile,
                    "remote_subdir": remote_subdir,
                }
            )

    return matrix_hosts


def get_lockfile_sources_from_remote(
    host_repository: str,
    lockfile_path: str,
    ref: str = "main",
) -> set[str]:
    """Fetch a remote lockfile and extract normalized source repository URLs.

    Args:
        host_repository (str): Host repository in OWNER/REPO format.
        lockfile_path (str): Path to lockfile within the host repository.
        ref (str): Git reference (branch, tag, or commit). Defaults to "main".

    Returns:
        set[str]: Normalized source repository URLs found in the lockfile's
            'sources' section.

    Raises:
        requests.RequestException: If the lockfile cannot be fetched.
        ValueError: If the lockfile is not valid JSON.
    """
    # Build the GitHub raw content URL
    url = f"https://raw.githubusercontent.com/{host_repository}/{ref}/{lockfile_path}"

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    try:
        lock_data = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse lockfile from {url}: invalid JSON") from exc

    sources = lock_data.get("sources", {})
    if not isinstance(sources, dict):
        return set()

    # Extract and normalize source repository URLs
    source_urls: set[str] = set()
    for source_entry in sources.values():
        if isinstance(source_entry, dict):
            repo_url = str(source_entry.get("repo_url", "")).strip()
            if repo_url:
                normalized = _normalize_remote_url(repo_url)
                source_urls.add(normalized)

    return source_urls


def source_repo_in_host_lockfile(
    source_repository: str,
    host_repository: str,
    lockfile_path: str,
    ref: str = "main",
) -> bool:
    """Check if a source repository is tracked in a host's lockfile.

    Args:
        source_repository (str): Source repository in OWNER/REPO format.
        host_repository (str): Host repository in OWNER/REPO format.
        lockfile_path (str): Path to lockfile within the host repository.
        ref (str): Git reference (branch, tag, or commit). Defaults to "main".

    Returns:
        bool: True if the source repository is found in the host's lockfile,
            False otherwise.
    """
    try:
        normalized_source = _normalize_remote_url(source_repository)
        lockfile_sources = get_lockfile_sources_from_remote(
            host_repository=host_repository,
            lockfile_path=lockfile_path,
            ref=ref,
        )
        return normalized_source in lockfile_sources
    except Exception:
        # If lockfile cannot be fetched or parsed, assume the host should
        # not be updated (fail safe to avoid unnecessary updates).
        # This catches RequestException, ValueError, and any other errors.
        return False
