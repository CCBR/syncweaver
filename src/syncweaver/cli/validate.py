"""CLI command for validating syncweaver lockfiles."""

from __future__ import annotations

import json
import pathlib

import click
import jsonschema
from jsonschema import ValidationError


def _load_schema_from_file(schema_path: pathlib.Path) -> dict:
    """Load a JSON schema from disk."""
    schema_text = schema_path.read_text()
    schema_data = json.loads(schema_text)
    return schema_data


def _load_packaged_lockfile_schema() -> dict:
    """Load the bundled syncweaver lockfile JSON schema."""
    from importlib import resources

    schema_data: dict
    schema_text = (
        resources.files("syncweaver.schemas")
        .joinpath("syncweaver-lock.schema.json")
        .read_text()
    )
    schema_data = json.loads(schema_text)
    return schema_data


def _validate_lockfile_against_schema(lock_data: dict, schema_data: dict) -> None:
    """Validate lockfile data and raise a readable schema error when invalid."""
    try:
        jsonschema.validate(instance=lock_data, schema=schema_data)
    except ValidationError as exc:
        location = "/".join(str(item) for item in exc.path)
        if not location:
            location = "<root>"
        raise ValidationError(f"{exc.message} (at {location})") from exc


@click.command("validate")
@click.option(
    "--lockfile",
    default=".syncweaver-lock.json",
    show_default=True,
    type=click.Path(path_type=pathlib.Path),
    help="Path to .syncweaver-lock.json in the host repository.",
)
@click.option(
    "--schema",
    default=None,
    type=click.Path(path_type=pathlib.Path),
    help="Optional path to a JSON schema file. Defaults to bundled schema.",
)
def validate_cmd(lockfile: pathlib.Path, schema: pathlib.Path | None) -> None:
    """Validate a lockfile against the syncweaver lockfile JSON schema."""
    cwd = pathlib.Path.cwd()
    lockfile_path = cwd / lockfile

    try:
        lock_text = lockfile_path.read_text()
        lock_data = json.loads(lock_text)
        if schema is None:
            schema_data = _load_packaged_lockfile_schema()
            schema_label = "packaged schema"
        else:
            schema_path = cwd / schema
            schema_data = _load_schema_from_file(schema_path)
            schema_label = str(schema_path)
        _validate_lockfile_against_schema(lock_data, schema_data)
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValidationError) as exc:
        raise click.ClickException(f"Lockfile does not match schema: {exc}") from exc

    click.echo(f"Lockfile is valid against {schema_label}: {lockfile_path}")
