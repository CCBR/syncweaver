#!/usr/bin/env python3
"""Check that every syncweaver CLI command and subcommand has a docs/cli/ page.

Run from the docs/ directory:

    python check_cli_docs.py

Raises ``RuntimeError`` listing the missing paths if any documentation pages are
absent; exits cleanly when all commands are covered.
"""

import subprocess
from pathlib import Path

DOCS_CLI = Path(__file__).parent / "cli"


def parse_commands(help_text: str) -> list[str]:
    """Extract subcommand names from a Click-style help message.

    Args:
        help_text: Full help text emitted by a Click command.

    Returns:
        list[str]: Subcommand names listed under the ``Commands:`` section.
    """
    lines = help_text.splitlines()
    commands: list[str] = []
    in_commands = False
    for line in lines:
        if line.startswith("Commands:"):
            in_commands = True
        elif in_commands:
            if not line.strip():
                if commands:
                    break
            elif not line.startswith(" "):
                break
            else:
                parts = line.strip().split()
                if parts:
                    commands.append(parts[0])
    return commands


def run_help(*args: str) -> str:
    """Run a syncweaver help invocation and return stdout.

    Args:
        *args: Positional arguments appended after ``syncweaver``.

    Returns:
        str: Standard output of the help command.
    """
    result = subprocess.run(
        ["syncweaver", *args, "--help"],
        capture_output=True,
        text=True,
    )
    cmd = " ".join(["syncweaver", *args, "--help"])
    if result.returncode != 0:
        raise RuntimeError(f"Help command failed: {cmd}\n{result.stderr}")
    if not result.stdout.strip():
        raise RuntimeError(f"Help command produced no output: {cmd}\n{result.stderr}")
    return result.stdout


def check() -> None:
    """Verify that every CLI command has a corresponding docs/cli/ page.

    Raises:
        RuntimeError: If any CLI commands are missing documentation pages.
    """
    missing: list[str] = []

    top_commands = parse_commands(run_help())

    for cmd in top_commands:
        cmd_help = run_help(cmd)
        subcommands = parse_commands(cmd_help)

        if subcommands:
            # Group command: expect docs/cli/{cmd}/index.qmd
            index_path = DOCS_CLI / cmd / "index.qmd"
            if not index_path.exists():
                missing.append(f"cli/{cmd}/index.qmd")
            for subcmd in subcommands:
                subcmd_path = DOCS_CLI / cmd / f"{subcmd}.qmd"
                if not subcmd_path.exists():
                    missing.append(f"cli/{cmd}/{subcmd}.qmd")
        else:
            # Leaf command: expect docs/cli/{cmd}.qmd
            leaf_path = DOCS_CLI / f"{cmd}.qmd"
            if not leaf_path.exists():
                missing.append(f"cli/{cmd}.qmd")

    if missing:
        lines = ["Missing CLI documentation pages:"]
        lines.extend(f"  docs/{path}" for path in missing)
        lines.append(
            "\nCreate a .qmd file for each missing command in docs/cli/. "
            "See an existing file for the expected scaffold."
        )
        raise RuntimeError("\n".join(lines))

    print(f"All {len(top_commands)} CLI commands are documented.")


if __name__ == "__main__":
    check()
