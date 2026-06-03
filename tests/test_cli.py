"""Basic tests for the syncweaver CLI."""

from click.testing import CliRunner

from syncweaver.cli import cli
from syncweaver.templates import list_templates


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "syncweaver" in result.output


def test_templates_list():
    runner = CliRunner()
    result = runner.invoke(cli, ["templates", "list"])
    assert result.exit_code == 0
    assert ".yml" in result.output


def test_templates_add(tmp_path):
    template_name = list_templates()[0].removesuffix(".yml")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["templates", "add", template_name, "--output", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert (tmp_path / f"{template_name}.yml").exists()


def test_templates_add_no_overwrite(tmp_path):
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
