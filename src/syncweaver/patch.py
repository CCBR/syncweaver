"""Patch lifecycle logic for syncweaver."""

from __future__ import annotations

import datetime as dt
import difflib
import pathlib
import shutil
import subprocess
import tempfile

from syncweaver.git import run_git
from syncweaver.lockfile import load_existing_lockfile, write_lockfile


def _source_entry(lock_data: dict, repo_url: str, source_path: str) -> dict:
    """Return the lockfile source entry for a given repository URL and path."""
    sources = lock_data.get("sources", {})
    source_entry = sources.get(source_path)
    if not source_entry:
        raise KeyError(f"Source path is not tracked in lockfile: {source_path}")

    tracked_repo_url = source_entry.get("repo_url")
    if tracked_repo_url != repo_url:
        raise KeyError(
            "Tracked source path maps to a different repository URL: "
            f"{source_path} -> {tracked_repo_url}"
        )
    return source_entry


def _iter_relative_files(
    root: pathlib.Path, excluded_dir: pathlib.Path
) -> set[pathlib.Path]:
    """Collect relative file paths under root while excluding excluded_dir."""
    files: set[pathlib.Path] = set()
    for candidate in root.rglob("*"):
        is_excluded = excluded_dir in candidate.parents or candidate == excluded_dir
        if candidate.is_file() and not is_excluded:
            files.add(candidate.relative_to(root))
    return files


def _read_text_lines(path: pathlib.Path) -> list[str]:
    """Read file text as lines, preserving line terminators when present."""
    lines: list[str] = []
    if not path.exists():
        lines = []
    else:
        lines = path.read_text(errors="surrogateescape").splitlines(keepends=True)
    return lines


def _unified_diff(
    before_path: pathlib.Path,
    after_path: pathlib.Path,
    relative_path: pathlib.Path,
) -> str:
    """Generate a deterministic unified diff chunk for one file."""
    before_lines = _read_text_lines(before_path)
    after_lines = _read_text_lines(after_path)
    diff_text = ""
    if before_lines != after_lines:
        diff_lines = difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{relative_path.as_posix()}",
            tofile=f"b/{relative_path.as_posix()}",
        )
        diff_text = "".join(diff_lines)
    return diff_text


def _default_patch_filename(repo_url: str, source_path: pathlib.Path) -> str:
    """Build a deterministic patch name from the tracked source identifier."""
    del repo_url
    source_identifier = source_path.as_posix().lstrip("./")
    return f"{source_identifier.replace('/', '-')}.diff"


def _resolve_baseline_root(temp_repo: pathlib.Path, source_entry: dict) -> pathlib.Path:
    """Resolve baseline source root from optional remote_subdir lock metadata."""
    baseline_root = temp_repo
    remote_subdir = source_entry.get("remote_subdir")
    if remote_subdir:
        normalized = pathlib.PurePosixPath(str(remote_subdir).strip("/"))
        if str(normalized) in {"", "."}:
            raise RuntimeError("Lockfile remote_subdir cannot be empty or '.'")

        baseline_root = temp_repo / pathlib.Path(*normalized.parts)
        if not baseline_root.exists() or not baseline_root.is_dir():
            raise RuntimeError(
                "Tracked remote_subdir is missing in baseline repository: "
                f"{remote_subdir}"
            )
    return baseline_root


def _validate_patch_structure(patch_text: str) -> None:
    """Validate basic unified diff structure before writing a patch file."""
    lines = patch_text.splitlines()
    if not lines:
        raise RuntimeError("Generated patch is empty")

    index = 0
    file_blocks = 0
    while index < len(lines):
        line = lines[index]
        if not line.startswith("--- "):
            raise RuntimeError(
                "Generated patch has invalid structure: expected a '--- ' file header"
            )

        if index + 1 >= len(lines) or not lines[index + 1].startswith("+++ "):
            raise RuntimeError(
                "Generated patch has invalid structure: missing matching '+++ ' file header"
            )

        old_path = lines[index][4:].strip()
        new_path = lines[index + 1][4:].strip()
        if not old_path or not new_path:
            raise RuntimeError(
                "Generated patch has invalid structure: empty file path in header"
            )

        file_blocks += 1
        index += 2
        saw_hunk = False
        while index < len(lines) and not lines[index].startswith("--- "):
            if lines[index].startswith("@@ "):
                saw_hunk = True
            index += 1

        if not saw_hunk:
            raise RuntimeError(
                "Generated patch has invalid structure: file section missing '@@' hunks"
            )

    if file_blocks == 0:
        raise RuntimeError("Generated patch has no file sections")


