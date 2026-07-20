# syncweaver

<!-- README.md is generated from README.qmd. Please edit that file -->

[![build](https://github.com/CCBR/syncweaver/actions/workflows/build-python.yml/badge.svg)](https://github.com/CCBR/syncweaver/actions/workflows/build-python.yml)
[![docs](https://github.com/CCBR/syncweaver/actions/workflows/docs-quartodoc.yml/badge.svg)](https://ccbr.github.io/syncweaver)
[![codecov](https://codecov.io/gh/CCBR/syncweaver/graph/badge.svg?token=V4BSDLIEyi)](https://codecov.io/gh/CCBR/syncweaver)
[![docker](https://img.shields.io/docker/v/nciccbr/syncweaver?logo=docker&label=docker&color=blue.png)](https://hub.docker.com/r/nciccbr/syncweaver)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21460219.svg)](https://doi.org/10.5281/zenodo.21460219)

> synchronize code and weave patches seamlessly

syncweaver synchronizes code between package repositories and host
repositories, and manages the full lifecycle of patch artifacts from
generation through upstream pull request submission, rejection status
tracking, and dependency-aware release dispatch.

View the documentation website at <https://ccbr.github.io/syncweaver>.

## Installation

# Installation

## Quick Start

Install syncweaver with pip:

```sh
pip install git+https://github.com/CCBR/syncweaver.git
```

## System Dependencies

syncweaver has minimal required system dependencies, but some features
require additional tools:

### Required

- Python \>= 3.11
- Git – Used for all source synchronization and patching operations

### Optional

- Docker – Required for dependency analysis with functracer
  - Used by: `syncweaver deps analyze`,
    `syncweaver deps select-update-paths` (when dependency gating is
    enabled)
  - Without Docker: Core sync operations work fine, but dependency
    impact analysis will fail

## Feature Requirements

| Feature                                            | Required System Dependencies                              |
| -------------------------------------------------- | --------------------------------------------------------- |
| Source synchronization (`add`, `remove`, `update`) | Git                                                       |
| Patch contribution (`contribute-patch`)            | Git                                                       |
| Dependency analysis (`deps analyze`)               | Git, Docker                                               |
| Dependency gating in updates                       | Git, Docker                                               |
| GitHub integration                                 | Git, optional: GitHub CLI (`gh`) for token auto-detection |

## GitHub CLI (Optional)

The GitHub CLI (`gh`) is optional and used only for automatic token
resolution. If not available, provide GitHub tokens explicitly via: -
`--token` flag - `GITHUB_TOKEN` environment variable

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
      add         Add an external repository to the current host repository.
      contribute  Contribute a tracked host patch back to the source repository.
      deps        Analyze source dependencies for host repository integration.
      init        Initialize syncweaver starter content in local or remote...
      patch       Create, mark, and list source patch artifacts.
      remove      Remove a tracked external repository from the current host...
      templates   List and add workflow templates to a repo.
      update      Update a tracked external repository in the current host...
      validate    Validate a lockfile against the syncweaver lockfile JSON...

```sh
syncweaver --version
```

    syncweaver, version 0.1.0-dev

## Actions

Custom github actions used in our github workflows.

- [setup-syncweaver](actions/setup-syncweaver) - Configure syncweaver
  for subsequent workflow steps using Docker image tags when available,
  otherwise install from git ref.
- [update-host-source-direct](actions/update-host-source-direct) - Check
  out a host repository directly, update matching tracked sources, and
  open a PR
- [update-source](actions/update-source) - Run syncweaver update for a
  tracked source path

## Help and Contributing

Come across a bug? Open an
[issue](https://github.com/CCBR/syncweaver/issues) and include a minimal
reproducible example.

Have a question or idea? Start a
[discussion](https://github.com/CCBR/syncweaver/discussions).

Want to contribute? Read the [contributing
guide](.github/CONTRIBUTING.md).
