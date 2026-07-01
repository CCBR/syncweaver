"""CLI command for updating a tracked external repository in a host repository."""

from __future__ import annotations

import json
import pathlib
import shutil
import tempfile
import subprocess

import click

from syncweaver.cli.add import _copy_checked_out_repo, _resolve_remote_source_path
from syncweaver.git import run_git
from syncweaver.lockfile import load_existing_lockfile, write_lockfile
from syncweaver.patch import create_patch
from syncweaver.util import format_subprocess_error


def _apply_tracked_patch(
    source_entry: dict,
    checkout_root: pathlib.Path,
    remote_subdir: str | None,
    host_root: pathlib.Path,
    patch_text_backup: str,
) -> tuple[pathlib.Path | None, bool]:
    """Apply a tracked host patch to a temporary repository checkout."""
    patch_value = str(source_entry.get("patch", "")).strip()
    patch_file: pathlib.Path | None = None
    patch_applied = False
    if patch_value:
        host_root_resolved = host_root.resolve()
        patch_file = (host_root / pathlib.Path(patch_value)).resolve()
        if not patch_file.is_relative_to(host_root_resolved):
            raise ValueError(
                "Resolved patch path must remain within the host repository: "
                f"{patch_value}"
            )
        apply_args = [
            "-C",
            str(checkout_root),
            "apply",
            "--whitespace=nowarn",
            "-p1",
            *(
                [
                    "--directory",
                    pathlib.PurePosixPath(remote_subdir.strip("/")).as_posix(),
                ]
                if remote_subdir
                else []
            ),
        ]
        if patch_file.is_file():
            run_git([*apply_args, str(patch_file)])
            patch_applied = True
        elif patch_text_backup:
            with tempfile.TemporaryDirectory(
                prefix="syncweaver-update-patch-"
            ) as temp_dir:
                temp_patch = pathlib.Path(temp_dir) / "tracked.diff"
                temp_patch.write_text(patch_text_backup)
                run_git([*apply_args, str(temp_patch)])
                patch_applied = True
        else:
            raise FileNotFoundError(
                f"Tracked patch file does not exist in host repository: {patch_value}"
            )
    return patch_file, patch_applied


def _normalize_remote_subdir(remote_subdir: str | None) -> str:
    """Normalize optional remote_subdir to a comparable POSIX string."""
    normalized = ""
    if remote_subdir is not None:
        candidate = remote_subdir.strip().strip("/")
        if candidate:
            normalized = pathlib.PurePosixPath(candidate).as_posix()
    return normalized


def _has_relevant_source_changes(
    checkout_root: pathlib.Path,
    previous_git_sha: str,
    target_git_sha: str,
    normalized_remote_subdir: str,
) -> bool:
    """Check whether source changes affect the tracked scope for update.

    Args:
        checkout_root (pathlib.Path): Temporary local clone path.
        previous_git_sha (str): Previously tracked commit SHA.
        target_git_sha (str): Candidate commit SHA.
        normalized_remote_subdir (str): Normalized tracked subdirectory.

    Returns:
        bool: True when relevant files changed between commits.
    """
    previous_sha = previous_git_sha.strip().lower()
    target_sha = target_git_sha.strip().lower()
    has_changes = True

    if previous_sha and (previous_sha == target_sha):
        has_changes = False
    elif previous_sha:
        diff_args = [
            "-C",
            str(checkout_root),
            "diff",
            "--name-only",
            previous_sha,
            target_sha,
        ]
        if normalized_remote_subdir:
            diff_args.extend(["--", normalized_remote_subdir])
        diff_output = run_git(diff_args)
        has_changes = bool(diff_output.strip())

    return has_changes


