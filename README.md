### Open Learning Django Apps

This repository is the home of MIT Open Learning's reusable django apps.

### Getting Started

This set of libraries is managed using [uv](https://docs.astral.sh/uv/).

### Setup

To run this app in local development mode, copy `testapp/main/settings/example.dev.py` to  `testapp/main/settings/dev.py`. This file has the same defaults as `testapp/main/settings/test.py`, but it is gitignored so you can safely add secrets to it. `manage.py` and `main/wsgi.py` both load `dev.py`.


#### Use on your host system

- Install `xmlsec` native libraries for your OS: https://xmlsec.readthedocs.io/en/stable/install.html
- Install `uv` as described in the manual: https://docs.astral.sh/uv/
- Bootstrap the `uv` environment: `uv python install 3.11 ; uv sync`

#### Use the Docker Compose environment (recommended)

The Compose environment includes a container for general use called `shell`. You'll get a shell with `uv` already set up, and with a PostgreSQL database available.

- Ensure that 'other' users can write to the repo directory: `chmod -R o+w .`
- Build the containers: `docker compose build`
- Get a shell in the `shell` container: `docker compose run --rm -ti shell bash`

The database server is exposed on port 55432 locally - you can override this by setting `POSTGRES_PORT` in your environment.

### Navigating this repository

- Django applications follow the naming convention `mitol-django-{name}`, `pip` installable by the same name.
- Within each app, code is implemented under the [implicit namespace](https://www.python.org/dev/peps/pep-0420/) `mitol`
  - Module paths follow the pattern `mitol.{name}`
  - The app itself is installable to `INSTALLED_APPS` as `"{name}"`.

### Adding a new app

Apps go in the `src/` folder. Test suites for apps go in the `tests/` folder (which is a Django app for this purpose).

Per convention, use `_` for spaces within your app name if you must use spaces.

To add a new one, it's easiest to copy one of the existing apps. There's one called `uvtestapp` that has (basically) nothing in it, and can be used for this purpose.

1. Duplicate the `uvtestapp` folder, and rename the copy to the name you wish to use.
2. Update things within the folder to use the new name. This will include:
   * The folder under `mitol`
   * `README.md`
   * `pyproject.toml`
   * `mitol/<appname>/__init__.py`
   * `mitol/<appname>/apps.py`
3. Update the root `pyproject.toml`
   * Under `[project]`, add the new app into `dependencies` in the same format that's already there.
   * Under `[tool.uv.sources]`, add a new entry for the new app, using (again) the same format as the other entries.
4. Test building: `uv build --package mitol-django-<appname>` . (This ensures that uv is OK with your changes.)
5. Add space for the app in the `tests` app: `mkdir tests/mitol/<appname>` and add a blank `__init__.py` to it.
6. Add the app to `testapp/main/settings/shared.py`
   * You must add it to `INSTALLED_APPS`.
   * If your app has configuration settings, add to the `import_settings_module` call at the top too.

You can now add your code and tests.

### Running Django commands

You can run Django commands by using the `testapp` that's included:

`uv run tests/manage.py`

The management commands for each ol-django app should be available. If you need to run things that require a database, run it in the Docker Compose setup as it contains a PostgreSQL database.

### Running tests

Run `uv run pytest`. This should run all the tests. If you want to run a specific one, specify with a file path as per usual. Use the whole path (so `tests/mitol/<appname>/etc`).

#### Testing with tox

If you want to run the full test suite for the CI Python/Django matrix (Python 3.11-3.13 and Django 4.2, 5.0, 5.1, 5.2), install tox and run:

```shell
uv tool install tox --with tox-uv
tox
```

### Changelogs

We maintain changelogs in `changelog.d/` directories with each app. To create a new changelog for your changes, run:

- `uv run scripts/changelog.py create --app APPNAME`
  - `APPNAME`: the name of an application directory

You will need to adjust permissions/ownership on the new file if you're using the Compose setup.

Then fill out the new file that was generated with information about your changes. These fragments are folded into the app's `CHANGELOG.md` when you prepare a release. **Do this before you put up a PR for your changes.**

### Releases

Changelogs are maintained according to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning uses a date-based versioning scheme with incremental builds on the same day.
Version tags follow `{package-name}/v{version}` and are created by CI.

**A release is a version change merged to `main`.** There are no tags to push and
no release commands to run against the remote.

1. On a branch, prepare the release:

   ```shell
   uv run scripts/release.py prepare --app APPNAME
   ```

   This bumps the app's version everywhere it is declared and folds its
   `changelog.d/` fragments into `CHANGELOG.md`.

2. Commit the result, open a PR, and merge it once CI is green.

That is the whole process. Once the checks pass on `main`, the `publish` job in
[the CI workflow](.github/workflows/ci.yml) builds every package whose version
is not yet on PyPI, uploads it, and then creates the version tag.

If you would rather not use `prepare`, editing the version by hand works too —
the workflow only reads `[project] version` from the app's `pyproject.toml`. Two
checks still apply:

- Keep the other two declarations (`[tool.bumpver] current_version` and
  `mitol/APPNAME/__init__.py`) in step, or `uv run scripts/version.py check`
  fails CI.
- Touching an app still requires a changelog change in the same PR, either a
  new `changelog.d/` fragment or an edit to its `CHANGELOG.md`, or
  `uv run scripts/changelog.py check` fails CI.

#### How the workflow decides what to publish

For each app it compares the version in `pyproject.toml` against PyPI, and
publishes only what is missing there. PyPI is the source of truth rather than
the tag history, because this repository contains published versions that were
never tagged. Practical consequences:

- Re-running the workflow is safe; already-published versions are skipped.
- Bumping several apps in one PR releases all of them.
- Editing a `pyproject.toml` without changing its version releases nothing.
- The tag is created only after a successful upload, so a tag always means the
  version really is on PyPI.

#### PyPI Trusted Publishing

Publishing uses [Trusted Publishing](https://docs.pypi.org/trusted-publishers/):
GitHub mints a short-lived OIDC token for the job, so there is no PyPI API token
in this repository.

Each PyPI project must be told to trust this workflow once, under *Manage project
→ Publishing*:

| Field | Value |
| --- | --- |
| Owner | `mitodl` |
| Repository | `ol-django` |
| Workflow name | `ci.yml` |
| Environment | `pypi` |

The values are identical for every package. A package whose publisher is not yet
configured simply fails its own matrix job, without affecting the others.

When adding a **new** package, register it as a
[pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
with the same values before its first release, since the PyPI project will not
exist yet.
