"""CLI command for removing a tracked external repository from a host repository."""

from __future__ import annotations

import json
import pathlib
import shutil

import click

from syncweaver.lockfile import load_existing_lockfile, write_lockfile


def remove_tracked_repository(
    destination_path: pathlib.Path,
    lockfile_path: pathlib.Path,
) -> tuple[pathlib.Path, pathlib.Path, bool]:
    """Remove a tracked external repository and its lockfile entry."""
    cwd = pathlib.Path.cwd()
    destination = cwd / destination_path
    lockfile = cwd / lockfile_path

    lock_data = load_existing_lockfile(lockfile)
    source_key = destination_path.as_posix()
    source_entry = lock_data.get("sources", {}).pop(source_key, None)
    if not source_entry:
        raise KeyError(f"Source path is not tracked in lockfile: {source_key}")

    destination_exists = destination.exists()
    if destination_exists:
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()

    write_lockfile(lockfile, lock_data)
    return destination, lockfile, destination_exists


@click.command("remove")
@click.option(
    "--path",
    "destination_path",
    required=True,
    type=click.Path(path_type=pathlib.Path),
    help="Tracked destination path in the host repository, e.g. code/package1.",
)
@click.option(
    "--lockfile",
    default=".syncweaver-lock.json",
    show_default=True,
    type=click.Path(path_type=pathlib.Path),
    help="Path to .syncweaver-lock.json in the host repository.",
)
def remove_cmd(destination_path: pathlib.Path, lockfile: pathlib.Path) -> None:
    """Remove a tracked external repository from the current host repository."""
    try:
        dest, lock_path, removed_destination = remove_tracked_repository(
            destination_path=destination_path,
            lockfile_path=lockfile,
        )
    except (KeyError, json.JSONDecodeError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc

    if removed_destination:
        click.echo(f"Removed vendored repository at {dest}")
    else:
        click.echo(f"Removed lockfile entry for missing vendored repository at {dest}")
    click.echo(f"Updated {lock_path} to remove {destination_path.as_posix()}")
