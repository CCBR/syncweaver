"""CLI command for adding an external repository to a host repository."""

from __future__ import annotations

import json
import pathlib
import shutil
import tempfile

import click

from syncweaver.git import run_git
from syncweaver.lockfile import read_lockfile, write_lockfile


def _resolve_repo_url_input(repo_url: str, cwd: pathlib.Path) -> tuple[str, str]:
    """Resolve clone URL and tracked URL from a user-provided repo value."""
    normalized_input = repo_url.strip()
    if not normalized_input:
        raise ValueError("--repo-url cannot be empty")

    if normalized_input.startswith("file://"):
        raise ValueError("--repo-url must not be a local filesystem path")

    if normalized_input.startswith(("./", "../", "/", "~")):
        raise ValueError("--repo-url must not be a local filesystem path")

    candidate_path = pathlib.Path(normalized_input).expanduser()
    if not candidate_path.is_absolute():
        candidate_path = cwd / candidate_path
    if candidate_path.exists():
        raise ValueError("--repo-url must not be a local filesystem path")
    elif (
        "://" not in normalized_input
        and normalized_input.count("/") == 1
        and "@" not in normalized_input
    ):
        slug = normalized_input.removesuffix(".git")
        clone_url = f"https://github.com/{slug}.git"
        tracked_repo_url = f"https://github.com/{slug}"
    elif "://" not in normalized_input and "@" not in normalized_input:
        raise ValueError("--repo-url must be a remote URL or OWNER/REPO shorthand")
    else:
        clone_url = normalized_input
        tracked_repo_url = normalized_input
    return clone_url, tracked_repo_url


def _copy_checked_out_repo(source: pathlib.Path, destination: pathlib.Path) -> None:
    """Copy a checked-out repository working tree without the .git directory."""
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(".git"),
    )


def _ensure_linguist_vendored_entry(
    host_root: pathlib.Path, destination_path: pathlib.Path
) -> None:
    """Ensure destination path is marked linguist-vendored in .gitattributes."""
    gitattributes_path = host_root / ".gitattributes"
    entry_path = destination_path.as_posix()

    existing_lines: list[str] = []
    if gitattributes_path.exists():
        existing_lines = gitattributes_path.read_text().splitlines()

    has_destination_entry = False
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            tokens = stripped.split()
            if tokens and tokens[0] == entry_path:
                has_destination_entry = True

    if not has_destination_entry:
        existing_lines.append(f"{entry_path} linguist-vendored")

    gitattributes_path.write_text("\n".join(existing_lines) + "\n")


def _resolve_remote_source_path(
    checkout_root: pathlib.Path, remote_subdir: str | None
) -> pathlib.Path:
    """Resolve and validate the source path inside a checked-out repository."""
    source_root = checkout_root
    if remote_subdir:
        normalized = pathlib.PurePosixPath(remote_subdir.strip("/"))
        if str(normalized) in {"", "."}:
            raise ValueError("--remote-subdir cannot be empty or '.'")

        source_root = checkout_root / pathlib.Path(*normalized.parts)
        if not source_root.exists() or not source_root.is_dir():
            raise FileNotFoundError(
                "Remote subdirectory does not exist in checked out repository: "
                f"{remote_subdir}"
            )
    return source_root


def add_external_repository(
    destination_path: pathlib.Path,
    repo_url: str,
    ref: str | None,
    remote_subdir: str | None,
    lockfile_path: pathlib.Path,
    overwrite: bool,
) -> tuple[pathlib.Path, pathlib.Path, str, str]:
    """Add an external repository and register it in .syncweaver-lock.json."""
    cwd = pathlib.Path.cwd()
    destination = cwd / destination_path
    lockfile = cwd / lockfile_path
    clone_repo_url, tracked_repo_url = _resolve_repo_url_input(repo_url, cwd)

    if destination.exists():
        if not overwrite:
            raise FileExistsError(
                f"Destination already exists: {destination_path}. "
                "Pass --overwrite to replace it."
            )
        shutil.rmtree(destination)

    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="syncweaver-add-") as temp_dir:
        temp_repo = pathlib.Path(temp_dir) / "repo"
        run_git(["clone", "--quiet", "--no-checkout", clone_repo_url, str(temp_repo)])

        selected_ref = ref
        if selected_ref:
            run_git(
                [
                    "-C",
                    str(temp_repo),
                    "fetch",
                    "--depth",
                    "1",
                    "origin",
                    selected_ref,
                ]
            )
            run_git(["-C", str(temp_repo), "checkout", "--quiet", "FETCH_HEAD"])
        else:
            run_git(["-C", str(temp_repo), "checkout", "--quiet", "HEAD"])
            selected_ref = run_git(
                [
                    "-C",
                    str(temp_repo),
                    "symbolic-ref",
                    "--short",
                    "refs/remotes/origin/HEAD",
                ]
            )
            selected_ref = selected_ref.removeprefix("origin/")

        git_sha = run_git(["-C", str(temp_repo), "rev-parse", "HEAD"])
        source_root = _resolve_remote_source_path(temp_repo, remote_subdir)
        _copy_checked_out_repo(source_root, destination)

    lock_data = read_lockfile(lockfile, cwd, run_git)
    sources = lock_data.setdefault("sources", {})
    source_key = destination_path.as_posix()
    sources[source_key] = {
        "repo_url": tracked_repo_url,
        "ref": selected_ref,
        "git_sha": git_sha,
        "installed_by": ["syncweaver"],
    }
    if remote_subdir:
        normalized_subdir = pathlib.PurePosixPath(remote_subdir.strip("/")).as_posix()
        sources[source_key]["remote_subdir"] = normalized_subdir
    write_lockfile(lockfile, lock_data)
    _ensure_linguist_vendored_entry(cwd, destination_path)

    return destination, lockfile, selected_ref, git_sha


@click.command("add")
@click.option(
    "--path",
    "destination_path",
    required=True,
    type=click.Path(path_type=pathlib.Path),
    help="Destination path in the host repository, e.g. code/package1.",
)
@click.option(
    "--repo-url",
    required=True,
    help="External repository URL or OWNER/REPO shorthand.",
)
@click.option(
    "--ref",
    default=None,
    help="Git ref to vendor (branch, tag, or commit). Defaults to remote HEAD.",
)
@click.option(
    "--remote-subdir",
    default=None,
    help=(
        "Optional repository subdirectory to vendor, e.g. src/package1. "
        "When omitted, vendors repository root."
    ),
)
@click.option(
    "--lockfile",
    default=".syncweaver-lock.json",
    show_default=True,
    type=click.Path(path_type=pathlib.Path),
    help="Path to .syncweaver-lock.json in the host repository.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite destination path if it already exists.",
)
def add_cmd(
    destination_path: pathlib.Path,
    repo_url: str,
    ref: str | None,
    remote_subdir: str | None,
    lockfile: pathlib.Path,
    overwrite: bool,
) -> None:
    """Add an external repository to the current host repository."""
    try:
        dest, lock_path, selected_ref, git_sha = add_external_repository(
            destination_path=destination_path,
            repo_url=repo_url,
            ref=ref,
            remote_subdir=remote_subdir,
            lockfile_path=lockfile,
            overwrite=overwrite,
        )
    except (
        FileExistsError,
        RuntimeError,
        ValueError,
        json.JSONDecodeError,
        OSError,
    ) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Vendored repository into {dest}")
    click.echo(f"Updated {lock_path} with ref {selected_ref} at {git_sha}")
