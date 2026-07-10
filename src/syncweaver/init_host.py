"""Initialize syncweaver host repository content and orchestrator registration."""

from __future__ import annotations

import pathlib
import tempfile

import requests
import yaml

from syncweaver.constants import DEFAULT_LOCKFILE_PATH
from syncweaver.git import build_github_git_env, run_git
from syncweaver.lockfile import read_lockfile, write_lockfile
from syncweaver.templates import use_template


DEFAULT_HOST_WORKFLOW_TEMPLATES = [
    "syncweaver-host-update.yml",
    "syncweaver-host-contribute-patch.yml",
]


def _github_headers(github_token: str) -> dict[str, str]:
    """Build GitHub API headers for authenticated requests."""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    return headers


def _split_repo_slug(repo_slug: str) -> tuple[str, str]:
    """Validate and split OWNER/REPO slug into owner and repository name."""
    repo_slug_input = repo_slug.strip()
    owner = ""
    repository = ""

    if repo_slug_input.count("/") == 1:
        owner_candidate, repository_candidate = repo_slug_input.split("/", 1)
        owner = owner_candidate.strip()
        repository = repository_candidate.strip()

    if (not owner) or (not repository):
        raise ValueError("Repository must be in OWNER/REPO format")

    result = (owner, repository)
    return result


def _sanitize_branch_component(value: str) -> str:
    """Convert free text into a branch-safe identifier component."""
    lowered = value.strip().lower()
    normalized = lowered.replace("/", "-")
    normalized = normalized.replace("_", "-")
    normalized = normalized.replace(" ", "-")
    output_chars: list[str] = []
    for char in normalized:
        is_valid = char.isalnum() or char in {"-", "."}
        if is_valid:
            output_chars.append(char)
        else:
            output_chars.append("-")
    sanitized = "".join(output_chars).strip("-.")
    if not sanitized:
        sanitized = "host"
    return sanitized


def _load_host_registry(host_registry_path: pathlib.Path) -> tuple[dict, list[dict]]:
    """Load orchestrator host registry document and normalize host entries."""
    registry_data: dict = {}
    if host_registry_path.exists():
        raw_content = host_registry_path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(raw_content) or {}
        if not isinstance(parsed, dict):
            raise ValueError("orchestrator host registry must be a YAML mapping")
        registry_data = parsed

    hosts = registry_data.get("hosts", [])
    if not isinstance(hosts, list):
        raise ValueError("orchestrator host registry key 'hosts' must be a list")

    normalized_hosts: list[dict] = []
    for host in hosts:
        if isinstance(host, dict):
            normalized_hosts.append(dict(host))

    result = (registry_data, normalized_hosts)
    return result


def _upsert_host_registry_entry(
    host_entries: list[dict],
    host_repo: str,
    lockfile_path: str,
) -> bool:
    """Insert or update the host entry in orchestrator registry data."""
    normalized_lockfile = lockfile_path.strip()
    lockfile_is_default = normalized_lockfile == DEFAULT_LOCKFILE_PATH

    has_match = False
    changed = False

    for host_entry in host_entries:
        repository = str(host_entry.get("repository", "")).strip()
        if repository == host_repo:
            has_match = True
            existing_lockfile = str(
                host_entry.get("lockfile", DEFAULT_LOCKFILE_PATH)
            ).strip()

            if lockfile_is_default:
                has_explicit_lockfile = "lockfile" in host_entry
                if has_explicit_lockfile:
                    del host_entry["lockfile"]
                    changed = True
            elif existing_lockfile != normalized_lockfile:
                host_entry["lockfile"] = normalized_lockfile
                changed = True

    if not has_match:
        entry: dict[str, str] = {"repository": host_repo}
        if not lockfile_is_default:
            entry["lockfile"] = normalized_lockfile
        host_entries.append(entry)
        changed = True

    return changed


