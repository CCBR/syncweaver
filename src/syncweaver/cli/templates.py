"""CLI commands for managing workflow templates."""

import pathlib

import click

from syncweaver.templates import list_templates, use_template


@click.group("templates")
def templates_group():
    """List and add workflow templates to a repo."""


@templates_group.command("list")
def list_cmd():
    """List available workflow templates."""
    for name in list_templates():
        click.echo(name)


@templates_group.command("add")
@click.argument("template_name")
@click.option(
    "--output",
    "-o",
    default=".github/workflows",
    show_default=True,
    help="Directory to write the template file.",
    type=click.Path(),
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite an existing file.",
)
def add_cmd(template_name: str, output: str, overwrite: bool):
    """Copy TEMPLATE_NAME into the output directory.

    TEMPLATE_NAME may omit the .yml extension.
    """
    try:
        dest = use_template(
            template_name, output_dir=pathlib.Path(output), overwrite=overwrite
        )
        click.echo(f"Wrote {dest}")
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    except FileExistsError as exc:
        raise click.ClickException(str(exc)) from exc
