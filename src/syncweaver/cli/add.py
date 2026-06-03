"""CLI command for adding an external repository to a host repository."""

from __future__ import annotations

import json
import pathlib
import shutil
import tempfile

import click

from syncweaver.git import run_git
from syncweaver.lockfile import read_lockfile, write_lockfile


def _copy_checked_out_repo(source: pathlib.Path, destination: pathlib.Path) -> None:
    """Copy a checked-out repository working tree without the .git directory."""
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(".git"),
    )


def add_external_repository(
    destination_path: pathlib.Path,
    repo_url: str,
    ref: str | None,
    lockfile_path: pathlib.Path,
    overwrite: bool,
) -> tuple[pathlib.Path, pathlib.Path, str, str]:
    """Add an external repository and register it in .syncweaver-lock.json."""
    cwd = pathlib.Path.cwd()
    destination = cwd / destination_path
    lockfile = cwd / lockfile_path

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
        run_git(["clone", "--quiet", "--no-checkout", repo_url, str(temp_repo)])

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
        _copy_checked_out_repo(temp_repo, destination)

    lock_data = read_lockfile(lockfile, cwd, run_git)
    repos = lock_data.setdefault("repos", {})
    repo_entry = repos.setdefault(repo_url, {})
    sources = repo_entry.setdefault("sources", {})
    source_key = destination_path.as_posix()
    sources[source_key] = {
        "branch": selected_ref,
        "git_sha": git_sha,
        "installed_by": ["syncweaver"],
    }
    write_lockfile(lockfile, lock_data)

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
    help="External repository URL or local path to clone.",
)
@click.option(
    "--ref",
    default=None,
    help="Git ref to vendor (branch, tag, or commit). Defaults to remote HEAD.",
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
    lockfile: pathlib.Path,
    overwrite: bool,
) -> None:
    """Add an external repository to the current host repository."""
    try:
        dest, lock_path, selected_ref, git_sha = add_external_repository(
            destination_path=destination_path,
            repo_url=repo_url,
            ref=ref,
            lockfile_path=lockfile,
            overwrite=overwrite,
        )
    except (FileExistsError, RuntimeError, json.JSONDecodeError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Vendored repository into {dest}")
    click.echo(f"Updated {lock_path} with ref {selected_ref} at {git_sha}")
