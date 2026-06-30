# syncweaver & functracer — Tool Reference

These two tools form the automation backbone of Approach B (per-capsule repos). They are purpose-built for the OMIX/NIDAP architecture and are **not part of Approach A**.

---

## functracer

### What it does

- Given a capsule's entry script (`main.R`) and a package, `functracer` analyzes the call graph and returns every function the capsule depends on — both direct calls and transitive calls (functions called by functions).
- Given a new package ref (tag, branch, or commit SHA) and the previously locked commit, `functracer` determines whether the new version contains changes that would affect the capsule based on the list of functions used by the capsule entry script. In syncweaver workflows, refs are resolved to commit SHAs before comparison whenever possible.

### Why it exists

When a new version of the OMIX monorepo or MOSuite is released, not every capsule needs to be updated. A change to a volcano-specific plotting function is irrelevant to the heatmap capsule. But the reverse is equally important: a change made inside the volcano module might touch a shared core function that other capsules also depend on — and those capsules need to be updated too, even though the change originated in volcano. `functracer` answers both questions: _"Does this upstream change affect my capsule?"_ and _"Does this change in one module ripple out to other capsules that share the same underlying functions?"_

### How it works

```r
functracer::analyze_dependencies(entry_script, package)
```

Returns a table of every function dependency with:

- **function** — the function name
- **source** — which package it comes from (e.g. MOSuite)
- **dep_type** — `direct` (called by `main.R`) or `indirect` (called transitively)
- **call_path** — the full chain, e.g. `main.R -> batch_correct_counts -> plot_corr_heatmap`

### Querying the dependency map — two directions

functracer builds a complete dependency map across **all** capsules. Once built, it can be queried in either direction:

**Forward — upstream change → which capsules are affected?**
A new version of MOSuite or OMIX is released → functracer checks each capsule's dependency graph against the changed functions → only capsules that call those functions (directly or transitively) are updated. A change to a volcano-specific plotting function leaves the heatmap capsule untouched.

**Reverse — a module change → which other capsules are also affected?**
A developer edits a function inside the volcano module. If that function is shared with core, or is called transitively by other capsules, functracer identifies all capsules that depend on it — not just the volcano capsule. This prevents a scenario where a change to one module silently breaks another capsule that happened to share the same underlying function.

Because functracer traces **transitive** dependencies (the full call chain, not just direct calls), it catches indirect coupling that a manual review would likely miss. For example: volcano calls `plot_corr_heatmap`, which calls `extract_counts` from core. If `extract_counts` changes, functracer flags every capsule whose call graph passes through it — even if that capsule never explicitly references `extract_counts` in its own `main.R`.

### Decision logic

When any function changes — whether from an upstream release or an edit within a module:

1. Identify which functions changed
2. Query the full cross-capsule dependency map for those functions
3. **If a capsule's call graph includes the changed function** → update that capsule's lockfile and cut a new release
4. **If no capsule depends on the changed function** → do nothing

### Critical risk

A silent false negative — `functracer` incorrectly marking a capsule as unaffected when it is — would cause the capsule to ship stale code with no warning. This tool **must have thorough test coverage** before the system goes to production.

---

## syncweaver

### What it does

A command-line interface (CLI) for synchronizing code between upstream sources (the OMIX monorepo, MOSuite R package) and individual capsule repos. It handles both directions: pulling upstream changes down into a capsule repo, and contributing capsule edits back upstream.

### Why it exists

Capsule repos need to stay in sync with upstream sources, but the relationship is not a simple `git pull`. The monorepo has a different directory layout than the capsule repo, versions must be pinned independently, and changes from analysts working in Code Ocean need a structured path back to the upstream source — with conflict handling and patch management that GitHub Actions alone cannot reliably provide.

### The lockfile

Each capsule repo contains a `.syncweaver-lock.json` that specifies every upstream source the capsule depends on:

```json
{
  "sources": {
    "code/OMIX-core": {
      "repo_url": "https://github.com/CCBR/OMIX-core",
      "remote_subdir": "core/",
      "ref": "v1.0.0",
      "git_sha": "c09ee39"
    },
    "code/OMIX-module-volcano": {
      "repo_url": "https://github.com/CCBR/OMIX-core",
      "remote_subdir": "modules/volcano",
      "ref": "v1.3.2",
      "git_sha": "e2b4fa7"
    }
  }
}
```

Each source entry is **independently pinned** by both semantic version (`ref`) and exact commit (`git_sha`). A capsule can upgrade one source while holding another stable.

### Key operations

- **Sync downstream** — pull a new upstream release into a capsule repo, update the lockfile, open a PR for maintainer review
- **Patch upstream** — take analyst edits from a capsule repo and contribute them back to the upstream monorepo as a PR
- **Staleness check** — compare the locked `git_sha` against the commit SHA resolved from the requested upstream ref (or upstream HEAD when applicable) to detect whether a capsule is out of date
- **Conflict handling** — explicit patching operations, not silent overwrites; conflicts surface for human resolution before `main` is touched

### Multi-module support

Because the lockfile is a list of source entries, a capsule that needs code from multiple monorepo modules simply declares multiple entries. syncweaver pulls each independently and places them in the correct subdirectory of the capsule repo. There is no combinatorial complexity — adding a module dependency is adding one JSON entry.

### Relationship with functracer

syncweaver and functracer work in tandem:

1. New upstream release is tagged
2. `functracer` determines which capsules are affected
3. `syncweaver` updates only those capsules' lockfiles and opens PRs
4. GitHub Actions orchestrates the entire sequence automatically

---

## How they fit into the release pipeline

```
New release tagged in OMIX monorepo
         │
         ▼
functracer: which capsules depend on changed functions?
         │
         ├─ Capsule A: affected → syncweaver updates lockfile → PR opened → CI passes → maintainer merges → new capsule release
         │
         └─ Capsule B: unaffected → no action taken
```
