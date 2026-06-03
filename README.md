# syncweaver

<!-- README.md is generated from README.qmd. Please edit that file -->

[![build](https://github.com/CCBR/syncweaver/actions/workflows/build-python.yml/badge.svg)](https://github.com/CCBR/syncweaver/actions/workflows/build-python.yml)
[![docs](https://img.shields.io/badge/docs-website-0A7D6C.png)](https://ccbr.github.io/syncweaver)
[![license](https://img.shields.io/badge/license-MIT-1F6FEB.png)](LICENSE.md)

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

For development, follow setup instructions in
[.github/CONTRIBUTING.md](.github/CONTRIBUTING.md).

## Usage

```sh
syncweaver --help
syncweaver --version
```

Print citation metadata:

```sh
syncweaver --citation
```

See the full CLI reference at <https://ccbr.github.io/syncweaver/cli>.

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

## Citation

You can view the updated syncweaver citation with:

```sh
syncweaver --citation
```

Please cite this software if you use it in a publication:

zsh:1: command not found: ccbr_tools

### Bibtex entry

```bibtex
zsh:1: command not found: ccbr_tools
```

Full citation metadata is available in [CITATION.cff](CITATION.cff).
