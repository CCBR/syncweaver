"""Initialize syncweaver orchestrator repository content."""

from __future__ import annotations

import importlib.resources
import pathlib
import tempfile

import requests

from syncweaver.git import build_github_git_env, run_git


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


def _copy_tree_contents(
    source_dir: pathlib.Path,
    destination_dir: pathlib.Path,
    overwrite: bool,
) -> list[pathlib.Path]:
    """Copy all files under source_dir into destination_dir recursively."""
    source_files = sorted(path for path in source_dir.rglob("*") if path.is_file())
    destination_dir.mkdir(parents=True, exist_ok=True)

    conflicting_paths: list[pathlib.Path] = []
    if not overwrite:
        for source_file in source_files:
            relative_path = source_file.relative_to(source_dir)
            destination_path = destination_dir / relative_path
            if destination_path.exists():
                conflicting_paths.append(destination_path)

    if conflicting_paths:
        conflict_csv = ", ".join(str(path) for path in conflicting_paths)
        raise FileExistsError(
            "Refusing to overwrite existing files. "
            f"Use --overwrite to replace: {conflict_csv}"
        )

    copied_files: list[pathlib.Path] = []
    for source_file in source_files:
        relative_path = source_file.relative_to(source_dir)
        destination_path = destination_dir / relative_path
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(
            source_file.read_text(encoding="utf-8"), encoding="utf-8"
        )
        copied_files.append(destination_path)

    return copied_files


def init_orchestrator_in_directory(
    destination_dir: pathlib.Path,
    overwrite: bool = False,
) -> list[pathlib.Path]:
    """Copy packaged orchestrator template files into destination_dir.

    Args:
        destination_dir: Directory to receive orchestrator files.
        overwrite: Whether existing destination files may be overwritten.

    Returns:
        list[pathlib.Path]: Absolute paths of files copied into destination_dir.
    """
    copied_files: list[pathlib.Path] = []
    template_root = importlib.resources.files("syncweaver.templates") / "orchestrator"
    with importlib.resources.as_file(template_root) as source_dir:
        copied_files = _copy_tree_contents(
            source_dir=source_dir,
            destination_dir=destination_dir,
            overwrite=overwrite,
        )
    return copied_files


def _get_owner_type(owner: str, headers: dict[str, str]) -> str:
    """Lookup GitHub owner account type (User or Organization)."""
    owner_type = ""
    response = requests.get(
        f"https://api.github.com/users/{owner}",
        headers=headers,
        timeout=30,
    )
    if response.ok:
        owner_type = str(response.json().get("type", "")).strip() or "User"
    else:
        raise RuntimeError(
            f"GitHub API error {response.status_code} resolving owner '{owner}': "
            f"{response.text}"
        )
    return owner_type


def _get_authenticated_login(headers: dict[str, str]) -> str:
    """Resolve the login of the authenticated token owner."""
    login = ""
    response = requests.get("https://api.github.com/user", headers=headers, timeout=30)
    if response.ok:
        login = str(response.json().get("login", "")).strip()
    else:
        raise RuntimeError(
            "Unable to determine authenticated GitHub user: "
            f"{response.status_code} {response.text}"
        )
    if not login:
        raise RuntimeError("Unable to determine authenticated GitHub user login")
    return login


def _ensure_repository_exists(
    repo_slug: str,
    github_token: str,
    create_if_missing: bool,
    private: bool,
) -> tuple[dict, bool]:
    """Get repository metadata, creating the repository when requested."""
    owner, repository = _split_repo_slug(repo_slug)
    headers = _github_headers(github_token)

    created_repo = False
    repo_metadata: dict = {}
    get_response = requests.get(
        f"https://api.github.com/repos/{owner}/{repository}",
        headers=headers,
        timeout=30,
    )

    if get_response.ok:
        repo_metadata = get_response.json()
    elif get_response.status_code == 404 and create_if_missing:
        owner_type = _get_owner_type(owner=owner, headers=headers)
        create_payload = {
            "name": repository,
            "private": private,
            "auto_init": True,
        }
        create_url = ""
        if owner_type == "Organization":
            create_url = f"https://api.github.com/orgs/{owner}/repos"
        else:
            authenticated_login = _get_authenticated_login(headers=headers)
            if authenticated_login != owner:
                raise RuntimeError(
                    "Token user does not match requested repository owner. "
                    f"Token login: {authenticated_login}, requested owner: {owner}"
                )
            create_url = "https://api.github.com/user/repos"

        create_response = requests.post(
            create_url,
            headers=headers,
            json=create_payload,
            timeout=30,
        )
        if create_response.ok:
            repo_metadata = create_response.json()
            created_repo = True
        else:
            raise RuntimeError(
                f"GitHub API error {create_response.status_code} creating "
                f"repository {owner}/{repository}: {create_response.text}"
            )
    elif get_response.status_code == 404 and not create_if_missing:
        raise RuntimeError(
            f"Repository does not exist and creation is disabled: {owner}/{repository}"
        )
    else:
        raise RuntimeError(
            f"GitHub API error {get_response.status_code} loading repository "
            f"{owner}/{repository}: {get_response.text}"
        )

    result = (repo_metadata, created_repo)
    return result