def init_host_in_directory(
    destination_dir: pathlib.Path,
    *,
    lockfile_path: pathlib.Path = pathlib.Path(DEFAULT_LOCKFILE_PATH),
    overwrite: bool = False,
    host_repo: str = "",
    orchestrator_repo: str = "",
) -> dict[str, str | list[str]]:
    """Create lockfile and host workflow boilerplate in a local repository.

    Args:
        destination_dir: Host repository root directory.
        lockfile_path: Lockfile path relative to destination_dir.
        overwrite: Whether existing files may be overwritten.
        host_repo: Optional host repository override in OWNER/REPO format.
        orchestrator_repo: Optional orchestrator repository override in OWNER/REPO
            format.

    Returns:
        dict[str, str | list[str]]: Initialization metadata including host,
            orchestrator, lockfile path, and copied workflow files.
    """
    destination_dir_resolved = destination_dir.resolve()
    lockfile_relpath = pathlib.PurePosixPath(lockfile_path.as_posix())
    lockfile_full_path = destination_dir_resolved / lockfile_relpath

    if lockfile_full_path.exists() and not overwrite:
        raise FileExistsError(
            f"{lockfile_relpath} already exists. Pass --overwrite to replace it."
        )

    workflow_output_dir = destination_dir_resolved / ".github" / "workflows"
    if not overwrite:
        conflicting_workflows: list[pathlib.Path] = []
        for template_name in DEFAULT_HOST_WORKFLOW_TEMPLATES:
            workflow_target = workflow_output_dir / template_name
            if workflow_target.exists():
                conflicting_workflows.append(workflow_target)
        if conflicting_workflows:
            conflict_csv = ", ".join(str(path) for path in conflicting_workflows)
            raise FileExistsError(
                "Refusing to overwrite existing workflow files. "
                f"Pass --overwrite to replace: {conflict_csv}"
            )

    lock_data = read_lockfile(
        lockfile=lockfile_full_path,
        cwd=destination_dir_resolved,
        run_git=run_git,
    )

    host_repo_input = host_repo.strip()
    if host_repo_input:
        _split_repo_slug(host_repo_input)
        lock_data["host"] = host_repo_input

    orchestrator_repo_input = orchestrator_repo.strip()
    if orchestrator_repo_input:
        _split_repo_slug(orchestrator_repo_input)
        lock_data["orchestrator"] = orchestrator_repo_input

    sources = lock_data.get("sources")
    if not isinstance(sources, dict):
        lock_data["sources"] = {}

    write_lockfile(lockfile_full_path, lock_data)

    copied_workflows: list[str] = []
    for template_name in DEFAULT_HOST_WORKFLOW_TEMPLATES:
        written_path = use_template(
            template_name,
            output_dir=workflow_output_dir,
            overwrite=overwrite,
        )
        copied_workflows.append(
            written_path.relative_to(destination_dir_resolved).as_posix()
        )

    result = {
        "host": str(lock_data.get("host", "")).strip(),
        "orchestrator": str(lock_data.get("orchestrator", "")).strip(),
        "lockfile": lockfile_relpath.as_posix(),
        "workflows": copied_workflows,
    }
    return result


