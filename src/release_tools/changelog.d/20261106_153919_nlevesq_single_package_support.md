### Added

- `[tool.ol-release] layout = "single"` for a repository that is one package
  rather than a workspace of many. The root `pyproject.toml` is the package,
  tags drop the `{name}/` prefix, and `--app` becomes optional. `tag-format`
  overrides the tag convention for either layout.

### Fixed

- A single-package repository discovered no packages at all, so
  `changelog check`, `version check` and `publish matrix` all reported success
  while examining nothing - and the package would never have been released.
- `changelog check`, `version check` and `publish matrix` now fail instead
  of reporting success when they find no packages to examine.
- `init` picks the module that `[tool.bumpver.file_patterns]` actually
  rewrites for `mitol-django-authentication`, where it previously chose a
  stale `__init__.py` at the package root.
- `CHANGELOG.md`, `changelog.d/` and the lockfile are matched by path
  component rather than by a glob needing a leading directory, so a package at
  the repository root is recognised as changelog bookkeeping rather than as
  source.
- `init` prunes virtualenv and build trees while looking for the module that
  holds `__version__`, instead of walking the entire checkout.
- `prepare` skips the lockfile refresh when the repository has no `uv.lock`,
  rather than failing after the version has already been bumped.
- `init` no longer follows directory symlinks while looking for the version
  module, so a link pointing at an ancestor cannot send it in circles, and an
  unreadable directory is skipped rather than fatal.
- An unrecognised `[tool.ol-release] layout` is reported instead of silently
  reverting to `workspace`, which discovered nothing and passed every gate.
- A `tag-format` that cannot render is rejected when the config is read,
  rather than raising from `prepare` after the version has been bumped and
  the fragments collected.
