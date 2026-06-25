"""Git command helpers shared across syncweaver modules."""

from __future__ import annotations

import base64
import os
import pathlib
import subprocess


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