def register_host_with_orchestrator_repository(
    *,
    orchestrator_repo: str,
    host_repo: str,
    lockfile_path: str,
    github_token: str,
    host_registry_path: pathlib.Path = pathlib.Path(".github/host-repositories.yml"),
    branch_name: str = "",
    base_ref: str = "",
    pr_title: str = "",
    pr_body: str = "",
) -> dict[str, str | bool]:
    """Open a PR to register a host repository in orchestrator host registry.

    Args:
        orchestrator_repo: Orchestrator repository in OWNER/REPO format.
        host_repo: Host repository in OWNER/REPO format.
        lockfile_path: Lockfile path tracked by the orchestrator registry.
        github_token: GitHub token with permission to push and open pull requests.
        host_registry_path: Registry path relative to orchestrator repository root.
        branch_name: Optional branch name for the registry change.
        base_ref: Optional pull request base branch override.
        pr_title: Optional pull request title override.
        pr_body: Optional pull request body override.

    Returns:
        dict[str, str | bool]: Registration result metadata.
    """
    orchestrator_repo_input = orchestrator_repo.strip()
    host_repo_input = host_repo.strip()
    lockfile_path_input = lockfile_path.strip()

    _split_repo_slug(orchestrator_repo_input)
    _split_repo_slug(host_repo_input)

    if not lockfile_path_input:
        raise ValueError("lockfile path must be a non-empty relative path")

    owner, repository = _split_repo_slug(orchestrator_repo_input)

    headers = _github_headers(github_token)
    repo_response = requests.get(
        f"https://api.github.com/repos/{owner}/{repository}",
        headers=headers,
        timeout=30,
    )
    if not repo_response.ok:
        raise RuntimeError(
            f"GitHub API error {repo_response.status_code} loading repository "
            f"{orchestrator_repo_input}: {repo_response.text}"
        )

    repo_metadata = repo_response.json()
    clone_url = str(repo_metadata.get("clone_url", "")).strip()
    if not clone_url:
        clone_url = f"https://github.com/{owner}/{repository}.git"

    resolved_base_ref = (
        base_ref.strip()
        or str(repo_metadata.get("default_branch", "")).strip()
        or "main"
    )

    branch_stub = _sanitize_branch_component(host_repo_input)
    resolved_branch_name = branch_name.strip() or f"syncweaver/init-host/{branch_stub}"
    resolved_pr_title = (
        pr_title.strip() or f"chore(syncweaver): register host {host_repo_input}"
    )
    default_pr_body = (
        "Register a new syncweaver host repository in orchestrator registry.\n\n"
        f"- host repository: {host_repo_input}"
    )
    if lockfile_path_input != DEFAULT_LOCKFILE_PATH:
        default_pr_body = f"{default_pr_body}\n- lockfile: {lockfile_path_input}"
    resolved_pr_body = pr_body.strip() or default_pr_body

    has_registry_changes = False
    git_env = build_github_git_env(github_token)
    redacted_values = [github_token]

    with tempfile.TemporaryDirectory(prefix="syncweaver-init-host-") as temp_dir:
        repo_dir = pathlib.Path(temp_dir) / "repo"
        run_git(
            ["clone", "--quiet", clone_url, str(repo_dir)],
            env=git_env,
            redacted_values=redacted_values,
        )
        run_git(
            [
                "-C",
                str(repo_dir),
                "checkout",
                "-B",
                resolved_branch_name,
                f"origin/{resolved_base_ref}",
            ],
            env=git_env,
            redacted_values=redacted_values,
        )
        run_git(
            ["-C", str(repo_dir), "config", "user.name", "github-actions[bot]"],
            env=git_env,
            redacted_values=redacted_values,
        )
        run_git(
            [
                "-C",
                str(repo_dir),
                "config",
                "user.email",
                "41898282+github-actions[bot]@users.noreply.github.com",
            ],
            env=git_env,
            redacted_values=redacted_values,
        )

        registry_full_path = repo_dir / host_registry_path
        registry_full_path.parent.mkdir(parents=True, exist_ok=True)

        registry_data, host_entries = _load_host_registry(registry_full_path)
        has_registry_changes = _upsert_host_registry_entry(
            host_entries=host_entries,
            host_repo=host_repo_input,
            lockfile_path=lockfile_path_input,
        )

        if has_registry_changes:
            registry_data["hosts"] = host_entries
            registry_full_path.write_text(
                yaml.safe_dump(registry_data, sort_keys=False),
                encoding="utf-8",
            )
            run_git(
                ["-C", str(repo_dir), "add", registry_full_path.as_posix()],
                env=git_env,
                redacted_values=redacted_values,
            )
            run_git(
                [
                    "-C",
                    str(repo_dir),
                    "commit",
                    "--message",
                    f"chore(syncweaver): register host {host_repo_input}",
                ],
                env=git_env,
                redacted_values=redacted_values,
            )
            run_git(
                [
                    "-C",
                    str(repo_dir),
                    "push",
                    "origin",
                    f"HEAD:refs/heads/{resolved_branch_name}",
                ],
                env=git_env,
                redacted_values=redacted_values,
            )

    pr_url = ""
    if has_registry_changes:
        pr_response = requests.post(
            f"https://api.github.com/repos/{owner}/{repository}/pulls",
            headers=headers,
            json={
                "title": resolved_pr_title,
                "head": resolved_branch_name,
                "base": resolved_base_ref,
                "body": resolved_pr_body,
            },
            timeout=30,
        )
        if not pr_response.ok:
            raise RuntimeError(
                f"GitHub API error {pr_response.status_code} opening pull request: "
                f"{pr_response.text}"
            )

        pr_url = str(pr_response.json().get("html_url", "")).strip()
        if not pr_url:
            raise RuntimeError("GitHub API did not return a pull request URL")

    result = {
        "orchestrator_repository": orchestrator_repo_input,
        "host_repository": host_repo_input,
        "lockfile": lockfile_path_input,
        "branch": resolved_branch_name,
        "base_ref": resolved_base_ref,
        "created_pr": has_registry_changes,
        "pr_url": pr_url,
    }
    return result
