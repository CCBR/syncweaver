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
- preserve independent patch decisions (accept or reject per patch)
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
- syncweaver patch annotate-rejected --patch code/package1/.syncweaver/syncweaver.0002-normalization.patch --pr-url [url] --reason [text]
- syncweaver patch list --path code/package1 --lockfile .syncweaver-lock.json

### secondary syncweaver commands

- syncweaver contribute --upstream-repo ccbr/package1 --lockfile .syncweaver-lock.json --path code/package1 --patch-dir [optional-override] --branch feature/from-host-repo1
- syncweaver deps scan --entrypoints run.R --source-path code/package1 --source-name package1 --lockfile .syncweaver-lock.json --out dependencies.yml
- syncweaver deps validate --file dependencies.yml
- syncweaver deps relevance --dependencies dependencies.yml --changed-files [csv|file]
- syncweaver release changed-files --from-tag [prev] --to-ref [head]
- syncweaver release notify-host-repositories --host-repositories-file host-repositories.yml --source-name package1 --changed-files [csv]

## reusable composite actions (templates)

create one action per directory under actions/.

host-repo-generate-patches/

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
  - generate or update patch files via cli
  - update patch path field in .syncweaver-lock.json for each changed source entry
  - commit patch artifacts if changed

host-repo-open-upstream-pr/

- inputs:
  - source-repo
  - branch-name
  - patch-dir (optional override; default is [source-path]/.syncweaver)
  - host-repo-name
  - github-token
- steps:
  - clone source repo
  - apply patches in deterministic order (numeric prefix)
  - push branch
  - open pr with standard body text

host-repo-mark-patch-rejected/

- inputs:
  - patch-file
  - pr-url
  - reason
- steps:
  - prepend rejection metadata header
  - commit and push

host-repo-regenerate-dependencies/

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

source-notify-relevant-host repositories/

- inputs:
  - source-name
  - host-repositories-file
  - changed-files
  - github-token
- steps:
  - for each host repository, fetch dependencies.yml
  - dispatch only if overlap with files list

## workflow templates under examples/

host-repo-pattern1-outbound.yml

- on push to main paths [source-path]/\*\*
- calls host-repo-generate-patches then host-repo-open-upstream-pr

host-repo-dependencies-refresh.yml

- on push to entrypoint files (run.R, scripts/\*\*)
- calls host-repo-regenerate-dependencies

host-repo-mark-rejected.yml

- workflow_dispatch inputs: patch_file, pr_url, reason
- calls host-repo-mark-patch-rejected

source-release-notify.yml

- on release published
- computes changed files for release
- calls source-notify-relevant-host repositories

## data and metadata contracts

.syncweaver-lock.json

- file is only edited by the syncweaver cli; it is not intended to be edited manually
- format modeled after nf-core modules.json top-level patterns:
  - name
  - homePage
  - repos
- recommended source entry shape:
  - repos[[repo_url]].sources[[source_path]].branch
  - repos[[repo_url]].sources[[source_path]].git_sha
  - repos[[repo_url]].sources[[source_path]].installed_by (list)
  - repos[[repo_url]].sources[[source_path]].patches (optional, ordered list of relative paths)
  - repos[[repo_url]].sources[[source_path]].patch (optional, single-file compatibility key)
- single source for baseline pull sha and branch per tracked source path
- example:

```json
{
  "name": "ccbr/host repository1",
  "homePage": "https://github.com/ccbr/host repository1",
  "repos": {
    "https://github.com/ccbr/package1": {
      "sources": {
        "code/package1": {
          "branch": "main",
          "git_sha": "3a1f2d49a7a0e8e3db7a9d3b2ea73ff77d1f9b10",
          "installed_by": ["syncweaver"],
          "patches": [
            "code/package1/.syncweaver/syncweaver.0001-qc-thresholds.patch",
            "code/package1/.syncweaver/syncweaver.0002-normalization.patch"
          ]
        }
      }
    }
  }
}
```

dependencies.yml

- required fields per source:
  - direct_functions
  - transitive_functions
  - files
- files is authoritative for release relevance

[source-path]/.syncweaver/syncweaver.[nnnn]-[slug].patch

- unified diff format
- each patch file may include hunks for multiple files; split into multiple patch files when independent acceptance decisions are desired
- patch files are applied in lexical order using zero-padded numeric prefixes (0001, 0002, ...)
- paths are referenced from .syncweaver-lock.json via source-level patches list (nf-core-style linkage, extended to patch series)
- for backward compatibility, a single patch may be tracked in patch when only one patch file exists
- optional metadata headers (kept in patch body preamble or tracked in lockfile json extension fields):
  - status: rejected-upstream
  - rejected-date
  - reason
  - upstream-pr

## testing strategy

unit tests (pytest):

- .syncweaver-lock.json parse, validate, read, and write
- patch generation and deterministic ordering
- patch series generation for multi-file changes
- patch metadata annotation
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
- rejection workflow marks patch metadata without altering baseline git_sha in .syncweaver-lock.json
- source release workflow dispatches only to host repositories whose dependencies.yml files overlap changed files
- all tests pass in ci and release automation can draft a versioned release
