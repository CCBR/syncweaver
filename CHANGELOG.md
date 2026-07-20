## syncweaver development version

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
