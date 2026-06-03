"""Entry point wrapper for the syncweaver CLI."""

from syncweaver.cli.main import cli


def main() -> None:
    """Run the syncweaver command-line interface."""
    cli()


if __name__ == "__main__":
    main()
