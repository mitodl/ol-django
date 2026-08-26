### Added

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

- The query-detection vocabulary moved into `mitol.drf_lint.rules.patterns`, now
  shared by the LibCST checker and the `ast`-based indexer. `ORM001` and
  `ORM002` behave as before, except that `ORM001` also recognises
  `_default_manager` and `_base_manager`.
- `check_source()` and `check_file()` take an optional `CheckContext`. Without
  one there is no index, and both behave exactly as they did before.
- The `drf-serializer-orm-check` pre-commit hook sets `require_serial: true`, so
  parallel invocations do not each build their own index.

### Notes

- Upgrading will surface new violations in existing projects. Run
  `drf-lint --generate-baseline` once, or roll the new codes out with
  `--select`.
- `--no-cross-file` restores the previous single-file behaviour exactly.
