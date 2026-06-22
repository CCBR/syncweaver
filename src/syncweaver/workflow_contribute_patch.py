"""Resolve contribute-patch workflow metadata for host repositories."""

from __future__ import annotations

import os
import pathlib
from urllib.parse import urlparse

from syncweaver.lockfile import (
    load_existing_lockfile,
    resolve_source_path_from_lockfile,
)


def _repo_slug_from_url(url: str) -> str:
    """Extract OWNER/REPO slug from a normalized repository URL."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Cannot derive repository slug from: {url}")

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        raise ValueError(f"Cannot derive repository slug from: {url}")

    owner = path_parts[0]
    repo = path_parts[1]
    slug = f"{owner}/{repo}"
    return slug


def resolve_contribute_patch_metadata(
    *,
    lockfile: pathlib.Path,
    host_cwd: pathlib.Path,
    source_path: str | None,
    repo_url: str | None,
    source_repository: str | None,
    patch_path: str | None,
    source_base_ref: str | None,
) -> dict[str, str]:
    """Resolve workflow inputs into concrete source and patch metadata.

    Args:
        lockfile: Path to the syncweaver lockfile in the host repository.
        host_cwd: Host repository working directory used for resolving relative paths.
        source_path: Optional tracked source path override.
        repo_url: Optional source repository URL or OWNER/REPO shorthand.
        source_repository: Optional explicit OWNER/REPO source repository.
        patch_path: Optional explicit patch file path.
        source_base_ref: Optional explicit source repository base ref.

    Returns:
        dict[str, str]: Resolved metadata fields required by the workflow.

    Raises:
        ValueError: If lockfile metadata is missing or ambiguous.
        FileNotFoundError: If resolved patch file does not exist.
    """
    source_path_input = ""
    repo_url_input = ""
    source_repository_input = ""
    patch_path_input = ""
    source_base_ref_input = ""

    if source_path is not None:
        source_path_input = source_path.strip()
    if repo_url is not None:
        repo_url_input = repo_url.strip()
    if source_repository is not None:
        source_repository_input = source_repository.strip()
    if patch_path is not None:
        patch_path_input = patch_path.strip()
    if source_base_ref is not None:
        source_base_ref_input = source_base_ref.strip()

    repo_selector = repo_url_input
    if not repo_selector and source_repository_input:
        repo_selector = source_repository_input

    resolved_source_path = resolve_source_path_from_lockfile(
        lockfile=lockfile,
        source_path=source_path_input,
        repo_url=repo_selector,
    )

    lock_data = load_existing_lockfile(lockfile)
    sources = lock_data.get("sources", {})
    source_entry_raw = sources.get(resolved_source_path)
    if not isinstance(source_entry_raw, dict):
        raise ValueError(
            f"lockfile source entry is invalid for source_path: {resolved_source_path}"
        )

    resolved_repo_url = str(source_entry_raw.get("repo_url", "")).strip()
    if not resolved_repo_url:
        raise ValueError(
            "lockfile source entry is missing repo_url for source_path: "
            f"{resolved_source_path}"
        )

    resolved_source_repository = source_repository_input
    if not resolved_source_repository:
        resolved_source_repository = _repo_slug_from_url(resolved_repo_url)

    resolved_patch_path = patch_path_input
    if not resolved_patch_path:
        resolved_patch_path = str(source_entry_raw.get("patch", "")).strip()
    if not resolved_patch_path:
        raise ValueError(
            "no patch path was provided and no tracked patch exists in lockfile "
            f"for source_path: {resolved_source_path}"
        )

    patch_file = (host_cwd / pathlib.Path(resolved_patch_path)).resolve()
    if not patch_file.exists():
        raise FileNotFoundError(
            "resolved patch file does not exist in host repository: "
            f"{resolved_patch_path}"
        )

    resolved_source_base_ref = source_base_ref_input
    if not resolved_source_base_ref:
        resolved_source_base_ref = (
            str(source_entry_raw.get("ref", "")).strip() or "main"
        )

    result = {
        "source_path": resolved_source_path,
        "repo_url": resolved_repo_url,
        "source_repository": resolved_source_repository,
        "patch_path": resolved_patch_path,
        "source_base_ref": resolved_source_base_ref,
    }
    return result


def write_github_output(outputs: dict[str, str], output_path: pathlib.Path) -> None:
    """Write key-value pairs to the GitHub Actions output file."""
    with output_path.open("a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    """Resolve metadata from workflow environment and emit GitHub outputs."""
    lockfile = pathlib.Path(os.environ.get("LOCKFILE_PATH", ".syncweaver-lock.json"))
    host_cwd = pathlib.Path(os.environ.get("SYNCWEAVER_HOST_CWD", ".")).resolve()
    source_path = os.environ.get("SOURCE_PATH_INPUT", "")
    repo_url = os.environ.get("REPO_URL_INPUT", "")
    source_repository = os.environ.get("SOURCE_REPOSITORY_INPUT", "")
    patch_path = os.environ.get("PATCH_PATH_INPUT", "")
    source_base_ref = os.environ.get("SOURCE_BASE_REF_INPUT", "")
    output_file = os.environ.get("GITHUB_OUTPUT", "")

    if not output_file:
        raise RuntimeError("GITHUB_OUTPUT is not set")

    resolved = resolve_contribute_patch_metadata(
        lockfile=lockfile,
        host_cwd=host_cwd,
        source_path=source_path,
        repo_url=repo_url,
        source_repository=source_repository,
        patch_path=patch_path,
        source_base_ref=source_base_ref,
    )
    write_github_output(resolved, pathlib.Path(output_file))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
