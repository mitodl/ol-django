### Added

- `mitol-release-tools`, the changelog, version and PyPI release tooling for a
  monorepo of Python packages, as a single `ol-release` command.
- `ol-release init` creates what the other commands read but never write: a
  per-package `changelog.d/` with scriv's config, a `CHANGELOG.md` carrying
  scriv's insert marker, a `[tool.bumpver]` table, and the `__version__`
  bumpver rewrites. `--check` reports the gaps without writing, so it works as
  a CI step.

### Fixed

- `init` asks for `--versioning` instead of guessing the scheme from the
  current version. `2024.10.24` is a valid `MAJOR.MINOR.PATCH` and a valid
  date both, so the guess configured date-versioned packages for semantic
  bumping - `--bump patch` would have advanced it to the invented date
  `2024.10.25` - while `1.0` and `0.1.0a1` got a date pattern bumpver rejects.
  The flag is only needed for packages with no `[tool.bumpver]` table; one
  that has it already declares its scheme there.
- `init` normalises `[project] version` to double quotes, so the bumpver file
  pattern it writes alongside can actually match it. A single-quoted version
  left bumpver silently unable to rewrite that declaration.
