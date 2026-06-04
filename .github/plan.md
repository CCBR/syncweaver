# syncweaver repository plan

## repository purpose

create a dedicated repository that provides:

- a python cli to orchestrate source-to-host-repository synchronization and patch lifecycle operations
- reusable github actions (composite actions) for host repos and source repos
- workflow templates that downstream repos can copy with minimal changes

tagline:

- synchronize code and weave patches seamlessly

scope alignment from pattern 1:

- implement outbound flow first: analyst edits vendored source code in host repository, patch is generated, and pr is opened upstream
- preserve independent patch decisions (accept or reject per patch) as an optional patch-series extension
- do not use git subtree or git submodule

## core design principles

- file distribution and change tracking remain separate
- host repository gh is the only owner of .syncweaver-lock.json and syncweaver-managed patch files; the lockfile is managed exclusively by the syncweaver cli
- source gh remains host-repository-agnostic (no .syncweaver-lock.json and no patch metadata)
- host repository co is a git mirror that does not write .syncweaver-lock.json
- every automation step is auditable and reproducible

## repo structure

- src/syncweaver/
- actions/
- scripts/
- tests/
- docs/
- .github/workflows/
- pyproject.toml
- VERSION
- CHANGELOG.md
- README.md
- CITATION.cff

## python cli design

framework:

- click

entry command:

- syncweaver

syncweaver commands are intended to be run within host repositories, i.e. repos
that contain a main driver script (`code/main.R`) plus vendored source repositories (`code/Package1/`) that the main script relies on.

### primary syncweaver commands

- syncweaver list --lockfile .syncweaver-lock.json
- syncweaver add --path code/package1 --repo-url ccbr/package1 --ref [tag] --lockfile .syncweaver-lock.json
- syncweaver update --path code/package1 --repo-url ccbr/package1 --ref [tag] --lockfile .syncweaver-lock.json
- syncweaver remove --path code/package1 --lockfile .syncweaver-lock.json
- syncweaver patch create --path code/package1 --repo-url ccbr/package1 --lockfile .syncweaver-lock.json --patch-dir [optional-override]
- syncweaver patch annotate-rejected --patch code/package1/.syncweaver/package1.diff --pr-url [url] --reason [text]
- syncweaver patch list --path code/package1 --lockfile .syncweaver-lock.json
- syncweaver validate --lockfile .syncweaver-lock.json

### secondary syncweaver commands

- syncweaver contribute --upstream-repo ccbr/package1 --lockfile .syncweaver-lock.json --path code/package1 --patch-dir [optional-override] --branch feature/from-host-repo1
- syncweaver deps scan --entrypoints run.R --source-path code/package1 --source-name package1 --lockfile .syncweaver-lock.json --out dependencies.yml
- syncweaver deps validate --file dependencies.yml
- syncweaver deps relevance --dependencies dependencies.yml --changed-files [csv|file]
- syncweaver release changed-files --from-tag [prev] --to-ref [head]
- syncweaver release notify-host-repositories --host-repositories-file host-repositories.yml --source-name package1 --changed-files [csv]

## reusable composite actions (templates)

create one action per directory under actions/.

generate-patches/

- trigger intent: called by host repository workflow on changes under code/package1/\*\*
- inputs:
  - source-name
  - source-repo
  - source-ref-key (default package1)
  - source-path (default code/package1)
  - lockfile (default .syncweaver-lock.json)
  - patch-dir (optional override; default is [source-path]/.syncweaver)
- steps:
  - checkout with full history
  - read baseline sha and branch from .syncweaver-lock.json
  - generate or update one canonical patch file via cli
  - update source-level `patch` field in .syncweaver-lock.json for each changed source entry
  - commit patch artifact if changed

open-upstream-pr/

- inputs:
  - source-repo
  - branch-name
  - patch-dir (optional override; default is [source-path]/.syncweaver)
  - host-repo-name
  - github-token
- steps:
  - clone source repo
  - apply canonical patch file referenced in .syncweaver-lock.json
  - push branch
  - open pr with standard body text

mark-patch-rejected/

- inputs:
  - patch-file
  - pr-url
  - reason
- steps:
  - write rejection status metadata to lockfile extension fields or workflow records
  - commit and push

scan-dependencies/

- inputs:
  - source-name
  - entrypoints
  - source-path
  - lockfile
  - output-file
- steps:
  - setup r + scanner deps or run scanner container
  - generate dependencies.yml
  - commit and push if changed

## github actions workflow templates in src/syncweaver/templates

- generate-patches.yml

  - on push to main paths [source-path]/\*\*
  - call generate-patches action

- contribute-upstream.yml

  - on workflow dispatch
  - call generate-patches action then open-upstream-pr action

- scan-dependencies.yml

  - on push to entrypoint files (main.R)
  - calls scan-dependencies action

