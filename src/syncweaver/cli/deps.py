"""Dependency analysis CLI commands."""

from __future__ import annotations

import json
import pathlib
import subprocess

import click

from syncweaver.dependency_analysis import (
    DEFAULT_FUNCTRACER_IMAGE_TAG,
    FUNCTRACER_BACKEND_DOCKER,
    FUNCTRACER_BACKEND_LOCAL,
    FUNCTRACER_BACKEND_SINGULARITY,
    analyze_source_dependencies,
)
from syncweaver.host_source_update import select_source_paths_for_update
from syncweaver.util import format_subprocess_error


@click.group("deps")
def deps_group() -> None:
    """Analyze source dependencies for host repository integration."""


@deps_group.command("analyze")
@click.option(
    "--source-path",
    required=True,
    type=click.Path(path_type=pathlib.Path),
    help="Tracked source path in host repository, e.g. code/package1.",
)
@click.option(
    "--host-repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, path_type=pathlib.Path),
    help="Path to host repository root.",
)
@click.option(
    "--source-type",
    default="auto",
    show_default=True,
    type=click.Choice(["auto", "r_package", "python_package"], case_sensitive=False),
    help="Dependency analyzer source type routing.",
)
@click.option(
    "--entry-script",
    multiple=True,
    type=click.Path(path_type=pathlib.Path),
    help="Optional host script to analyze (repeatable).",
)
@click.option(
    "--repository",
    default="",
    show_default=True,
    help="Optional source repository URL for release impact analysis.",
)
@click.option(
    "--release-tag",
    default="",
    show_default=True,
    help="Optional candidate release tag/ref for impact analysis.",
)
@click.option(
    "--previous-tag",
    default="",
    show_default=True,
    help="Optional baseline release tag/ref for impact analysis.",
)
@click.option(
    "--package-name",
    default="",
    show_default=True,
    help="Optional package name override for functracer.",
)
def analyze_cmd(
    source_path: pathlib.Path,
    host_repo: pathlib.Path,
    source_type: str,
    entry_script: tuple[pathlib.Path, ...],
    repository: str,
    release_tag: str,
    previous_tag: str,
    package_name: str,
) -> None:
    """Analyze source usage and optional release impact in host scripts."""
    source_path_input = source_path.as_posix().strip()
    entry_scripts: list[str] = []
    for script_path in entry_script:
        entry_scripts.append(script_path.as_posix())

    try:
        result = analyze_source_dependencies(
            host_repo_path=host_repo,
            source_path=source_path_input,
            source_type_input=source_type,
            entry_scripts=entry_scripts,
            repository=repository,
            release_tag=release_tag,
            previous_tag=previous_tag,
            package_name=package_name,
        )
    except (
        FileNotFoundError,
        ValueError,
        subprocess.CalledProcessError,
        OSError,
    ) as exc:
        if isinstance(exc, subprocess.CalledProcessError):
            raise click.ClickException(format_subprocess_error(exc)) from exc
        raise click.ClickException(str(exc)) from exc

    click.echo(json.dumps(result, indent=2, sort_keys=True))


@deps_group.command("select-update-paths")
@click.option(
    "--source-paths-json",
    required=True,
    help="JSON array of candidate source paths resolved from lockfile.",
)
@click.option(
    "--lockfile",
    default=".syncweaver-lock.json",
    show_default=True,
    type=click.Path(path_type=pathlib.Path),
    help="Lockfile path relative to host repository root.",
)
@click.option(
    "--source-ref",
    required=True,
    help="Candidate source ref for update impact analysis.",
)
@click.option(
    "--host-repo",
    default=".",
    show_default=True,
    type=click.Path(exists=True, file_okay=False, path_type=pathlib.Path),
    help="Path to host repository root.",
)
@click.option(
    "--functracer-entry-scripts",
    default="",
    show_default=True,
    help="Comma/newline-separated host entry scripts for functracer checks.",
)
@click.option(
    "--functracer-source-paths",
    default="",
    show_default=True,
    help="Optional comma/newline-separated source paths to gate with functracer.",
)
@click.option(
    "--functracer-backend",
    default=None,
    show_default=False,
    type=click.Choice(
        [
            FUNCTRACER_BACKEND_LOCAL,
            FUNCTRACER_BACKEND_DOCKER,
            FUNCTRACER_BACKEND_SINGULARITY,
        ],
        case_sensitive=False,
    ),
    help="Optional functracer backend (local, docker, singularity). When omitted, auto-detects from PATH in that order.",
)
@click.option(
    "--functracer-version",
    default="",
    show_default=False,
    help=f"Optional functracer version (e.g. {DEFAULT_FUNCTRACER_IMAGE_TAG} or any docker image tag). When omitted, falls back to {DEFAULT_FUNCTRACER_IMAGE_TAG}.",
)
@click.option(
    "--github-output",
    default=None,
    type=click.Path(path_type=pathlib.Path, dir_okay=False),
    help="Optional path to append GitHub Action output variables.",
)
def select_update_paths_cmd(
    source_paths_json: str,
    lockfile: pathlib.Path,
    source_ref: str,
    host_repo: pathlib.Path,
    functracer_entry_scripts: str,
    functracer_source_paths: str,
    functracer_backend: str,
    functracer_version: str,
    github_output: pathlib.Path | None,
) -> None:
    """Filter candidate source paths and emit selection JSON and optional outputs."""
    try:
        parsed_source_paths = json.loads(source_paths_json)
    except json.JSONDecodeError as exc:
        raise click.ClickException("source-paths-json must be valid JSON") from exc

    if not isinstance(parsed_source_paths, list):
        raise click.ClickException("source-paths-json must decode to a JSON array")

    source_paths: list[str] = []
    for source_path in parsed_source_paths:
        source_paths.append(str(source_path))

    lockfile_path = host_repo / lockfile
    normalized_functracer_backend = (
        functracer_backend.strip().lower() if functracer_backend else None
    )
    normalized_functracer_version = (
        functracer_version.strip() if functracer_version else None
    )
    try:
        selected_source_paths, skipped_source_paths = select_source_paths_for_update(
            source_paths=source_paths,
            lockfile_path=lockfile_path,
            source_ref_input=source_ref,
            host_repo_path=host_repo,
            functracer_entry_scripts_input=functracer_entry_scripts,
            functracer_source_paths_input=functracer_source_paths,
            functracer_backend=normalized_functracer_backend,
            functracer_image_tag=normalized_functracer_version,
        )
    except (
        FileNotFoundError,
        ValueError,
        subprocess.CalledProcessError,
        OSError,
    ) as exc:
        if isinstance(exc, subprocess.CalledProcessError):
            raise click.ClickException(format_subprocess_error(exc)) from exc
        raise click.ClickException(str(exc)) from exc

    payload = {
        "source_paths": selected_source_paths,
        "source_count": len(selected_source_paths),
        "skipped_source_paths": skipped_source_paths,
        "skipped_source_count": len(skipped_source_paths),
    }

    if github_output is not None:
        output_path = pathlib.Path(github_output)
        with output_path.open("a", encoding="utf-8") as fh:
            fh.write(f"source_paths={json.dumps(selected_source_paths)}\n")
            fh.write(f"source_count={len(selected_source_paths)}\n")
            fh.write(f"skipped_source_paths={json.dumps(skipped_source_paths)}\n")
            fh.write(f"skipped_source_count={len(skipped_source_paths)}\n")

    click.echo(json.dumps(payload, indent=2, sort_keys=True))
