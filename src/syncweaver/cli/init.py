"""CLI commands for repository initialization workflows."""

from __future__ import annotations

import pathlib

import click

from syncweaver.constants import DEFAULT_LOCKFILE_PATH
from syncweaver.git import resolve_github_token
from syncweaver.init_host import (
    init_host_in_directory,
    register_host_with_orchestrator_repository,
)
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


@init_group.command("host")
@click.option(
    "--host-repo",
    default="",
    show_default=False,
    help=(
        "Optional host repository override in OWNER/REPO format. "
        "When omitted, syncweaver infers host metadata from git origin."
    ),
)
@click.option(
    "--orchestrator-repo",
    default="",
    show_default=False,
    help=(
        "Optional orchestrator repository override in OWNER/REPO format. "
        "When omitted, syncweaver derives it from host metadata."
    ),
)
@click.option(
    "--lockfile",
    default=DEFAULT_LOCKFILE_PATH,
    show_default=True,
    type=click.Path(path_type=pathlib.Path),
    help="Path to lockfile in the host repository.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite existing lockfile and workflow templates when present.",
)
@click.option(
    "--register/--no-register",
    default=True,
    help="Open a PR in orchestrator repo to add this host to host-repositories.yml.",
)
@click.option(
    "--token",
    envvar="GITHUB_TOKEN",
    default="",
    show_default=False,
    help=(
        "GitHub token used to register the host in orchestrator repo. "
        "May also be set via GITHUB_TOKEN or resolved from gh auth."
    ),
)
@click.option(
    "--registry-path",
    default=".github/host-repositories.yml",
    show_default=True,
    type=click.Path(path_type=pathlib.Path),
    help="Path to host registry inside the orchestrator repository.",
)
@click.option(
    "--branch",
    "branch_name",
    default="",
    show_default=False,
    help="Optional branch name for orchestrator registration pull request.",
)
@click.option(
    "--base-ref",
    default="",
    show_default=False,
    help="Optional base branch for orchestrator registration pull request.",
)
@click.option(
    "--title",
    "pr_title",
    default="",
    show_default=False,
    help="Optional orchestrator registration pull request title.",
)
@click.option(
    "--body",
    "pr_body",
    default="",
    show_default=False,
    help="Optional orchestrator registration pull request body.",
)
def init_host_cmd(
    host_repo: str,
    orchestrator_repo: str,
    lockfile: pathlib.Path,
    overwrite: bool,
    register: bool,
    token: str,
    registry_path: pathlib.Path,
    branch_name: str,
    base_ref: str,
    pr_title: str,
    pr_body: str,
) -> None:
    """Initialize host repository boilerplate and orchestrator registration.

    This command creates or refreshes a host lockfile and syncweaver host
    GitHub Actions workflows in the current repository. By default, it also
    opens a pull request in the orchestrator repository to add this host to
    host registry metadata.
    """
    cwd = pathlib.Path.cwd()
    try:
        init_result = init_host_in_directory(
            destination_dir=cwd,
            lockfile_path=lockfile,
            overwrite=overwrite,
            host_repo=host_repo,
            orchestrator_repo=orchestrator_repo,
        )

        click.echo(f"Initialized host lockfile: {init_result['lockfile']}")
        click.echo(f"Host repository: {init_result['host']}")
        click.echo(f"Orchestrator repository: {init_result['orchestrator']}")
        for workflow_path in init_result["workflows"]:
            click.echo(f"Wrote workflow: {workflow_path}")

        if register:
            resolved_host = str(init_result["host"]).strip()
            resolved_orchestrator = str(init_result["orchestrator"]).strip()
            if resolved_host.startswith("unknown/"):
                raise ValueError(
                    "Unable to infer host repository from git origin. "
                    "Pass --host-repo OWNER/REPO or run --no-register."
                )
            resolved_token = resolve_github_token(token)
            registration_result = register_host_with_orchestrator_repository(
                orchestrator_repo=resolved_orchestrator,
                host_repo=resolved_host,
                lockfile_path=str(init_result["lockfile"]),
                github_token=resolved_token,
                host_registry_path=registry_path,
                branch_name=branch_name,
                base_ref=base_ref,
                pr_title=pr_title,
                pr_body=pr_body,
            )
            created_pr = bool(registration_result.get("created_pr", False))
            click.echo(f"Orchestrator branch: {registration_result['branch']}")
            click.echo(f"Orchestrator base ref: {registration_result['base_ref']}")
            if created_pr:
                click.echo(f"Pull request: {registration_result['pr_url']}")
            else:
                click.echo("Host already registered in orchestrator registry.")
    except (FileExistsError, OSError, RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
