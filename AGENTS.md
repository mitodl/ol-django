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

# Prepare a release (bumps the version, folds changelog.d into CHANGELOG.md)
uv run scripts/release.py prepare --app <appname>
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

**Versioning**: Date-based scheme `YYYY.MM.DD[.INC0]`. Tags follow `{package-name}/v{version}` and are created by CI, never by hand. Each app declares its version in three places (`[project] version`, `[tool.bumpver] current_version`, and `mitol/<appname>/__init__.py`); `uv run scripts/release.py prepare` updates all three and `uv run scripts/version.py check` enforces that they agree.

**Releases**: A release is a version change merged to `main`. The `detect-releases` and `publish` jobs in `.github/workflows/ci.yml` then build every app whose `pyproject.toml` version is not yet on PyPI, publish it via Trusted Publishing (OIDC, no API token), and create the tag. PyPI is the source of truth for what is already released, so re-runs are safe and multi-app bumps work. Never add a tag-triggered publish step, and keep publishing in `ci.yml` rather than a `workflow_run` workflow (zizmor rejects that trigger).

**Adding a new app**: Copy `src/uvtestapp`, update names throughout, add to root `pyproject.toml` under `[project].dependencies` and `[tool.uv.sources]`, add to `testapp/main/settings/shared.py` (`INSTALLED_APPS` + `import_settings_modules`), and create `tests/<appname>/__init__.py`.

## CI

CI (`.github/workflows/ci.yml`) runs on every push across Python 3.11–3.13 and Django 4.2, 5.0, 5.1, and 5.2 with a PostgreSQL service container. It checks:
1. Changelog presence (`uv run scripts/changelog.py check`)
2. Version consistency (`uv run scripts/version.py check`)
3. Tests (`uv run pytest`)

On `main`, the `detect-releases` and `publish` jobs then release any app whose version is not yet on PyPI, building with `uv build --package <pypi-name>`. Build by PyPI project name rather than directory: `mitol-drf-lint` does not follow the `mitol-django-<dir>` convention.

## Ruff Configuration

Configured in root `pyproject.toml`. Key settings: `line-length = 88`, `inline-quotes = "double"`, `pydocstyle` convention = `pep257`. `S101` (assert) is allowed in test files. Migration files ignore several rules.
