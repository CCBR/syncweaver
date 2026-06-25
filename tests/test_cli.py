"""Basic tests for the syncweaver CLI."""

import json
import pathlib

from click.testing import CliRunner

import syncweaver.cli.deps as deps_cli
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
    assert "deps" in result.output


def test_deps_analyze_outputs_json(tmp_path):
    """Verify deps analyze command emits JSON analysis output.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    host_repo_path = tmp_path / "host-repo"
    host_repo_path.mkdir()
    source_root = host_repo_path / "code" / "package1"
    source_root.mkdir(parents=True)
    (source_root / "DESCRIPTION").write_text("Package: package1\n", encoding="utf-8")
    (source_root / "R").mkdir()

    def _stub_analyze_source_dependencies(
        host_repo_path: pathlib.Path,
        source_path: str,
        source_type_input: str,
        entry_scripts,
        repository: str,
        release_tag: str,
        previous_tag: str,
        package_name: str,
    ):
        output = {
            "analysis_engine": "functracer",
            "entry_scripts": ["main.R"],
            "impacted_scripts": ["main.R"],
            "language": "r",
            "release_impact_available": True,
            "source_path": source_path,
            "source_type": "r_package",
            "unaffected_scripts": [],
        }
        return output

    original = deps_cli.analyze_source_dependencies
    deps_cli.analyze_source_dependencies = _stub_analyze_source_dependencies
    try:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "deps",
                "analyze",
                "--host-repo",
                str(host_repo_path),
                "--source-path",
                "code/package1",
            ],
        )
    finally:
        deps_cli.analyze_source_dependencies = original
    assert result.exit_code == 0
    assert '"analysis_engine": "functracer"' in result.output


def test_deps_select_update_paths_outputs_json(tmp_path):
    """Verify deps select-update-paths emits selected and skipped path payload.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    host_repo_path = tmp_path / "host-repo"
    host_repo_path.mkdir()
    lockfile_path = host_repo_path / ".syncweaver-lock.json"
    lockfile_path.write_text("{}\n", encoding="utf-8")

    def _stub_select_source_paths_for_update(
        source_paths,
        lockfile_path,
        source_ref_input,
        host_repo_path,
        functracer_entry_scripts_input,
        functracer_source_paths_input,
    ):
        return ["code/package1"], ["code/package2"]

    original = deps_cli.select_source_paths_for_update
    deps_cli.select_source_paths_for_update = _stub_select_source_paths_for_update
    try:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "deps",
                "select-update-paths",
                "--host-repo",
                str(host_repo_path),
                "--lockfile",
                ".syncweaver-lock.json",
                "--source-paths-json",
                '["code/package1", "code/package2"]',
                "--source-ref",
                "v1.2.3",
            ],
        )
    finally:
        deps_cli.select_source_paths_for_update = original
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["source_paths"] == ["code/package1"]
    assert payload["source_count"] == 1
    assert payload["skipped_source_paths"] == ["code/package2"]
    assert payload["skipped_source_count"] == 1


def test_deps_select_update_paths_writes_github_output(tmp_path):
    """Verify deps select-update-paths appends expected GitHub output fields.

    Args:
        tmp_path: Temporary directory fixture.

    Returns:
        None: Assertions validate command behavior.
    """
    host_repo_path = tmp_path / "host-repo"
    host_repo_path.mkdir()
    lockfile_path = host_repo_path / ".syncweaver-lock.json"
    lockfile_path.write_text("{}\n", encoding="utf-8")
    github_output_path = tmp_path / "github-output.txt"

    def _stub_select_source_paths_for_update(
        source_paths,
        lockfile_path,
        source_ref_input,
        host_repo_path,
        functracer_entry_scripts_input,
        functracer_source_paths_input,
    ):
        return ["code/package1"], []

    original = deps_cli.select_source_paths_for_update
    deps_cli.select_source_paths_for_update = _stub_select_source_paths_for_update
    try:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "deps",
                "select-update-paths",
                "--host-repo",
                str(host_repo_path),
                "--lockfile",
                ".syncweaver-lock.json",
                "--source-paths-json",
                '["code/package1"]',
                "--source-ref",
                "v1.2.3",
                "--github-output",
                str(github_output_path),
            ],
        )
    finally:
        deps_cli.select_source_paths_for_update = original
    assert result.exit_code == 0
    output_text = github_output_path.read_text(encoding="utf-8")
    assert 'source_paths=["code/package1"]' in output_text
    assert "source_count=1" in output_text
    assert "skipped_source_paths=[]" in output_text
    assert "skipped_source_count=0" in output_text


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