- mark-rejected.yml
  - workflow_dispatch inputs: patch_file, pr_url, reason
  - called when a PR created by contribute-upstream or open-upstream-pr gets rejected
  - calls mark-patch-rejected

## data and metadata contracts

### .syncweaver-lock.json

- file is only edited by the syncweaver cli; it is not intended to be edited manually
- format modeled after nf-core modules.json top-level patterns:
  - name
  - homePage
  - repos
- recommended source entry shape:
  - repos[[repo_url]].sources[[source_path]].branch
  - repos[[repo_url]].sources[[source_path]].git_sha
  - repos[[repo_url]].sources[[source_path]].installed_by (list)
  - repos[[repo_url]].sources[[source_path]].patch (optional, relative path to a single patch file)
  - repos[[repo_url]].sources[[source_path]].patches (optional extension for future patch-series support)
- single source for baseline pull sha and branch per tracked source path
- example:

```json
{
  "name": "org1/host repository1",
  "homePage": "https://github.com/org1/host repository1",
  "sources": {
    "code/package1": {
      "repo_url": "https://github.com/org2/package1",
      "ref": "main",
      "git_sha": "3a1f2d49a7a0e8e3db7a9d3b2ea73ff77d1f9b10",
      "patch": "code/package1/.syncweaver/package1.diff"
    }
  }
}
```

### dependencies.yml

- required fields per source:
  - direct_functions
  - transitive_functions
  - files
- files is authoritative for release relevance

### patch files

[source-path]/.syncweaver/[source-name].diff

- default format follows nf-core modules patch behavior: one patch file per tracked source path
- patch filename should be deterministic from source identifier (nf-core-style `component.replace('/', '-') + ".diff"`)
- patch content must be standard unified diff with `---`, `+++`, and `@@` hunks
- one patch file may contain changes for multiple files under the same source path
- patch references are stored in `.syncweaver-lock.json` under source-level `patch`
- reverse-apply checks should be used to validate that patch content is consistent with vendored files
- patch-body metadata headers are not part of the canonical format; status or audit metadata should be stored in lockfile extension fields or workflow records
- optional future extension: support `patches` as an ordered patch series only when independent accept/reject decisions are required

## testing strategy

unit tests (pytest):

- .syncweaver-lock.json parse, validate, read, and write
- patch generation and deterministic ordering
- patch validation (structure checks for `---`, `+++`, `@@`)
- reverse-apply validation against vendored source files
- rejection/audit metadata annotation in lockfile extension fields or workflow records
- dependency relevance matching
- changed-files parsing between tags and commits

integration tests:

- local temp git repos emulating source gh and host repository gh
- end-to-end pattern 1 simulation:
  - modify vendored file
  - generate patch
  - apply patch in source clone
  - verify resulting diff and pr payload content

workflow tests:

- actionlint
- shellcheck for shell steps
- smoke tests for composite actions via act (optional) or mocked runner scripts

## ci and release baseline

borrow from ccbr/actions conventions:

- ruff + pytest + coverage in build workflow
- pre-commit with ruff-format, conventional commit check, and codespell
- VERSION-driven semantic versioning
- draft release and post-release workflows
- codecov upload
- documentation with quarto

## security and compliance

- never store credentials in the repo
- require CCBR_BOT_TOKEN from org secrets for cross-repo operations
- log actor, repo, action, timestamp, and model or provider metadata where ai-assisted automation is involved
- keep phi and nih-sensitive data out of pr payloads and logs

## mvp phasing

phase 0: bootstrap

- scaffold repo, packaging, ci, lint, tests, docs, and release files

phase 1: pattern 1 core

- implement top-level syncweaver commands and contribute workflows (including patch and contribute upstream flows)
- ship actions:
  - host-repo-generate-patches
  - host-repo-open-upstream-pr
  - host-repo-mark-patch-rejected
- ship workflow templates for host repos

phase 2: dependency-aware release dispatch

- implement deps relevance checks and source notify action
- ship source release workflow template

phase 3: hardening

- rich validation and doctor checks
- better conflict handling and deterministic patch ordering
- expanded integration tests and failure-path tests

## open decisions

- decide whether deps scan remains an r-based script in host repos or is wrapped by python cli with an r subprocess
- decide registry source for dependent host repositories: host-repositories.yml in source repo vs centralized registry repo

## definition of done for initial release

- a host repo can install and run template workflows with only repository-specific input edits
- editing code/package1/\*\* in host repository generates patch files and opens an upstream pr automatically
- rejection workflow records status metadata without altering baseline git_sha in .syncweaver-lock.json
- source release workflow dispatches only to host repositories whose dependencies.yml files overlap changed files
- all tests pass in ci and release automation can draft a versioned release
