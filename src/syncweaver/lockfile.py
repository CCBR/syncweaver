"""Helpers for reading and writing the syncweaver lockfile."""

from __future__ import annotations

import json
import pathlib
from urllib.parse import urlparse

from syncweaver.util import get_version


DEFAULT_ORCHESTRATOR_NAME = "syncweaver-orchestrator"


def _derive_orchestrator_repo(
    host_repo: str, default_repo_name=DEFAULT_ORCHESTRATOR_NAME
) -> str:
    """Build default orchestrator repo as ORG/syncweaver-orchestrator."""
    host_repo_stripped = host_repo.strip()
    if "/" in host_repo_stripped:
        candidate_org = host_repo_stripped.split("/", 1)[0].strip()
        if candidate_org:
            host_org = candidate_org
    else:
        raise ValueError(
            "Invalid host repository format: cannot determine organization name"
        )
    orchestrator_repo = f"{host_org}/{default_repo_name}"
    return orchestrator_repo


def _normalize_remote_url(url: str) -> str:
    """Normalize a git remote URL to an https URL when possible."""
    stripped = url.strip()
    normalized = stripped
    if stripped.startswith("git@") and ":" in stripped:
        host_part, path_part = stripped.split(":", 1)
        host = host_part.split("@", 1)[1]
        path = path_part.removesuffix(".git")
        normalized = f"https://{host}/{path}"
    elif stripped.startswith("http://") or stripped.startswith("https://"):
        normalized = stripped.removesuffix(".git")
    elif "/" in stripped and "@" not in stripped and "://" not in stripped:
        parts = [part for part in stripped.split("/") if part]
        if len(parts) == 2:
            # Interpret OWNER/REPO shorthand as a GitHub repository URL.
            normalized = f"https://github.com/{parts[0]}/{parts[1]}"
        elif len(parts) >= 3 and "." in parts[0]:
            # Interpret host/OWNER/REPO shorthand as https://host/OWNER/REPO.
            normalized = f"https://{'/'.join(parts)}"
        normalized = normalized.removesuffix(".git")
    return normalized


def _detect_host_repo_metadata(cwd: pathlib.Path, run_git) -> tuple[str, str, str]:
    """Detect host metadata defaults from git origin and syncweaver runtime."""
    host_repo = f"unknown/{cwd.name}"
    orchestrator_repo = _derive_orchestrator_repo(host_repo)
    syncweaver_version = get_version()
    try:
        remote_url = run_git(["config", "--get", "remote.origin.url"], cwd=cwd)
    except RuntimeError:
        remote_url = ""

    if remote_url:
        normalized_remote = _normalize_remote_url(remote_url)
        parsed = urlparse(normalized_remote)
        if parsed.scheme in {"http", "https"} and parsed.path.strip("/"):
            host_repo = parsed.path.strip("/")
            orchestrator_repo = _derive_orchestrator_repo(host_repo)
    return host_repo, orchestrator_repo, syncweaver_version


def _upgrade_legacy_lockfile_shape(lock_data: dict) -> dict:
    """Upgrade legacy lockfile payloads to the top-level `sources` shape."""
    upgraded = lock_data
    has_sources = isinstance(upgraded.get("sources"), dict)
    has_legacy_repos = isinstance(upgraded.get("repos"), dict)
    if has_legacy_repos and not has_sources:
        sources: dict[str, dict] = {}
        legacy_repos = upgraded.get("repos", {})
        for repo_url, repo_entry in legacy_repos.items():
            legacy_sources = repo_entry.get("sources", {})
            for source_path, source_entry in legacy_sources.items():
                upgraded_entry = dict(source_entry)
                if "branch" in upgraded_entry and "ref" not in upgraded_entry:
                    upgraded_entry["ref"] = upgraded_entry.pop("branch")
                upgraded_entry["repo_url"] = repo_url

                existing_entry = sources.get(source_path)
                if existing_entry and existing_entry != upgraded_entry:
                    raise ValueError(
                        "Legacy lockfile has conflicting tracked entries for "
                        f"source path: {source_path}"
                    )
                sources[source_path] = upgraded_entry

        upgraded["sources"] = sources
        upgraded.pop("repos", None)

    if "host" not in upgraded and "name" in upgraded:
        upgraded["host"] = upgraded["name"]

    if "orchestrator" not in upgraded:
        host_repo = str(upgraded.get("host", "")).strip()
        upgraded["orchestrator"] = _derive_orchestrator_repo(host_repo)

    if "syncweaver_version" not in upgraded:
        upgraded["syncweaver_version"] = get_version()

    upgraded.pop("name", None)
    upgraded.pop("homePage", None)

    sources = upgraded.get("sources", {})
    if isinstance(sources, dict):
        for source_entry in sources.values():
            if isinstance(source_entry, dict):
                source_entry.pop("installed_by", None)
    return upgraded


