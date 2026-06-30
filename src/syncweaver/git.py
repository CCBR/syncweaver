"""Git command helpers shared across syncweaver modules."""

from __future__ import annotations

import base64
import os
import pathlib
import re
import subprocess


_FULL_GIT_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")


def _redact_text(text: str, redacted_values: list[str] | None) -> str:
    """Replace sensitive substrings in text before surfacing an error."""
    redacted_text = text
    if redacted_values is not None:
        for value in redacted_values:
            if value:
                redacted_text = redacted_text.replace(value, "[REDACTED]")
    return redacted_text


def resolve_github_token(token: str) -> str:
    """Resolve a GitHub token from explicit input, env var, or the gh CLI."""
    resolved_token = token.strip()

    if not resolved_token:
        resolved_token = os.environ.get("GITHUB_TOKEN", "").strip()

    if not resolved_token:
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                resolved_token = result.stdout.strip()
        except FileNotFoundError:
            resolved_token = ""

    if not resolved_token:
        raise RuntimeError(
            "No GitHub token found. Provide --token, set GITHUB_TOKEN, "
            "or run `gh auth login`."
        )

    return resolved_token


def build_github_git_env(github_token: str) -> dict[str, str]:
    """Build process-local GitHub auth headers for git-over-HTTPS commands."""
    auth_bytes = f"x-access-token:{github_token}".encode("utf-8")
    encoded_auth = base64.b64encode(auth_bytes).decode("ascii")
    env = os.environ.copy()
    config_count_text = env.get("GIT_CONFIG_COUNT", "0").strip()
    config_count = 0
    if config_count_text:
        try:
            config_count = int(config_count_text)
        except ValueError:
            config_count = 0

    env["GIT_CONFIG_COUNT"] = str(config_count + 1)
    env[f"GIT_CONFIG_KEY_{config_count}"] = "http.https://github.com/.extraheader"
    env[f"GIT_CONFIG_VALUE_{config_count}"] = f"AUTHORIZATION: basic {encoded_auth}"
    return env


def run_git(
    args: list[str],
    cwd: pathlib.Path | None = None,
    env: dict[str, str] | None = None,
    redacted_values: list[str] | None = None,
) -> str:
    """Run a git command and return stdout, raising RuntimeError on failure."""
    command = ["git", *args]
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        stderr = _redact_text(result.stderr.strip(), redacted_values)
        cmd = _redact_text(" ".join(command), redacted_values)
        raise RuntimeError(f"Git command failed: {cmd}\n{stderr}")
    return result.stdout.strip()


def is_full_git_sha(value: str) -> bool:
    """Check whether input is a full 40-character git commit SHA."""
    value_input = value.strip()
    matches_full_sha = bool(_FULL_GIT_SHA_PATTERN.match(value_input))
    return matches_full_sha


def resolve_remote_ref_to_git_sha(repository: str, source_ref: str) -> str:
    """Resolve a remote source ref to a full commit SHA via git ls-remote.

    Args:
        repository (str): Source repository URL.
        source_ref (str): Source ref input (tag/branch/ref/commit SHA).

    Returns:
        str: Resolved full 40-character commit SHA.

    Raises:
        ValueError: If inputs are empty or ref cannot be resolved to a commit SHA.
        RuntimeError: If git ls-remote fails.
    """
    repository_input = repository.strip()
    source_ref_input = source_ref.strip()
    resolved_git_sha = ""

    if (not repository_input) or (not source_ref_input):
        raise ValueError("repository and source_ref are required for SHA resolution")

    if is_full_git_sha(source_ref_input):
        resolved_git_sha = source_ref_input.lower()
    else:
        command = ["git", "ls-remote", repository_input, source_ref_input]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode == 0:
            for output_line in completed.stdout.splitlines():
                line = output_line.strip()
                if line:
                    pieces = line.split()
                    candidate_sha = pieces[0].strip().lower()
                    if is_full_git_sha(candidate_sha):
                        resolved_git_sha = candidate_sha
        else:
            raise RuntimeError(
                "git ls-remote failed while resolving source_ref to commit SHA"
            )

        if not resolved_git_sha:
            raise ValueError(
                f"unable to resolve source_ref to a commit SHA: {source_ref_input}"
            )

    return resolved_git_sha
