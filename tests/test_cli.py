"""Basic tests for the syncweaver CLI."""

from click.testing import CliRunner

from syncweaver.cli import cli


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
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["templates", "add", "capsule-pattern1-outbound", "--output", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert (tmp_path / "capsule-pattern1-outbound.yml").exists()


def test_templates_add_no_overwrite(tmp_path):
    runner = CliRunner()
    runner.invoke(
        cli,
        ["templates", "add", "capsule-pattern1-outbound", "--output", str(tmp_path)],
    )
    result = runner.invoke(
        cli,
        ["templates", "add", "capsule-pattern1-outbound", "--output", str(tmp_path)],
    )
    assert result.exit_code != 0
