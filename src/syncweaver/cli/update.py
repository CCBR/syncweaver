"""CLI command for updating a tracked external repository in a host repository."""

from __future__ import annotations

import json
import pathlib
import shutil
import tempfile

import click

from syncweaver.cli.add import _copy_checked_out_repo, _resolve_remote_source_path
from syncweaver.git import run_git
from syncweaver.lockfile import load_existing_lockfile, write_lockfile


def update_external_repository(
    destination_path: pathlib.Path,
    ref: str | None,
    remote_subdir: str | None,
    lockfile_path: pathlib.Path,
) -> tuple[pathlib.Path, pathlib.Path, str, str]:
    """Update a tracked external repository and refresh lockfile metadata."""
    cwd = pathlib.Path.cwd()
    destination = cwd / destination_path
    lockfile = cwd / lockfile_path

    lock_data = load_existing_lockfile(lockfile)
    source_key = destination_path.as_posix()
    source_entry = lock_data.get("sources", {}).get(source_key)
    if not source_entry:
        raise KeyError(f"Source path is not tracked in lockfile: {source_key}")

    repo_url = source_entry.get("repo_url")
    if not repo_url:
        raise KeyError(f"Missing repo_url in lockfile for source path: {source_key}")

    selected_ref = ref
    if not selected_ref:
        selected_ref = source_entry.get("ref")
    if not selected_ref:
        raise KeyError(f"Missing ref in lockfile for source path: {source_key}")

    selected_remote_subdir = remote_subdir
    if selected_remote_subdir is None:
        selected_remote_subdir = source_entry.get("remote_subdir")

    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="syncweaver-update-") as temp_dir:
        temp_repo = pathlib.Path(temp_dir) / "repo"
        run_git(["clone", "--quiet", "--no-checkout", repo_url, str(temp_repo)])
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

        git_sha = run_git(["-C", str(temp_repo), "rev-parse", "HEAD"])
        source_root = _resolve_remote_source_path(temp_repo, selected_remote_subdir)
        _copy_checked_out_repo(source_root, destination)

    source_entry["ref"] = selected_ref
    source_entry["git_sha"] = git_sha
    if selected_remote_subdir:
        normalized_subdir = pathlib.PurePosixPath(
            selected_remote_subdir.strip("/")
        ).as_posix()
        source_entry["remote_subdir"] = normalized_subdir
    else:
        source_entry.pop("remote_subdir", None)
    write_lockfile(lockfile, lock_data)

    return destination, lockfile, selected_ref, git_sha


@click.command("update")
@click.option(
    "--path",
    "destination_path",
    required=True,
    type=click.Path(path_type=pathlib.Path),
    help="Tracked destination path in the host repository, e.g. code/package1.",
)
@click.option(
    "--ref",
    default=None,
    help="Git ref to vendor (branch, tag, or commit). Defaults to lockfile ref.",
)
@click.option(
    "--remote-subdir",
    default=None,
    help=(
        "Optional repository subdirectory to vendor, e.g. src/package1. "
        "Defaults to lockfile remote_subdir when present."
    ),
)
@click.option(
    "--lockfile",
    default=".syncweaver-lock.json",
    show_default=True,
    type=click.Path(path_type=pathlib.Path),
    help="Path to .syncweaver-lock.json in the host repository.",
)
def update_cmd(
    destination_path: pathlib.Path,
    ref: str | None,
    remote_subdir: str | None,
    lockfile: pathlib.Path,
) -> None:
    """Update a tracked external repository in the current host repository."""
    try:
        dest, lock_path, selected_ref, git_sha = update_external_repository(
            destination_path=destination_path,
            ref=ref,
            remote_subdir=remote_subdir,
            lockfile_path=lockfile,
        )
    except (
        FileNotFoundError,
        KeyError,
        RuntimeError,
        ValueError,
        json.JSONDecodeError,
        OSError,
    ) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Updated vendored repository in {dest}")
    click.echo(f"Updated {lock_path} with ref {selected_ref} at {git_sha}")
