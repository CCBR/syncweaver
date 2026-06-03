"""Top-level Click CLI for syncweaver."""

import click

from syncweaver.cli.add import add_cmd
from syncweaver.cli.patch import patch_group
from syncweaver.cli.templates import templates_group
from syncweaver.util import get_version, print_citation


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.version_option(get_version(), "-v", "--version", is_flag=True)
@click.option(
    "--citation",
    "-c",
    is_flag=True,
    callback=print_citation,
    expose_value=False,
    is_eager=True,
    help="Print the citation in BibTeX format and exit.",
)
def cli():
    """syncweaver: synchronize code and weave patches seamlessly."""


cli.add_command(templates_group)
cli.add_command(add_cmd)
cli.add_command(patch_group)
