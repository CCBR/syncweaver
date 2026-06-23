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
    assert "update" in result.output
    assert "remove" in result.output
    assert "contribute" in result.output


def test_update_help_includes_remote_subdir_option():
    """Verify `update --help` documents the remote subdirectory option.

    Returns:
        None: Assertions validate command behavior.
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["update", "--help"])
    assert result.exit_code == 0
    assert "--remote-subdir" in result.output


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


def test_contribute_help():
    """Verify contribute subcommand exposes expected options.

    Returns:
        None: Assertions validate command behavior.
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["contribute", "--help"])
    assert result.exit_code == 0
    assert "--path" in result.output
    assert "--repo-url" in result.output
    assert "--base-ref" in result.output
    assert "--lockfile" in result.output
    assert "--token" in result.output
    assert "--debug" in result.output


def test_contribute_opens_pr(tmp_path, monkeypatch):
    """Verify contribute resolves metadata and calls contribute_patch.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    import json
    import syncweaver.cli.contribute as contrib_module
    import syncweaver.contribute_patch as contribute_patch_module

    lock_data = {
        "name": "CCBR/host-repo",
        "homePage": "https://github.com/CCBR/host-repo",
        "sources": {
            "code/pkg": {
                "repo_url": "https://github.com/CCBR/package1",
                "ref": "main",
                "git_sha": "3a1f2d49a7a0e8e3db7a9d3b2ea73ff77d1f9b10",
                "patch": "code/pkg/.syncweaver/code-pkg.diff",
            }
        },
    }
    lockfile = tmp_path / ".syncweaver-lock.json"
    lockfile.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    patch_file = tmp_path / "code/pkg/.syncweaver/code-pkg.diff"
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    patch_file.write_text(
        "--- a/pkg.py\n+++ b/pkg.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
    )

    monkeypatch.chdir(tmp_path)

    captured = {}

    def _fake_contribute_patch(
        resolved, host_cwd, github_token, *, run_id="", debug=False
    ):
        captured["resolved"] = resolved
        captured["token"] = github_token
        return "https://github.com/CCBR/package1/pull/42"

    monkeypatch.setattr(
        contribute_patch_module, "contribute_patch", _fake_contribute_patch
    )
    monkeypatch.setattr(contrib_module, "contribute_patch", _fake_contribute_patch)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["contribute", "--path", "code/pkg", "--token", "ghp_testtoken"],
    )
    assert result.exit_code == 0, result.output
    assert "https://github.com/CCBR/package1/pull/42" in result.output
    assert captured["resolved"]["source_path"] == "code/pkg"
    assert captured["token"] == "ghp_testtoken"


def test_contribute_debug_prints_metadata(tmp_path, monkeypatch):
    """Verify --debug flag prints resolved metadata before opening PR.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    import json
    import syncweaver.cli.contribute as contrib_module

    lock_data = {
        "name": "CCBR/host-repo",
        "homePage": "https://github.com/CCBR/host-repo",
        "sources": {
            "code/pkg": {
                "repo_url": "https://github.com/CCBR/package1",
                "ref": "main",
                "git_sha": "3a1f2d49a7a0e8e3db7a9d3b2ea73ff77d1f9b10",
                "patch": "code/pkg/.syncweaver/code-pkg.diff",
            }
        },
    }
    lockfile = tmp_path / ".syncweaver-lock.json"
    lockfile.write_text(f"{json.dumps(lock_data, indent=2)}\n")

    patch_file = tmp_path / "code/pkg/.syncweaver/code-pkg.diff"
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    patch_file.write_text(
        "--- a/pkg.py\n+++ b/pkg.py\n@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n"
    )

    monkeypatch.chdir(tmp_path)
    import syncweaver.contribute_patch as contribute_patch_module

    monkeypatch.setattr(
        contribute_patch_module,
        "contribute_patch",
        lambda *a, **kw: "https://github.com/CCBR/package1/pull/1",
    )
    monkeypatch.setattr(
        contrib_module,
        "contribute_patch",
        lambda *a, **kw: "https://github.com/CCBR/package1/pull/1",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["contribute", "--path", "code/pkg", "--token", "ghp_testtoken", "--debug"],
    )
    assert result.exit_code == 0, result.output
    assert "source_path" in result.output
    assert "CCBR/package1" in result.output


def test_contribute_fails_when_lockfile_missing(tmp_path, monkeypatch):
    """Verify contribute raises ClickException when lockfile does not exist.

    Args:
        tmp_path: Temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["contribute", "--token", "ghp_testtoken"])
    assert result.exit_code != 0
