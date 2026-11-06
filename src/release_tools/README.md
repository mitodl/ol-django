# mitol-release-tools

Changelog, version and PyPI release management for a monorepo of Python
packages, as `ol-release`.

The model is that **a release is a version change merged to the default
branch**. Nothing is tagged or uploaded by hand: CI compares each package's
`[project] version` against PyPI and publishes whatever is missing there.

```
ol-release init --versioning date      bootstrap a repo for the commands below
ol-release changelog create --app X    write a new changelog fragment
ol-release changelog check             fail a PR with missing or misplaced fragments
ol-release version check               fail a PR whose version declarations disagree
ol-release prepare --app X             bump the version and collect the fragments
ol-release publish matrix              emit the packages that are not yet on PyPI
```

## Where it looks for packages

Packages come from the uv workspace the repo already declares, so there is no
second place to keep that list in step:

```toml
[tool.uv.workspace]
members = ["src/*", "testapp"]
```

Each matching directory with a `pyproject.toml` is a package. `[tool.uv.workspace] exclude`
is honoured. Repos with no workspace table fall back to `src/*`.

What the workspace cannot say is which members are the tool's business, so:

```toml
[tool.ol-release]
exclude = ["uvtestapp", "testapp"]
```

An excluded member is ignored entirely — no changelog required of it, no
version consistency enforced, never published. Separately, a package
classified `Private :: Do Not Upload` stays fully managed but is never offered
to `publish matrix`. Use the classifier for something whose changelog you still
want governed, and `exclude` for a directory the tool should not look at.

## Layout it expects

Per package: a `changelog.d/` of [scriv](https://scriv.readthedocs.io/)
fragments, a `CHANGELOG.md` carrying scriv's insert marker, and a
`[tool.bumpver]` table whose `file_patterns` name every file declaring the
version. Repo-wide: a shared entry-title template at `.scriv/entry_title.md.j2`.

`ol-release init` creates whatever is missing, and `init --check` reports it
without writing, which makes it usable as a CI step.

`--versioning date|semver` is required. It says which bumpver pattern to
configure for packages that have no `[tool.bumpver]` table yet, and it is not
inferred: `2024.10.24` is a valid `MAJOR.MINOR.PATCH` and a valid date both, so
a version string cannot say which scheme produced it. Packages that already
have the table keep the scheme declared there, and the flag does not touch
them. Run `init` once per scheme, scoped with `--app`, in a repo whose packages
disagree. Both are
idempotent and neither rewrites content it did not write.

Changelog fragments are markdown in every repository. A package that already
keeps a reStructuredText changelog keeps it: `init` adds a `CHANGELOG.md` that
links to it rather than converting it.

## Why click and not cyclopts

`ol-release version` and `ol-release changelog` re-export bumpver's and scriv's
own commands rather than reimplementing them, and those are click commands.
