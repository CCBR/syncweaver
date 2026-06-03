# syncweaver

<!-- README.md is generated from README.qmd. Please edit that file -->

[![build](https://github.com/CCBR/syncweaver/actions/workflows/build-python.yml/badge.svg)](https://github.com/CCBR/syncweaver/actions/workflows/build-python.yml)
[![docs](https://github.com/CCBR/syncweaver/actions/workflows/docs-quartodoc.yml/badge.svg)](https://ccbr.github.io/syncweaver)
[![codecov](https://codecov.io/gh/CCBR/syncweaver/graph/badge.svg?token=V4BSDLIEyi)](https://codecov.io/gh/CCBR/syncweaver)

> synchronize code and weave patches seamlessly

syncweaver synchronizes code between package repositories and host
repositories, and manages the full lifecycle of patch artifacts from
generation through upstream pull request submission, rejection status
tracking, and dependency-aware release dispatch.

View the documentation website at <https://ccbr.github.io/syncweaver>.

## Installation

Install syncweaver with pip:

```sh
pip install git+https://github.com/CCBR/syncweaver.git
```

## Usage

```sh
syncweaver --help
```

    Usage: syncweaver [OPTIONS] COMMAND [ARGS]...

      syncweaver: synchronize code and weave patches seamlessly.

    Options:
      -v, --version   Show the version and exit.
      -c, --citation  Print the citation in BibTeX format and exit.
      -h, --help      Show this message and exit.

    Commands:
      add        Add an external repository to the current host repository.
      patch      Create, annotate, and list source patch artifacts.
      templates  List and add workflow templates to a repo.

```sh
syncweaver --version
```

    syncweaver, version 0.0.1-dev

## Actions

Custom github actions used in our github workflows.

## Help and Contributing

Come across a bug? Open an
[issue](https://github.com/CCBR/syncweaver/issues) and include a minimal
reproducible example.

Have a question or idea? Start a
[discussion](https://github.com/CCBR/syncweaver/discussions).

Want to contribute? Read the [contributing
guide](.github/CONTRIBUTING.md).
