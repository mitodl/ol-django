# mitol-drf-lint

Linting rules for Django REST Framework serializers. Detects the database
queries that turn a list endpoint into an N+1 - whether the query is written in
the serializer, hidden behind a model property, or pulled in just by naming a
field.

## Rules

| Rule | Description |
|------|-------------|
| `ORM001` | Django ORM manager access (`.objects.`) inside a serializer method |
| `ORM002` | Related-manager queryset call (`instance.children.filter()` etc.) inside a serializer method |
| `ORM003` | A model **property** that performs a query, accessed in a serializer method |
| `ORM004` | A function or method that performs a query, called in a serializer method |
| `ORM005` | A query-performing model member named in `fields` or a `source=` |
| `ORM006` | Traversing an unfetched foreign key (`instance.author.name`) |
| `ORM007` | A relation the serializer reads that is missing from `required_prefetches` |
| `ORM008` | A `BaseSerializer` subclass that never declares `required_prefetches` |
| `ORM009` | A `required_prefetches` entry `is_prefetched()` can never satisfy |

`ORM001` and `ORM002` need only the file in front of them. Everything else uses
the project index described below.

## Installation

```bash
pip install mitol-drf-lint
```

## Usage

```bash
# Check specific files
drf-lint path/to/serializers.py

# Check all serializers in a project
drf-lint $(find . -name "serializers.py" -not -path "*/migrations/*")

# Generate a baseline to suppress existing violations (for gradual rollout)
drf-lint --generate-baseline --baseline drf_lint_baseline.json --exclude '**/*_test.py' '*/serializers.py' '*/serializers/**/*.py'

# Subsequent runs ignore violations present in the baseline
drf-lint --baseline drf_lint_baseline.json --exclude '**/*_test.py' '*/serializers.py' '*/serializers/**/*.py'
```

Exit code is `0` when no new violations are found, `1` when violations are detected.

## Cross-file analysis

The query that costs you is usually not in the serializer:

```python
# models.py
class Course(models.Model):
    @property
    def run_count(self):
        return self.runs.count()  # the query lives here


# serializers.py
class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "run_count"]  # ORM005 - one query per row

    def get_summary(self, instance):
        return f"{instance.run_count} runs"  # ORM003
```

To catch that, drf-lint builds an index of the project: every class, member and
import, closed over the call graph so that a property which only *reaches* a
query several calls away still counts. It then resolves the serializer's
`Meta.model` through the file's own import statements and checks what the
serializer touches against that model.

Nothing is imported or executed, so a project that cannot be booted still
analyses fine, and Django is not a dependency.

**Discovery.** The project root is the nearest ancestor holding `.git`,
`pyproject.toml`, `manage.py` or `setup.cfg`. Every `.py` file underneath is
indexed, minus hidden directories and the usual non-source ones
(`migrations`, `node_modules`, `build`, `dist`, `site-packages`, …).

**Caching.** Scan results are cached in `.drf_lint_cache.json` at the project
root, keyed on each file's size and mtime, so only edited files are re-read.
Add it to `.gitignore`. A cold build of a few thousand files takes about a
second; a warm one is a fraction of that. Warm a CI cache with
`drf-lint --build-index`.

**Confidence.** The cross-file rules are deliberately strict. A member is only
checked against the model when `Meta.model` resolves to an indexed class, and
`instance` is only treated as that model where DRF guarantees it: the second
argument of a `get_<field>` method or of `to_representation`, `self.instance`,
and single-assignment aliases of those. If anything cannot be resolved, nothing
is reported.

## `required_prefetches`

The hardest question a static checker faces here is *"but is it already
prefetched?"* - a property that queries is not an N+1 if the viewset
`prefetch_related`'d it.

`mitol.common.serializers.BaseSerializer` answers that question in the code
itself. Subclasses declare `required_prefetches`, and `to_representation`
verifies each entry at runtime, raising under `DEBUG` and pytest. drf-lint
reads the same declaration, so it can stay quiet about accesses that are
provably free - and name the missing entry when they are not.

```python
class CourseSerializer(BaseSerializer):
    required_prefetches = ["runs"]

    def get_runs(self, instance):
        return list(instance.runs.all())  # silent: reads the prefetch cache

    def get_published(self, instance):
        return instance.runs.filter(live=True)  # ORM002: .filter() re-queries
```

**A prefetch only helps for accesses that read its cache.** `.all()` and plain
iteration do. `.filter()`, `.exclude()`, `.order_by()` and `.annotate()` build a
fresh queryset; `.count()`, `.exists()`, `.first()` and `.last()` add their own
SQL. Those are still reported, with a message saying the prefetch does not help
and pointing at `Prefetch(queryset=...)`.

| Situation | Result |
|---|---|
| `instance.topics.all()`, `"topics"` declared | silent |
| `instance.author.name`, `"author"` declared | silent |
| `fields = ["run_list"]` where the property does `self.runs.all()`, `"runs"` declared | silent |
| `instance.topics.filter(...)`, `"topics"` declared | `ORM002`, with a tailored message |
| `instance.topics.all()`, not declared | `ORM007` - *add `"topics"`* |
| a relation serialized as a field, not declared | `ORM007` |
| `fields = ["run_count"]` where the property does `self.runs.count()` | `ORM005` - no prefetch fixes this |