def init_orchestrator_in_repository(
    repo_slug: str,
    github_token: str,
    *,
    branch_name: str = "syncweaver/init-orchestrator",
    base_ref: str = "",
    overwrite: bool = True,
    create_if_missing: bool = True,
    private: bool = True,
    pr_title: str = "",
    pr_body: str = "",
) -> dict[str, str | bool]:
    """Apply orchestrator templates to a GitHub repo and open a pull request.

    Args:
        repo_slug: Target repository in OWNER/REPO format.
        github_token: GitHub token for API and git authentication.
        branch_name: Branch name used for the template commit.
        base_ref: Optional PR base branch; defaults to repository default branch.
        overwrite: Whether copied files overwrite existing files in the branch.
        create_if_missing: Whether to create the repository when absent.
        private: Privacy setting when creating a missing repository.
        pr_title: Optional pull request title override.
        pr_body: Optional pull request body override.

    Returns:
        dict[str, str | bool]: Repo and PR metadata for reporting.
    """
    repo_metadata, created_repo = _ensure_repository_exists(
        repo_slug=repo_slug,
        github_token=github_token,
        create_if_missing=create_if_missing,
        private=private,
    )
    owner, repository = _split_repo_slug(repo_slug)
    resolved_base_ref = (
        base_ref.strip()
        or str(repo_metadata.get("default_branch", "")).strip()
        or "main"
    )
    resolved_title = (
        pr_title.strip() or "chore(init): add syncweaver orchestrator templates"
    )
    resolved_body = (
        pr_body.strip()
        or "Bootstrap orchestrator repository with syncweaver starter templates."
    )

    clone_url = str(repo_metadata.get("clone_url", "")).strip()
    if not clone_url:
        clone_url = f"https://github.com/{owner}/{repository}.git"

    git_env = build_github_git_env(github_token)
    redacted_values = [github_token]

    with tempfile.TemporaryDirectory(prefix="syncweaver-init-orch-") as tmp_dir:
        repo_dir = pathlib.Path(tmp_dir) / "repo"
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
                branch_name,
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

        init_orchestrator_in_directory(destination_dir=repo_dir, overwrite=overwrite)

        status_output = run_git(
            ["-C", str(repo_dir), "status", "--porcelain"],
            env=git_env,
            redacted_values=redacted_values,
        )
        if not status_output.strip():
            raise RuntimeError(
                "No file changes detected after copying orchestrator templates"
            )

        run_git(
            ["-C", str(repo_dir), "add", "--all"],
            env=git_env,
            redacted_values=redacted_values,
        )
        run_git(
            [
                "-C",
                str(repo_dir),
                "commit",
                "--message",
                "chore(init): add syncweaver orchestrator templates",
            ],
            env=git_env,
            redacted_values=redacted_values,
        )
        run_git(
            ["-C", str(repo_dir), "push", "origin", f"HEAD:refs/heads/{branch_name}"],
            env=git_env,
            redacted_values=redacted_values,
        )

    headers = _github_headers(github_token)
    pr_response = requests.post(
        f"https://api.github.com/repos/{owner}/{repository}/pulls",
        headers=headers,
        json={
            "title": resolved_title,
            "head": branch_name,
            "base": resolved_base_ref,
            "body": resolved_body,
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
        "repository": f"{owner}/{repository}",
        "base_ref": resolved_base_ref,
        "branch": branch_name,
        "created_repo": created_repo,
        "pr_url": pr_url,
    }
    return result
