# Contributing to syncweaver

## Proposing changes with issues

If you want to make a change, it's a good idea to first
[open an issue](https://github.com/CCBR/syncweaver/issues)
and make sure someone from the team agrees that it's needed.

If you've decided to work on an issue,
[assign yourself to the issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/assigning-issues-and-pull-requests-to-other-github-users#assigning-an-individual-issue-or-pull-request)
so others will know you're working on it.

## Pull request process

We use [GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow)
as our collaboration process.

### Commit messages

Commit messages must follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).
The `conventional-pre-commit` hook enforces this on commit.

### Setup

```sh
git clone https://github.com/CCBR/syncweaver
cd syncweaver
pip install -e ".[dev,test,docs]"
pre-commit install
```

### Running tests

```sh
pytest
```

### Code style

Python code is formatted with `ruff`. Run `ruff format src/ tests/` before committing,
or let the pre-commit hook handle it.