def _validate_patch_reverse_apply(patch_text: str, destination: pathlib.Path) -> None:
    """Ensure generated patch cleanly reverse-applies to current vendored files."""
    with tempfile.TemporaryDirectory(prefix="syncweaver-patch-check-") as temp_dir:
        temp_root = pathlib.Path(temp_dir)
        temp_component = temp_root / "component"
        shutil.copytree(destination, temp_component)

        patch_file = temp_root / "candidate.diff"
        patch_file.write_text(patch_text)

        result = subprocess.run(
            [
                "git",
                "apply",
                "--reverse",
                "--check",
                "-p1",
                str(patch_file),
            ],
            cwd=temp_component,
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(
                "Generated patch failed reverse-apply check against current "
                f"vendored files: {stderr}"
            )


def create_patch(
    source_path: pathlib.Path,
    repo_url: str,
    lockfile_path: pathlib.Path,
    patch_dir_override: pathlib.Path | None,
) -> pathlib.Path | None:
    """Create or update a canonical patch file for a tracked vendored source."""
    cwd = pathlib.Path.cwd()
    lockfile = cwd / lockfile_path
    lock_data = load_existing_lockfile(lockfile)

    source_key = source_path.as_posix()
    source_entry = _source_entry(lock_data, repo_url, source_key)
    git_sha = source_entry.get("git_sha")
    if not git_sha:
        raise KeyError(f"Missing git_sha in lockfile for {repo_url} at {source_key}")

    destination = cwd / source_path
    if not destination.exists() or not destination.is_dir():
        raise FileNotFoundError(f"Source path does not exist: {source_path}")

    if patch_dir_override is None:
        patch_dir = source_path / ".syncweaver"
    else:
        patch_dir = patch_dir_override
    patch_file = patch_dir / _default_patch_filename(repo_url, source_path)

    with tempfile.TemporaryDirectory(prefix="syncweaver-patch-") as temp_dir:
        temp_repo = pathlib.Path(temp_dir) / "repo"
        run_git(["clone", "--quiet", "--no-checkout", repo_url, str(temp_repo)])
        run_git(["-C", str(temp_repo), "checkout", "--quiet", git_sha])
        baseline_root = _resolve_baseline_root(temp_repo, source_entry)

        excluded_dir = destination / ".syncweaver"
        baseline_files = _iter_relative_files(
            baseline_root, excluded_dir=baseline_root / ".git"
        )
        current_files = _iter_relative_files(destination, excluded_dir=excluded_dir)
        all_files = sorted(baseline_files | current_files, key=lambda p: p.as_posix())

        chunks: list[str] = []
        for relative_path in all_files:
            before_file = baseline_root / relative_path
            after_file = destination / relative_path
            chunk = _unified_diff(before_file, after_file, relative_path)
            if chunk:
                chunks.append(chunk)

    patch_output: pathlib.Path | None = None
    patch_text = "".join(chunks)
    if patch_text:
        _validate_patch_structure(patch_text)
        _validate_patch_reverse_apply(patch_text, destination)
        patch_output = cwd / patch_file
        patch_output.parent.mkdir(parents=True, exist_ok=True)
        patch_output.write_text(patch_text)
        source_entry["patch"] = patch_file.as_posix()
        write_lockfile(lockfile, lock_data)
    else:
        existing_patch = source_entry.get("patch")
        if existing_patch:
            patch_path = cwd / pathlib.Path(existing_patch)
            if patch_path.exists():
                patch_path.unlink()
            source_entry.pop("patch", None)
            write_lockfile(lockfile, lock_data)

    return patch_output


def annotate_rejected_patch(
    patch_path: pathlib.Path,
    pr_url: str,
    reason: str,
    lockfile_path: pathlib.Path,
) -> tuple[str, str]:
    """Annotate a tracked patch as rejected in lockfile extension metadata."""
    cwd = pathlib.Path.cwd()
    lockfile = cwd / lockfile_path
    lock_data = load_existing_lockfile(lockfile)
    patch_key = patch_path.as_posix()

    found_patch = False
    for source_entry in lock_data.get("sources", {}).values():
        if source_entry.get("patch") == patch_key:
            patch_audit = source_entry.setdefault("patch_audit", {})
            patch_audit[patch_key] = {
                "status": "rejected",
                "pr_url": pr_url,
                "reason": reason,
                "annotated_at": dt.datetime.now(tz=dt.UTC).isoformat(),
            }
            write_lockfile(lockfile, lock_data)
            found_patch = True

    if not found_patch:
        raise KeyError(f"Patch path is not tracked in lockfile: {patch_key}")
    return patch_key, str(lockfile)


def list_patches(
    path: pathlib.Path, lockfile_path: pathlib.Path
) -> list[tuple[str, str, str]]:
    """List recorded patches for a tracked source path."""
    cwd = pathlib.Path.cwd()
    lockfile = cwd / lockfile_path
    lock_data = load_existing_lockfile(lockfile)

    source_key = path.as_posix()
    records: list[tuple[str, str, str]] = []
    source_entry = lock_data.get("sources", {}).get(source_key)
    if source_entry:
        patch_path = source_entry.get("patch")
        if patch_path:
            repo_url = source_entry.get("repo_url", "")
            records.append((repo_url, source_key, patch_path))

    return records
