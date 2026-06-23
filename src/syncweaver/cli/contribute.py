"""CLI command for contributing host patches back to source repositories."""

from __future__ import annotations

import json
import pathlib

import click

from syncweaver.contribute_patch import (
    _resolve_github_token,
    contribute_patch,
    resolve_contribute_patch_metadata,
)


@click.command("contribute")
@click.option(
    "--path",
    "source_path",
    default="",
    show_default=False,
    help=(
        "Tracked source path in the host repository, e.g. code/package1. "
        "Resolved automatically from lockfile when not provided."
    ),
)
@click.option(
    "--repo-url",
    default="",
    show_default=False,
    help=(
        "Source repository URL or OWNER/REPO shorthand. "
        "Used to disambiguate when multiple sources are tracked."
    ),
)
@click.option(
    "--source-repository",
    default="",
    show_default=False,
    help=(
        "Source repository in OWNER/REPO format. "
        "Derived from lockfile repo_url when not provided."
    ),
)
@click.option(
    "--patch",
    "patch_path",
    default="",
    show_default=False,
    type=click.Path(),
    help=(
        "Path to the patch file to contribute. "
        "Resolved from lockfile patch entry when not provided."
    ),
)
@click.option(
    "--base-ref",
    "source_base_ref",
    default="",
    show_default=False,
    help=(
        "Base branch or ref in the source repository to target. "
        "Defaults to lockfile ref when not provided."
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
    "--token",
    envvar="GITHUB_TOKEN",
    default="",
    show_default=False,
    help=(
        "GitHub token with push access to the source repository. "
        "May also be set via the GITHUB_TOKEN environment variable or resolved from `gh auth token` "
        "when not provided."
    ),
)
@click.option(
    "--run-id",
    default="",
    show_default=False,
    help="Optional identifier appended to the branch name for uniqueness.",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Print resolved metadata and verbose git output.",
)
def contribute_cmd(
    source_path: str,
    repo_url: str,
    source_repository: str,
    patch_path: str,
    source_base_ref: str,
    lockfile: pathlib.Path,
    token: str,
    run_id: str,
    debug: bool,
) -> None:
    """Contribute a tracked host patch back to the source repository.

    Clones the source repository, applies the patch to a new branch, pushes
    it, and opens a pull request.  Runs from the host repository directory.
    """
    cwd = pathlib.Path.cwd()
    try:
        resolved = resolve_contribute_patch_metadata(
            lockfile=cwd / lockfile,
            host_cwd=cwd,
            source_path=source_path,
            repo_url=repo_url,
            source_repository=source_repository,
            patch_path=patch_path,
            source_base_ref=source_base_ref,
        )
    except (
        FileNotFoundError,
        KeyError,
        ValueError,
        json.JSONDecodeError,
        OSError,
    ) as exc:
        raise click.ClickException(str(exc)) from exc

    if debug:
        click.echo("Resolved metadata:")
        click.echo(f"  source_path:       {resolved['source_path']}")
        click.echo(f"  repo_url:          {resolved['repo_url']}")
        click.echo(f"  source_repository: {resolved['source_repository']}")
        click.echo(f"  patch_path:        {resolved['patch_path']}")
        click.echo(f"  source_base_ref:   {resolved['source_base_ref']}")

    try:
        resolved_token = _resolve_github_token(token)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        pr_url = contribute_patch(
            resolved=resolved,
            host_cwd=cwd,
            github_token=resolved_token,
            run_id=run_id,
            debug=debug,
        )
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Pull request opened: {pr_url}")