`ORM008` catches a subclass with no declaration at all, which today only fails
when something instantiates it. `ORM009` catches an entry `is_prefetched()` can
never resolve - notably a traversal path like `"author__books"`, which is not a
field name and appears in no cache, so it raises on every serialization. A
plain name that is not a model field is *not* reported: django-prefetch
populates arbitrary names in `instance.__dict__`, which `is_prefetched` honours
on purpose.

Point the rules at your own base class with `--prefetch-base`, repeatable, if
your project wraps `BaseSerializer`.

## Configuration

Flags, or `[tool.drf_lint]` in `pyproject.toml`. The command line wins.

| Flag | Default | Purpose |
|------|---------|---------|
| `--project-root PATH` | auto-discovered | What to index |
| `--no-cross-file` | off | Run `ORM001`/`ORM002` only, as before the index existed |
| `--index-exclude GLOB` | - | Globs to leave out of the index (repeatable, or comma-separated) |
| `--index-cache PATH` | `<root>/.drf_lint_cache.json` | Cache location |
| `--no-index-cache` | off | Always rebuild |
| `--build-index` | - | Build or refresh the cache, then exit |
| `--select CODE` / `--ignore CODE` | all rules on | Staged rollout (repeatable, or comma-separated) |
| `--model-resolution {unique,never,any}` | `unique` | Fallback when `Meta.model` will not resolve through imports |
| `--receiver-heuristic {strict,names}` | `strict` | `names` also trusts a parameter *called* `instance`/`obj` |
| `--prefetch-base DOTTED` | `mitol.common.serializers.BaseSerializer` | Bases carrying the prefetch contract |
| `--warn-unresolved` | off | Report unresolvable `Meta.model` values on stderr; exit code unaffected |

```toml
[tool.drf_lint]
ignore = ["ORM006"]
model_resolution = "unique"
prefetch_base_serializers = ["myproject.serializers.AppSerializer"]
```

Index problems never fail a run: if no root can be found, or the scan hits an
error, drf-lint reports what the single-file rules found and exits normally.

## pre-commit Integration

### In this repo (local)

```yaml
- repo: local
  hooks:
    - id: drf-serializer-orm-check
      name: DRF Serializer ORM Check
      entry: drf-lint
      language: python
      files: "serializers\\.py$"
      require_serial: true
```

### From other repos

```yaml
- repo: https://github.com/mitodl/ol-django
  rev: <commit-sha-or-tag>
  hooks:
    - id: drf-serializer-orm-check
```

`require_serial` matters: parallel invocations would each build their own index.

## Suppressing individual violations

Add `# noqa: ORM003` (or any other code) at the end of the offending line, or
`# noqa` to suppress every rule on that line. This works on an individual
element of a multi-line `fields` list, since suppression is per source line:

```python
    fields = [
        "id",
        "run_count",  # noqa: ORM005
    ]
```

To silence a model member everywhere at once, mark it at the definition:

```python
@property
def looks_like_a_query(self):  # drf-lint: no-query
    return self.cached_thing.all()
```

`# drf-lint: no-query` also cuts propagation, so callers of that member stay
clean. `# drf-lint: query` does the reverse, for a member the scanner cannot
see through.

## How it works

Files under check are parsed with [LibCST](https://libcst.readthedocs.io/),
which preserves comments and exact columns - needed for `# noqa` and for
pointing at the right element of a `fields` list. The project index is parsed
with the stdlib `ast` module instead, which is far faster and needs neither.
The two share one vocabulary of query patterns so they cannot drift apart.

The checker walks the tree looking for:

1. **Serializer classes**: any class whose name ends in `Serializer` or that
   inherits from a class containing `Serializer`.
2. **Inside methods of those classes**: calls and attribute accesses that reach
   the database, directly or through the index.
3. **In `Meta` and the class body**: `fields`, `source=` and
   `required_prefetches` declarations.

Methods inside inner classes (e.g. `class Meta`) are not checked, and
write-path methods (`validate`, `validate_*`, `create`, `update`,
`to_internal_value`) are exempt except on `ListSerializer` subclasses, whose
bulk `create`/`update` can genuinely N+1.

## Limitations

- **`fields = "__all__"` cannot pull in a property.** DRF expands it through
  `model._meta`, which knows only concrete fields and relations. A property
  becomes a field only when named explicitly. The same reasoning applies to
  `exclude`. Declared fields carrying a `source=` are still checked either way.
- **A prefetched-but-unused relation is not reported.** There is no ORM rule for
  a stale `required_prefetches` entry yet.
- **Nested serializers do not propagate their prefetches.** A child's
  `required_prefetches` would have to appear on the parent as `"author__books"`,
  which `is_prefetched()` cannot evaluate - see `ORM009`.
- **Serializer `Meta` inheritance is followed one level.**
- **Dotted `source="a.b.c"` is checked on its first segment only.**
- **Third-party base classes terminate the inheritance walk**, so a querying
  property defined in an installed package is not seen.
- **The hook only sees the files it is given.** Adding a querying property to
  `models.py` creates violations in serializer files pre-commit will not
  re-check. Run `drf-lint --build-index && drf-lint '**/serializers.py'` in CI
  to catch those.
