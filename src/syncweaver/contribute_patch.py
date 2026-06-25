"""Resolve contribute-patch workflow metadata for host repositories."""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile
from urllib.parse import urlparse

import requests

from syncweaver.git import build_github_git_env, run_git
from syncweaver.lockfile import (
    load_existing_lockfile,
    resolve_source_path_from_lockfile,
)


def _repo_slug_from_url(url: str) -> str:
    """Extract OWNER/REPO slug from a repository URL or shorthand."""
    raw = url.strip()
    if not raw:
        raise ValueError("Cannot derive repository slug from an empty value")

    result = None

    # Support SSH remotes like git@github.com:OWNER/REPO(.git)
    if raw.startswith("git@") and ":" in raw:
        _, path_part = raw.split(":", 1)
        path = path_part.removesuffix(".git").strip("/")
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2:
            result = f"{parts[0]}/{parts[1]}"
        else:
            raise ValueError(f"Cannot derive repository slug from: {url}")
    # Support OWNER/REPO shorthand
    elif "://" not in raw and raw.count("/") == 1 and "@" not in raw:
        owner, repo = raw.split("/", 1)
        result = f"{owner}/{repo.removesuffix('.git')}"
    else:
        parsed = urlparse(raw.removesuffix(".git"))
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"Cannot derive repository slug from: {url}")

        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) < 2:
            raise ValueError(f"Cannot derive repository slug from: {url}")

        owner = path_parts[0]
        repo = path_parts[1].removesuffix(".git")
        result = f"{owner}/{repo}"

    return result


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

    host_root = host_cwd.resolve()
    patch_file = (host_root / pathlib.Path(resolved_patch_path)).resolve()
    if not patch_file.is_relative_to(host_root):
        raise ValueError(
            "resolved patch path must remain within the host repository: "
            f"{resolved_patch_path}"
        )
    if not patch_file.is_file():
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


def contribute_patch(
    resolved: dict[str, str],
    host_cwd: pathlib.Path,
    github_token: str,
    *,
    run_id: str = "",
    debug: bool = False,
) -> str:
    """Clone source repo, apply patch, push branch, and open a pull request.

    Args:
        resolved: Metadata dict from :func:`resolve_contribute_patch_metadata`.
        host_cwd: Host repository working directory; patch path is resolved relative
            to this directory.
        github_token: GitHub personal access token or App token used to push and
            to call the GitHub REST API.
        run_id: Optional identifier appended to the branch name for uniqueness
            (e.g. a CI run ID or timestamp).
        debug: When ``True`` print verbose git output to stdout.

    Returns:
        str: URL of the opened pull request.

    Raises:
        FileNotFoundError: If the patch file does not exist in the host repository.
        KeyError: If required metadata keys are missing from ``resolved``.
        RuntimeError: If git operations or the GitHub API call fail.
    """
    source_repository = resolved["source_repository"]
    source_base_ref = resolved["source_base_ref"]
    patch_path = resolved["patch_path"]
    source_path = resolved["source_path"]
    repo_url = resolved["repo_url"]

    host_root = host_cwd.resolve()
    patch_file = (host_root / pathlib.Path(patch_path)).resolve()
    if not patch_file.is_relative_to(host_root):
        raise ValueError(f"Patch path must be within the host repository: {patch_path}")
    if not patch_file.is_file():
        raise FileNotFoundError(f"Patch file does not exist: {patch_path}")

    branch_stub_raw = pathlib.PurePosixPath(source_path).as_posix().replace("/", "--")
    branch_stub = "".join(
        ch for ch in branch_stub_raw if ch.isalnum() or ch in {".", "_", "-"}
    )
    if not branch_stub:
        branch_stub = "patch"
    suffix = f"-{run_id}" if run_id else ""
    branch_name = f"syncweaver/contribute-patch/{branch_stub}{suffix}"
    source_git_url = f"https://github.com/{source_repository}.git"
    git_env = build_github_git_env(github_token)
    redacted_values = [github_token]

    with tempfile.TemporaryDirectory(prefix="syncweaver-contribute-") as tmp_dir:
        clone_root = pathlib.Path(tmp_dir) / "source"

        def _git(*args: str) -> str:
            """Run git inside the cloned source repository."""
            cmd = ["-C", str(clone_root), *args]
            if debug:
                import sys

                print(f"git {' '.join(args)}", file=sys.stderr)
            result = run_git(cmd, env=git_env, redacted_values=redacted_values)
            return result

        run_git(
            ["clone", "--quiet", "--no-checkout", source_git_url, str(clone_root)],
            env=git_env,
            redacted_values=redacted_values,
        )
        _git("fetch", "--depth", "1", "origin", source_base_ref)
        _git("checkout", "--quiet", "-b", branch_name, "FETCH_HEAD")
        _git("config", "user.name", "github-actions[bot]")
        _git(
            "config",
            "user.email",
            "41898282+github-actions[bot]@users.noreply.github.com",
        )

        apply_result = subprocess.run(
            [
                "git",
                "-C",
                str(clone_root),
                "apply",
                "--3way",
                "--whitespace=nowarn",
                str(patch_file),
            ],
            capture_output=True,
            text=True,
        )
        if apply_result.returncode != 0:
            raise RuntimeError(
                f"Patch failed to apply to {source_repository}@{source_base_ref}:\n"
                f"{apply_result.stderr.strip()}"
            )

        diff_output = run_git(
            ["-C", str(clone_root), "diff", "--stat"],
            env=git_env,
            redacted_values=redacted_values,
        )
        if not diff_output.strip():
            raise RuntimeError(
                "Patch applied cleanly but introduced no source changes. "
                "Nothing to contribute."
            )

        _git("add", "--all")
        _git(
            "commit",
            "--message",
            f"chore(syncweaver): apply host patch for {source_path}",
        )
        _git("push", "origin", f"HEAD:refs/heads/{branch_name}")

    pr_body = (
        f"Automated patch contribution from host repository.\n\n"
        f"**Inputs**\n"
        f"- source_path: `{source_path}`\n"
        f"- repo_url: `{repo_url}`\n"
        f"- source_repository: `{source_repository}`\n"
        f"- source_base_ref: `{source_base_ref}`\n"
        f"- patch_path: `{patch_path}`\n"
    )

    api_url = f"https://api.github.com/repos/{source_repository}/pulls"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "title": f"chore(syncweaver): apply host patch for {source_path}",
        "head": branch_name,
        "base": source_base_ref,
        "body": pr_body,
    }
    response = requests.post(api_url, headers=headers, json=payload, timeout=30)
    if not response.ok:
        raise RuntimeError(
            f"GitHub API error {response.status_code} opening PR: {response.text}"
        )
    pr_url = response.json()["html_url"]
    return pr_url


def write_github_output(outputs: dict[str, str], output_path: pathlib.Path) -> None:
    """Write key-value pairs to the GitHub Actions output file."""
    with output_path.open("a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            safe_value = "" if value is None else str(value)
            if "\n" in safe_value or "\r" in safe_value:
                delimiter = "SYNCWEAVER_OUTPUT"
                while delimiter in safe_value:
                    delimiter += "_X"
                handle.write(f"{key}<<{delimiter}\n{safe_value}\n{delimiter}\n")
            else:
                handle.write(f"{key}={safe_value}\n")


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
