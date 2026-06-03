"""Basic tests for the syncweaver CLI."""

from click.testing import CliRunner

from syncweaver.cli import cli
from syncweaver.templates import list_templates


def test_cli_help():
    """Validate top-level CLI help output.

    Returns:
        None: Assertions validate command behavior.
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "syncweaver" in result.output


def test_templates_list():
    """Verify template listing command prints YAML template names.

    Returns:
        None: Assertions validate command behavior.
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["templates", "list"])
    assert result.exit_code == 0
    assert ".yml" in result.output


def test_templates_add(tmp_path):
    """Verify templates add writes the selected template file.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    template_name = list_templates()[0].removesuffix(".yml")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["templates", "add", template_name, "--output", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert (tmp_path / f"{template_name}.yml").exists()


def test_templates_add_no_overwrite(tmp_path):
    """Verify templates add fails when destination exists without overwrite.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    template_name = list_templates()[0].removesuffix(".yml")
    runner = CliRunner()
    runner.invoke(
        cli,
        ["templates", "add", template_name, "--output", str(tmp_path)],
    )
    result = runner.invoke(
        cli,
        ["templates", "add", template_name, "--output", str(tmp_path)],
    )
    assert result.exit_code != 0