def update_external_repository(
    destination_path: pathlib.Path,
    ref: str | None,
    remote_subdir: str | None,
    patch_conflict_strategy: str,
    lockfile_path: pathlib.Path,
) -> tuple[pathlib.Path, pathlib.Path, str, str, bool, bool]:
    """Update a tracked external repository and refresh lockfile metadata."""
    cwd = pathlib.Path.cwd()
    destination = cwd / destination_path
    lockfile = cwd / lockfile_path

    lock_data = load_existing_lockfile(lockfile)
    source_key = destination_path.as_posix()
    source_entry = lock_data.get("sources", {}).get(source_key)
    if not source_entry:
        raise KeyError(f"Source path is not tracked in lockfile: {source_key}")

    tracked_patch_text = ""
    tracked_patch_value = str(source_entry.get("patch", "")).strip()
    patch_apply_warning = False
    if tracked_patch_value:
        host_root_resolved = cwd.resolve()
        tracked_patch_file = (cwd / pathlib.Path(tracked_patch_value)).resolve()
        if not tracked_patch_file.is_relative_to(host_root_resolved):
            raise ValueError(
                "Resolved patch path must remain within the host repository: "
                f"{tracked_patch_value}"
            )
        if tracked_patch_file.is_file():
            tracked_patch_text = tracked_patch_file.read_text()

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
    normalized_selected_subdir = _normalize_remote_subdir(selected_remote_subdir)
    normalized_previous_subdir = _normalize_remote_subdir(
        str(source_entry.get("remote_subdir", "")).strip()
    )

    previous_git_sha = str(source_entry.get("git_sha", "")).strip().lower()
    has_relevant_changes = True
    no_changes_detected = False
    should_refresh = True

    with tempfile.TemporaryDirectory(prefix="syncweaver-update-") as temp_dir:
        temp_repo = pathlib.Path(temp_dir) / "repo"
        run_git(["clone", "--quiet", "--no-checkout", repo_url, str(temp_repo)])
        run_git(
            [
                "-C",
                str(temp_repo),
                "fetch",
                "origin",
                selected_ref,
            ]
        )
        run_git(["-C", str(temp_repo), "checkout", "--quiet", "FETCH_HEAD"])

        git_sha = run_git(["-C", str(temp_repo), "rev-parse", "HEAD"])
        has_relevant_changes = _has_relevant_source_changes(
            checkout_root=temp_repo,
            previous_git_sha=previous_git_sha,
            target_git_sha=git_sha,
            normalized_remote_subdir=normalized_selected_subdir,
        )
        should_refresh = has_relevant_changes or (
            normalized_selected_subdir != normalized_previous_subdir
        )

        if should_refresh:
            if destination.exists():
                shutil.rmtree(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)

            source_root = _resolve_remote_source_path(temp_repo, selected_remote_subdir)
            try:
                _apply_tracked_patch(
                    source_entry=source_entry,
                    checkout_root=temp_repo,
                    remote_subdir=selected_remote_subdir,
                    host_root=cwd,
                    patch_text_backup=tracked_patch_text,
                )
            except RuntimeError:
                if patch_conflict_strategy == "warn":
                    patch_apply_warning = True
                else:
                    raise
            _copy_checked_out_repo(source_root, destination)
        else:
            no_changes_detected = True

    if tracked_patch_value and tracked_patch_text:
        tracked_patch_file = (cwd / pathlib.Path(tracked_patch_value)).resolve()
        if not tracked_patch_file.exists():
            tracked_patch_file.parent.mkdir(parents=True, exist_ok=True)
            tracked_patch_file.write_text(tracked_patch_text)

    if should_refresh:
        source_entry["ref"] = selected_ref
        source_entry["git_sha"] = git_sha
        if normalized_selected_subdir:
            source_entry["remote_subdir"] = normalized_selected_subdir
        else:
            source_entry.pop("remote_subdir", None)
        write_lockfile(lockfile, lock_data)

        if tracked_patch_value and not patch_apply_warning:
            tracked_patch_dir = pathlib.Path(tracked_patch_value).parent
            create_patch(
                source_path=destination_path,
                repo_url=repo_url,
                lockfile_path=lockfile_path,
                patch_dir_override=tracked_patch_dir,
            )

    return (
        destination,
        lockfile,
        selected_ref,
        git_sha,
        patch_apply_warning,
        no_changes_detected,
    )


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
    "--patch-conflict-strategy",
    type=click.Choice(["fail", "warn"], case_sensitive=False),
    default="fail",
    show_default=True,
    help=(
        "Behavior when tracked patch reapply fails during update. "
        "Use 'fail' to abort update or 'warn' to continue with unpatched files."
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
    patch_conflict_strategy: str,
    lockfile: pathlib.Path,
) -> None:
    """Update a tracked external repository in the current host repository."""
    try:
        dest, lock_path, selected_ref, git_sha, patch_apply_warning, no_changes = (
            update_external_repository(
                destination_path=destination_path,
                ref=ref,
                remote_subdir=remote_subdir,
                patch_conflict_strategy=patch_conflict_strategy.lower(),
                lockfile_path=lockfile,
            )
        )
    except (
        FileNotFoundError,
        KeyError,
        RuntimeError,
        subprocess.CalledProcessError,
        ValueError,
        json.JSONDecodeError,
        OSError,
    ) as exc:
        if isinstance(exc, subprocess.CalledProcessError):
            raise click.ClickException(format_subprocess_error(exc)) from exc
        raise click.ClickException(str(exc)) from exc

    if no_changes:
        click.echo(
            "No changes detected for tracked path; leaving vendored files and "
            "lock metadata unchanged."
        )
    else:
        click.echo(f"Updated vendored repository in {dest}")
        click.echo(f"Updated {lock_path} with ref {selected_ref} at {git_sha}")
        if patch_apply_warning:
            click.echo(
                "Warning: tracked patch failed to reapply; continued update with "
                "unpatched upstream files."
            )
