# mitol-release-tools

Changelog, version and PyPI release management for Python packages, as
`ol-release`. Works on a monorepo of many packages or on a repository that is
a single package.

The model is that **a release is a version change merged to the default
branch**. Nothing is tagged or uploaded by hand: CI compares each package's
`[project] version` against PyPI and publishes whatever is missing there.

```
ol-release init                        bootstrap a repo for the commands below
ol-release changelog create --app X    write a new changelog fragment
ol-release changelog check             fail a PR with missing or misplaced fragments
ol-release version check               fail a PR whose version declarations disagree
ol-release prepare --app X             bump the version and collect the fragments
ol-release publish matrix              emit the packages that are not yet on PyPI
```

## Layout

A repository that is one package says so, and gets the conventions that come
with that - tags without a package prefix, and `--app` optional since there is
only one answer:

```toml
[project]
name = "my-package"
version = "1.2.3"

[tool.ol-release]
layout = "single"
```

The default is `layout = "workspace"`, so a monorepo needs nothing. Layout is
stated rather than inferred: a repo can have both a root `[project]` and a
workspace, and guessing wrong changes what gets tagged and published.

`tag-format` overrides the default for either layout - `{name}/v{version}` for
a workspace, `v{version}` for a single package:

```toml
[tool.ol-release]
tag-format = "release-{version}"
```

In single layout the whole repository is the package, so anything at the root
counts as a change to it - except `CHANGELOG.md`, `changelog.d/` and the
lockfile. `init` writes `.scriv/` and `changelog.d/` into that same tree, so
exclude both from your build backend's sdist and wheel configuration.

CI for a single-package repo builds with a bare `uv build`: `--package` only
means something inside a workspace and is rejected outside one.

## Where it looks for packages

In the default workspace layout, packages come from the uv workspace the repo
already declares, so there is no second place to keep that list in step:

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

`--versioning date|semver` is needed only when a package has no
`[tool.bumpver]` table yet, and `init` asks for it by name when that is the
case. It is never inferred from the version: `2024.10.24` is a valid
`MAJOR.MINOR.PATCH` and a valid date both, so the string cannot say which
scheme produced it. A package that already has the table keeps the scheme
declared there. Run `init` once per scheme, scoped with `--app`, in a repo
whose packages disagree. Both are
idempotent and neither rewrites content it did not write.

Changelog fragments are markdown in every repository. A package that already
keeps a reStructuredText changelog keeps it: `init` adds a `CHANGELOG.md` that
links to it rather than converting it.

## Why click and not cyclopts

`ol-release version` and `ol-release changelog` re-export bumpver's and scriv's
own commands rather than reimplementing them, and those are click commands.
