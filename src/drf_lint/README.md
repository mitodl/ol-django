# mitol-drf-lint

LibCST-based linting rules for Django REST Framework serializers. Detects Django ORM queries executed inside DRF serializer methods, which cause N+1 query bugs.

## Rules

| Rule | Description |
|------|-------------|
| `ORM001` | Django ORM manager access (`.objects.`) inside a serializer method |
| `ORM002` | Related-manager queryset call (`instance.children.filter()` etc.) inside a serializer method |

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
drf-lint --generate-baseline --baseline drf_lint_baseline.json path/to/serializers.py

# Subsequent runs ignore violations present in the baseline
drf-lint --baseline drf_lint_baseline.json path/to/serializers.py
```

Exit code is `0` when no new violations are found, `1` when violations are detected.

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
```

### From other repos

```yaml
- repo: https://github.com/mitodl/ol-django
  rev: <commit-sha-or-tag>
  hooks:
    - id: drf-serializer-orm-check
```

## Suppressing individual violations

Add `# noqa: ORM001` or `# noqa: ORM002` at the end of the offending line, or
`# noqa` to suppress all rules on that line:

```python
def get_image(self, instance):
    item = instance.children.order_by("position").first()  # noqa: ORM002
```

## How it works

The checker uses [LibCST](https://libcst.readthedocs.io/) to parse Python source
files into a concrete syntax tree and walks the tree looking for:

1. **Serializer classes**: any class whose name ends in `Serializer` or that
   inherits from a class containing `Serializer`.
2. **Inside methods of those classes**: any `Call` node matching ORM patterns.

**ORM001 pattern**: attribute chain containing `.objects` (Django model manager),
e.g. `User.objects.filter(...)`.

**ORM002 pattern**: queryset method call on a multi-level attribute access,
e.g. `instance.children.all()`, `instance.resource_prices.filter(...)`.

Methods inside inner classes (e.g. `class Meta`) are not checked.
