"""Utility helpers for the syncweaver package."""

import pathlib

from cffconvert.cli.create_citation import create_citation
from cffconvert.cli.validate_or_write_output import validate_or_write_output


def repo_base(*paths: str) -> pathlib.Path:
    """Return an absolute path rooted at the syncweaver package directory.

    Args:
        *paths (str): Additional path segments to join.

    Returns:
        pathlib.Path: Resolved path.

    Examples:
        >>> repo_base("CITATION.cff")
    """
    basedir = pathlib.Path(__file__).absolute().parent
    return basedir.joinpath(*paths)


def get_version() -> str:
    """Return the installed package version.

    Reads from the ``VERSION`` file bundled with the package, falling back to
    ``importlib.metadata`` if unavailable.

    Returns:
        str: Version string.

    Examples:
        >>> get_version()
    """
    version = ""
    version_file = repo_base("VERSION")
    if version_file.is_file():
        version = version_file.read_text().strip()
    else:
        import importlib.metadata

        version = importlib.metadata.version("syncweaver")
    return version


def print_citation(context, param, value) -> None:
    """Print the project citation and exit when the citation flag is enabled.

    Args:
        context: Click context.
        param: Click option parameter (unused callback argument).
        value: Citation flag value.

    Returns:
        None: Always returns ``None``.

    Examples:
        >>> # Used as a Click callback and not called directly.
    """
    del param
    if value and not context.resilient_parsing:
        citation_file = repo_base("CITATION.cff")
        citation = create_citation(str(citation_file), None)
        validate_or_write_output(None, "bibtex", False, citation)
        context.exit()
    return None
