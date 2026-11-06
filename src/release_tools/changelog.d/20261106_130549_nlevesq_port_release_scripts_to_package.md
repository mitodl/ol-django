### Added

- `mitol-release-tools`, the changelog, version and PyPI release tooling for a
  monorepo of Python packages, as a single `ol-release` command.
- `ol-release init` creates what the other commands read but never write: a
  per-package `changelog.d/` with scriv's config, a `CHANGELOG.md` carrying
  scriv's insert marker, a `[tool.bumpver]` table, and the `__version__`
  bumpver rewrites. `--check` reports the gaps without writing, so it works as
  a CI step.
