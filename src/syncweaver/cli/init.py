"""CLI commands for repository initialization workflows."""

from __future__ import annotations

import pathlib

import click

from syncweaver.git import resolve_github_token
from syncweaver.init_orchestrator import (
    init_orchestrator_in_directory,
    init_orchestrator_in_repository,
)


@click.group("init")
def init_group() -> None:
    """Initialize syncweaver starter content in local or remote repositories."""


@init_group.command("orch")
@click.option(
    "--repo",
    default="",
    show_default=False,
    help=(
        "Optional GitHub repository in OWNER/REPO format. "
        "When set, syncweaver opens a pull request with orchestrator templates."
    ),
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite existing files when copying templates.",
)
@click.option(
    "--token",
    envvar="GITHUB_TOKEN",
    default="",
    show_default=False,
    help=(
        "GitHub token used when --repo is set. "
        "May also be set via GITHUB_TOKEN or resolved from gh auth."
    ),
)
@click.option(
    "--create-repo/--no-create-repo",
    default=True,
    help="Create the target repository when it does not exist.",
)
@click.option(
    "--private/--public",
    default=True,
    help="Privacy setting when creating a missing repository.",
)
@click.option(
    "--base-ref",
    default="",
    show_default=False,
    help="Optional PR base branch. Defaults to repository default branch.",
)
@click.option(
    "--branch",
    "branch_name",
    default="syncweaver/init-orchestrator",
    show_default=True,
    help="Branch name for the orchestrator template commit.",
)
@click.option(
    "--title",
    "pr_title",
    default="",
    show_default=False,
    help="Optional pull request title.",
)
@click.option(
    "--body",
    "pr_body",
    default="",
    show_default=False,
    help="Optional pull request body.",
)
def init_orch_cmd(
    repo: str,
    overwrite: bool,
    token: str,
    create_repo: bool,
    private: bool,
    base_ref: str,
    branch_name: str,
    pr_title: str,
    pr_body: str,
) -> None:
    """Initialize orchestrator repository files from packaged templates.

    Without --repo, copies template files from src/syncweaver/templates/orchestrator/
    into the current working directory. With --repo, applies the same files in a
    branch on the target repository and opens a pull request.
    """
    repo_input = repo.strip()

    try:
        if repo_input:
            resolved_token = resolve_github_token(token)
            result = init_orchestrator_in_repository(
                repo_slug=repo_input,
                github_token=resolved_token,
                branch_name=branch_name,
                base_ref=base_ref,
                overwrite=overwrite,
                create_if_missing=create_repo,
                private=private,
                pr_title=pr_title,
                pr_body=pr_body,
            )
            click.echo(f"Repository: {result['repository']}")
            click.echo(f"Branch: {result['branch']}")
            click.echo(f"Base ref: {result['base_ref']}")
            click.echo(f"Created repository: {result['created_repo']}")
            click.echo(f"Pull request: {result['pr_url']}")
        else:
            cwd = pathlib.Path.cwd()
            copied_files = init_orchestrator_in_directory(
                destination_dir=cwd,
                overwrite=overwrite,
            )
            click.echo(
                f"Copied {len(copied_files)} orchestrator files into {cwd.as_posix()}"
            )
    except (FileExistsError, OSError, RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
