"""Helpers for reading and writing the syncweaver lockfile."""

from __future__ import annotations

import json
import pathlib
from urllib.parse import urlparse


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
    return normalized


def _detect_host_repo_metadata(cwd: pathlib.Path, run_git) -> tuple[str, str]:
    """Detect host repository name and homepage from git origin."""
    default_name = cwd.name
    repo_name = default_name
    home_page = ""
    try:
        remote_url = run_git(["config", "--get", "remote.origin.url"], cwd=cwd)
    except RuntimeError:
        remote_url = ""

    if remote_url:
        home_page = _normalize_remote_url(remote_url)
        parsed = urlparse(home_page)
        if parsed.scheme in {"http", "https"} and parsed.path.strip("/"):
            repo_name = parsed.path.strip("/")
    return repo_name, home_page


def read_lockfile(lockfile: pathlib.Path, cwd: pathlib.Path, run_git) -> dict:
    """Read lockfile if present, otherwise create a default payload."""
    lock_data: dict
    if lockfile.exists():
        lock_data = json.loads(lockfile.read_text())
    else:
        repo_name, home_page = _detect_host_repo_metadata(cwd, run_git)
        lock_data = {
            "name": repo_name,
            "homePage": home_page,
            "repos": {},
        }
    return lock_data


def load_existing_lockfile(lockfile: pathlib.Path) -> dict:
    """Read lockfile JSON from disk and fail when it does not exist."""
    if not lockfile.exists():
        raise FileNotFoundError(f"Lockfile does not exist: {lockfile}")
    return json.loads(lockfile.read_text())


def write_lockfile(lockfile: pathlib.Path, data: dict) -> None:
    """Write lockfile JSON with a stable format."""
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    lockfile.write_text(f"{json.dumps(data, indent=2)}\n")