def read_lockfile(lockfile: pathlib.Path, cwd: pathlib.Path, run_git) -> dict:
    """Read lockfile if present, otherwise create a default payload."""
    lock_data: dict
    if lockfile.exists():
        lock_data = json.loads(lockfile.read_text())
        lock_data = _upgrade_legacy_lockfile_shape(lock_data)
    else:
        host_repo, orchestrator_repo, syncweaver_version = _detect_host_repo_metadata(
            cwd, run_git
        )
        lock_data = {
            "host": host_repo,
            "orchestrator": orchestrator_repo,
            "syncweaver_version": syncweaver_version,
            "sources": {},
        }
    return lock_data


def load_existing_lockfile(lockfile: pathlib.Path) -> dict:
    """Read lockfile JSON from disk and fail when it does not exist."""
    if not lockfile.exists():
        raise FileNotFoundError(f"Lockfile does not exist: {lockfile}")
    lock_data = json.loads(lockfile.read_text())
    lock_data = _upgrade_legacy_lockfile_shape(lock_data)
    return lock_data


def resolve_source_paths_from_lockfile(
    lockfile: pathlib.Path,
    source_path: str | None,
    repo_url: str | None = None,
) -> list[str]:
    """Resolve one or more tracked source paths for a sync operation.

    Args:
        lockfile (pathlib.Path): Path to the syncweaver lockfile.
        source_path (str | None): Optional requested source path from CLI or workflow
            inputs.
        repo_url (str | None): Optional repository URL used to select matching source
            paths when source_path is omitted.

    Returns:
        list[str]: Resolved source path list.

    Raises:
        ValueError: If source_path is not provided and lockfile content cannot
            determine matching tracked source paths.
    """
    resolved_source_paths: list[str] = []
    source_path_input = ""
    repo_url_input = ""
    if source_path is not None:
        source_path_input = source_path.strip()
    if repo_url is not None:
        repo_url_input = repo_url.strip()

    if source_path_input:
        resolved_source_paths = [source_path_input]
    else:
        lock_data: dict
        try:
            lock_data = load_existing_lockfile(lockfile)
        except FileNotFoundError as exc:
            raise ValueError(
                f"lockfile does not exist and source_path was not provided: {lockfile}"
            ) from exc

        sources = lock_data.get("sources", {})
        has_sources = isinstance(sources, dict) and bool(sources)
        if not has_sources:
            raise ValueError(
                "no tracked sources found in lockfile and source_path was not provided"
            )

        if repo_url_input:
            normalized_repo_url = _normalize_remote_url(repo_url_input)
            matching_source_paths: list[str] = []
            for path_key, source_entry in sources.items():
                entry_repo_url = str(source_entry.get("repo_url", "")).strip()
                if entry_repo_url:
                    normalized_entry_url = _normalize_remote_url(entry_repo_url)
                    if normalized_entry_url == normalized_repo_url:
                        matching_source_paths.append(str(path_key))

            if not matching_source_paths:
                raise ValueError(
                    "source_path was not provided and no tracked sources matched "
                    f"repo_url: {repo_url_input}"
                )

            resolved_source_paths = sorted(matching_source_paths)
        else:
            source_paths = sorted(str(path) for path in sources.keys())
            if len(source_paths) != 1:
                source_paths_csv = ", ".join(source_paths)
                raise ValueError(
                    "source_path was not provided and lockfile tracks multiple sources. "
                    "Please provide source_path explicitly or set repo_url. "
                    f"Tracked sources: {source_paths_csv}"
                )
            resolved_source_paths = source_paths
    return resolved_source_paths


def resolve_source_path_from_lockfile(
    lockfile: pathlib.Path,
    source_path: str | None,
    repo_url: str | None = None,
) -> str:
    """Resolve the tracked source path for a sync operation.

    Args:
        lockfile (pathlib.Path): Path to the syncweaver lockfile.
        source_path (str | None): Optional requested source path from CLI or workflow
            inputs.
        repo_url (str | None): Optional repository URL used to select a matching
            source path when source_path is omitted.

    Returns:
        str: Resolved source path to update.

    Raises:
        ValueError: If source_path is not provided and lockfile content cannot
            determine a single tracked source path.
    """
    resolved_source_path = ""
    resolved_source_paths = resolve_source_paths_from_lockfile(
        lockfile=lockfile,
        source_path=source_path,
        repo_url=repo_url,
    )
    if len(resolved_source_paths) != 1:
        repo_url_input = ""
        if repo_url is not None:
            repo_url_input = repo_url.strip()
        matching_paths_csv = ", ".join(sorted(resolved_source_paths))
        raise ValueError(
            "source_path was not provided and multiple tracked sources "
            f"matched repo_url {repo_url_input}. "
            "Please provide source_path explicitly. "
            f"Matching sources: {matching_paths_csv}"
        )
    resolved_source_path = resolved_source_paths[0]
    return resolved_source_path


def write_lockfile(lockfile: pathlib.Path, data: dict) -> None:
    """Write lockfile JSON with a stable format."""
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    lockfile.write_text(f"{json.dumps(data, indent=2)}\n")
