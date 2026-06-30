"""CLI commands for syncweaver patch lifecycle operations."""

from __future__ import annotations

import json
import pathlib

import click

from syncweaver.patch import (
    PATCH_STATUSES,
    create_patch,
    list_patches,
    mark_patch_status,
)


@click.group("patch")
def patch_group() -> None:
    """Create, mark, and list source patch artifacts."""


@patch_group.command("create")
@click.option(
    "--path",
    "source_path",
    required=True,
    type=click.Path(path_type=pathlib.Path),
    help="Tracked source path in the host repository, e.g. code/package1.",
)
@click.option(
    "--repo",
    "--repo-url",
    "repo",
    required=True,
    help="Repository URL as it appears in .syncweaver-lock.json.",
)
@click.option(
    "--lockfile",
    default=".syncweaver-lock.json",
    show_default=True,
    type=click.Path(path_type=pathlib.Path),
    help="Path to .syncweaver-lock.json in the host repository.",
)
@click.option(
    "--patch-dir",
    default=None,
    type=click.Path(path_type=pathlib.Path),
    help="Optional directory for the generated patch file.",
)
def create_cmd(
    source_path: pathlib.Path,
    repo: str,
    lockfile: pathlib.Path,
    patch_dir: pathlib.Path | None,
) -> None:
    """
    Create or update a canonical patch file for a
    tracked source path.
    """
    try:
        patch_path = create_patch(source_path, repo, lockfile, patch_dir)
    except (
        FileNotFoundError,
        KeyError,
        RuntimeError,
        json.JSONDecodeError,
        OSError,
    ) as exc:
        raise click.ClickException(str(exc)) from exc

    if patch_path:
        click.echo(f"Wrote patch file {patch_path}")
    else:
        click.echo("No source changes detected; patch file removed or unchanged.")


@patch_group.command("mark-status")
@click.option(
    "--patch",
    "patch_path",
    required=True,
    type=click.Path(path_type=pathlib.Path),
    help="Relative patch path, e.g. code/package1/.syncweaver/package1.diff.",
)
@click.option(
    "--status",
    required=True,
    type=click.Choice(PATCH_STATUSES, case_sensitive=False),
    help="Patch lifecycle status to record in the lockfile.",
)
@click.option(
    "--pr-url",
    default="",
    show_default=False,
    help="Optional upstream pull request URL associated with this patch.",
)
@click.option(
    "--reason",
    default="",
    show_default=False,
    help="Optional free-text note, required for rejected patches.",
)
@click.option(
    "--lockfile",
    default=".syncweaver-lock.json",
    show_default=True,
    type=click.Path(path_type=pathlib.Path),
    help="Path to .syncweaver-lock.json in the host repository.",
)
def mark_status_cmd(
    patch_path: pathlib.Path,
    status: str,
    pr_url: str,
    reason: str,
    lockfile: pathlib.Path,
) -> None:
    """Record patch lifecycle status metadata in lockfile extension fields."""
    try:
        patch_key, lockfile_written = mark_patch_status(
            patch_path=patch_path,
            status=status,
            pr_url=pr_url,
            reason=reason,
            lockfile_path=lockfile,
        )
    except (
        FileNotFoundError,
        KeyError,
        ValueError,
        json.JSONDecodeError,
        OSError,
    ) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Marked patch {patch_key} as {status.lower()} in {lockfile_written}")


@patch_group.command("list")
@click.option(
    "--path",
    "source_path",
    required=True,
    type=click.Path(path_type=pathlib.Path),
    help="Tracked source path in the host repository, e.g. code/package1.",
)
@click.option(
    "--lockfile",
    default=".syncweaver-lock.json",
    show_default=True,
    type=click.Path(path_type=pathlib.Path),
    help="Path to .syncweaver-lock.json in the host repository.",
)
def list_cmd(source_path: pathlib.Path, lockfile: pathlib.Path) -> None:
    """List tracked patch file records for a source path."""
    try:
        records = list_patches(path=source_path, lockfile_path=lockfile)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc

    if not records:
        click.echo(f"No patches tracked for {source_path.as_posix()}")
    else:
        for repo_url, path_key, patch_path in records:
            click.echo(f"{repo_url}\t{path_key}\t{patch_path}")
