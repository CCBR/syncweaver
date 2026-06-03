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
    repos = lock_data.get("repos", {})
    repo_entry = repos.get(repo_url)
    if not repo_entry:
        raise KeyError(f"Repository is not tracked in lockfile: {repo_url}")

    sources = repo_entry.get("sources", {})
    source_entry = sources.get(source_path)
    if not source_entry:
        raise KeyError(
            f"Source path is not tracked for repository {repo_url}: {source_path}"
        )
    return source_entry


def _iter_relative_files(
    root: pathlib.Path, excluded_dir: pathlib.Path
) -> set[pathlib.Path]:
    """Collect relative file paths under root while excluding excluded_dir."""
    files: set[pathlib.Path] = set()
    for candidate in root.rglob("*"):
        if not candidate.is_file():
            continue
        if excluded_dir in candidate.parents or candidate == excluded_dir:
            continue
        files.add(candidate.relative_to(root))
    return files


def _read_text_lines(path: pathlib.Path) -> list[str]:
    """Read file text as lines, preserving line terminators when present."""
    if not path.exists():
        return []
    return path.read_text(errors="surrogateescape").splitlines(keepends=True)


def _unified_diff(
    before_path: pathlib.Path,
    after_path: pathlib.Path,
    relative_path: pathlib.Path,
) -> str:
    """Generate a deterministic unified diff chunk for one file."""
    before_lines = _read_text_lines(before_path)
    after_lines = _read_text_lines(after_path)
    if before_lines == after_lines:
        return ""

    diff_lines = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=f"a/{relative_path.as_posix()}",
        tofile=f"b/{relative_path.as_posix()}",
    )
    return "".join(diff_lines)


def _default_patch_filename(repo_url: str, source_path: pathlib.Path) -> str:
    """Build a deterministic patch name from the tracked source identifier."""
    del repo_url
    source_identifier = source_path.as_posix().lstrip("./")
    return f"{source_identifier.replace('/', '-')}.diff"


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

        excluded_dir = destination / ".syncweaver"
        baseline_files = _iter_relative_files(
            temp_repo, excluded_dir=temp_repo / ".git"
        )
        current_files = _iter_relative_files(destination, excluded_dir=excluded_dir)
        all_files = sorted(baseline_files | current_files, key=lambda p: p.as_posix())

        chunks: list[str] = []
        for relative_path in all_files:
            before_file = temp_repo / relative_path
            after_file = destination / relative_path
            chunk = _unified_diff(before_file, after_file, relative_path)
            if chunk:
                chunks.append(chunk)

    patch_text = "".join(chunks)
    if patch_text:
        _validate_patch_structure(patch_text)
        _validate_patch_reverse_apply(patch_text, destination)
        patch_output = cwd / patch_file
        patch_output.parent.mkdir(parents=True, exist_ok=True)
        patch_output.write_text(patch_text)
        source_entry["patch"] = patch_file.as_posix()
        write_lockfile(lockfile, lock_data)
        return patch_output

    existing_patch = source_entry.get("patch")
    if existing_patch:
        patch_path = cwd / pathlib.Path(existing_patch)
        if patch_path.exists():
            patch_path.unlink()
        source_entry.pop("patch", None)
        write_lockfile(lockfile, lock_data)

    return None


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

    for repo_entry in lock_data.get("repos", {}).values():
        for source_entry in repo_entry.get("sources", {}).values():
            if source_entry.get("patch") != patch_key:
                continue
            patch_audit = source_entry.setdefault("patch_audit", {})
            patch_audit[patch_key] = {
                "status": "rejected",
                "pr_url": pr_url,
                "reason": reason,
                "annotated_at": dt.datetime.now(tz=dt.UTC).isoformat(),
            }
            write_lockfile(lockfile, lock_data)
            return patch_key, str(lockfile)

    raise KeyError(f"Patch path is not tracked in lockfile: {patch_key}")


def list_patches(
    path: pathlib.Path, lockfile_path: pathlib.Path
) -> list[tuple[str, str, str]]:
    """List recorded patches for a tracked source path."""
    cwd = pathlib.Path.cwd()
    lockfile = cwd / lockfile_path
    lock_data = load_existing_lockfile(lockfile)

    source_key = path.as_posix()
    records: list[tuple[str, str, str]] = []
    for repo_url, repo_entry in lock_data.get("repos", {}).items():
        source_entry = repo_entry.get("sources", {}).get(source_key)
        if not source_entry:
            continue
        patch_path = source_entry.get("patch")
        if patch_path:
            records.append((repo_url, source_key, patch_path))

    return records
