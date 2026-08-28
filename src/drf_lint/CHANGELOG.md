# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses date-based versioning.

<!-- scriv-insert-here -->

<a id='changelog-2026.8.28'></a>
## [2026.8.28] - 2026-08-28

### Removed

- Removed support for Python 3.10

### Added

- Added support for glob file paths
- Added support for --exclude argument to exclude files like tests

- Cross-file analysis. drf-lint now builds an index of the whole project, closed
  over the call graph, and resolves each serializer's `Meta.model` through its
  own imports - so a query hidden behind a model property is reported at the
  serializer that touches it.
  - `ORM003` - a query-performing model property accessed in a serializer method
  - `ORM004` - a query-performing function or method called in a serializer method
  - `ORM005` - a query-performing model member named in `fields` or a `source=`
  - `ORM006` - traversing an unfetched foreign key
- Awareness of `required_prefetches` on `mitol.common.serializers.BaseSerializer`
  subclasses. A relation the declaration covers is no longer reported, provided
  the access actually reads the prefetch cache; `.filter()`, `.count()` and
  friends re-query regardless and are reported with a message that says so.
  - `ORM007` - a relation the serializer reads that is missing from
    `required_prefetches`, naming the entry to add
  - `ORM008` - a `BaseSerializer` subclass that never declares
    `required_prefetches` (today this only fails on instantiation)
  - `ORM009` - an entry `is_prefetched()` can never satisfy, such as a
    `"author__books"` traversal path
- An on-disk index cache at `.drf_lint_cache.json`, invalidated per file by size
  and mtime, plus `--build-index` to warm it in CI.
- New flags: `--project-root`, `--no-cross-file`, `--index-exclude`,
  `--index-cache`, `--no-index-cache`, `--build-index`, `--select`, `--ignore`,
  `--model-resolution`, `--receiver-heuristic`, `--prefetch-base` and
  `--warn-unresolved`, all also settable under `[tool.drf_lint]` in
  `pyproject.toml`.
- `# drf-lint: query` and `# drf-lint: no-query` markers to correct the index at
  a member's definition, rather than at every call site.

### Changed

- Serializer write-path methods (`validate`, `validate_<field>`, `create`, `update`, `to_internal_value`) are now exempt from ORM N+1 checks. These methods only execute during POST/PATCH/PUT operations on a single resource, making N+1 detection inapplicable.

- The query-detection vocabulary moved into `mitol.drf_lint.rules.patterns`, now
  shared by the LibCST checker and the `ast`-based indexer. Two changes come with
  it: `ORM001` also recognises `_default_manager` and `_base_manager`, and
  `ORM002` no longer flags `.exists()` calls that carry arguments, since
  `QuerySet.exists()` takes none and `Storage.exists(name)` is not the ORM.
- `check_source()` and `check_file()` take an optional `CheckContext`. Without
  one there is no index, so only `ORM001` and `ORM002` are reported. Not quite
  the previous behaviour: `required_prefetches` is honoured whether or not there
  is an index, so a declaration in the file under check can now silence an
  `ORM002` that was previously reported.
- The `drf-serializer-orm-check` pre-commit hook sets `require_serial: true`, so
  parallel invocations do not each build their own index.

### Notes

- Upgrading will surface new violations in existing projects - `ORM003` through
  `ORM009`, and also `ORM001` on any `_default_manager` / `_base_manager` access
  that the narrower `.objects`-only check used to miss. Run
  `drf-lint --generate-baseline` once, or roll the new codes out with
  `--select`.
- `--no-cross-file` turns off the index and `required_prefetches` awareness,
  leaving `ORM001` and `ORM002` as the only rules in play. `ORM001` keeps its
  widened manager vocabulary either way, so this is the previous set of rules
  rather than the previous set of findings.

## 2025.3.27

- Initial release: `ORM001` and `ORM002` rules for detecting ORM queries inside DRF serializer methods
