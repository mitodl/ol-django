# Agent Instructions

## Repository Overview

MIT Open Learning's monorepo of reusable Django apps, published individually to PyPI as `mitol-django-{name}` packages. Managed as a `uv` workspace. Supports Python 3.10–3.13. Requires PostgreSQL for tests.

## Commands

```bash
# Install dependencies
uv sync

# Run all tests (requires PostgreSQL; defaults to DATABASE_URL, e.g., docker-compose Postgres on localhost:55432)
uv run pytest

# Run a specific test file
uv run pytest tests/<appname>/test_something.py

# Run a single test
uv run pytest tests/<appname>/test_something.py::test_function_name

# Lint and format
uv run ruff check --fix .
uv run ruff format .

# Django management (use testapp)
uv run testapp/manage.py <command>

# Create a changelog entry (required before every PR)
uv run scripts/changelog.py create --app <appname>
```

## Architecture

```
src/<appname>/          # Each reusable app's package root
  mitol/<appname>/      # Code lives under the `mitol` pkg_resources namespace package
    apps.py             # AppConfig: registered via full dotted path in INSTALLED_APPS (e.g., "mitol.<appname>.apps.<AppConfigName>")
    settings/           # App settings modules (imported by testapp)
  pyproject.toml        # Per-app package config and versioning

tests/<appname>/        # Test suites (mirror app structure, no `mitol` subdir)
testapp/                # Django project used only for testing
  main/settings/
    shared.py           # Base settings, INSTALLED_APPS, imports app settings modules
    test.py             # Test settings (loaded by pytest)
    dev.py              # Local dev settings (copy from example.dev.py if you need local overrides)

conftest.py             # Root-level pytest fixtures (learner, staff_user, clients, etc.)
pyproject.toml          # Root: workspace config, pytest config, ruff config, dev deps
```

## Key Conventions

**Namespace packages**: All app code lives under the `mitol` `pkg_resources` namespace package (each app's `mitol/__init__.py` calls `pkg_resources.declare_namespace(__name__)`). Module paths are `mitol.<appname>.*`. Apps register in `INSTALLED_APPS` using their `AppConfig` class (e.g., `"mitol.common.apps.CommonApp"`).

**Settings**: App-specific settings use a `MITOL_` prefix and are declared in `mitol.<appname>.settings.*` modules. The testapp imports them via `import_settings_modules()` in `testapp/main/settings/shared.py`. New apps must be added there.

**User model**: Never import `django.contrib.auth.models.User` directly. Use `get_user_model()` or `settings.AUTH_USER_MODEL`. Ruff enforces this via `banned-api`.

**Test placement**: Tests go in `tests/<appname>/test_*.py`. The `tests/` directory is on `pytest`'s `pythonpath` and contains test modules. `pytest` `pythonpath` includes `testapp`, `src`, and `tests`.

**Factories**: Use `factory-boy`. Common fixtures (`learner`, `staff_user`, `user_client`, etc.) are in root `conftest.py`. App-level factories live in `mitol/<appname>/factories/`.

**Changelogs**: Each app has a `changelog.d/` directory. A new changelog entry is **required** before submitting a PR. Use `uv run scripts/changelog.py create --app <appname>`.

**Versioning**: Date-based scheme `YYYY.MM.DD[.INC0]`. Tags follow `{package-name}/v{version}`.

**Adding a new app**: Copy `src/uvtestapp`, update names throughout, add to root `pyproject.toml` under `[project].dependencies` and `[tool.uv.sources]`, add to `testapp/main/settings/shared.py` (`INSTALLED_APPS` + `import_settings_modules`), and create `tests/<appname>/__init__.py`.

## CI

CI (`.github/workflows/ci.yml`) runs on every push across Python 3.10–3.13 with a PostgreSQL service container. It checks:
1. Changelog presence (`uv run scripts/changelog.py check`)
2. Tests (`uv run pytest`)

Releases to PyPI are triggered by version tags and run `uv build "src/<app-package>"` for the selected app.

## Ruff Configuration

Configured in root `pyproject.toml`. Key settings: `line-length = 88`, `inline-quotes = "double"`, `pydocstyle` convention = `pep257`. `S101` (assert) is allowed in test files. Migration files ignore several rules.
