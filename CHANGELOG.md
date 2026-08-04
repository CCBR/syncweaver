## syncweaver development version

## syncweaver 0.1.1

- Improve error message reported by `syncweaver update` when the lockfile is invalid. (#42, @kelly-sovacool, @copilot)
- Fix action `setup-syncweaver` Docker wrapper dropping stdin (missing `docker run -i`), which silently executed empty heredoc scripts passed to `syncweaver-python` and produced empty step outputs. (#36, @kelly-sovacool)
- Fix `syncweaver update` crashing with `fatal: bad object` when a tracked source's previously recorded commit is no longer reachable in the source repository (e.g. after an upstream branch rebase, force-push, or delete). The diff is now skipped in that case and the update proceeds as a full refresh instead of failing. (#38, @kelly-sovacool)
- Fix `syncweaver update` branch name clashing. (#40, @kelly-sovacool)

## syncweaver 0.1.0

This is the first release of syncweaver! 🎉
View the website for detailed documentation:
<https://ccbr.github.io/syncweaver>

Main commands:

- `syncweaver init host` -- initialize a host repository with boilerplate and orchestrator configuration.
- `syncweaver add` -- vendor an external repository (or subdirectory) into a host and record it in `.syncweaver-lock.json`
- `syncweaver update` -- update a vendored source to a new ref, reapplying any tracked patches
- `syncweaver remove` -- remove a tracked source from the host
- `syncweaver patch` -- create, list, and track patch artifacts for host-side modifications to vendored code
- `syncweaver contribute` -- open a pull request on the source repository to contribute a host patch upstream
- `syncweaver deps` -- analyze source dependencies for host integration
- `syncweaver templates` -- list and add GitHub Actions workflow templates to a repository
- `syncweaver validate` -- validate a lockfile against the syncweaver JSON schema

GitHub Actions are included for automated host updates, with support for a
central orchestrator repository to coordinate multi-host sync workflows.
A Docker image is published for use in CI workflows.
