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
7. Before the first release, register `mitol-django-<appname>` as a pending publisher on PyPI. Without it the first publish fails. See [PyPI Trusted Publishing](#pypi-trusted-publishing).

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

### Linting and formatting

Hooks live in `.pre-commit-config.yaml` and are run by [prek](https://prek.j178.dev/), which `uv sync` installs. The config format is unchanged, so the file stays readable by `pre-commit` too.

- Install the git hook: `uv run prek install -f`. The `-f` replaces an existing `pre-commit` hook, if you have one installed from before.
- Run every hook over the whole repo: `uv run prek run --all-files`

CI runs the same hooks in the `prek` check (`.github/workflows/autofix.yml`), and autofix.ci pushes a commit with any fixes to your PR.

### Changelogs

We maintain changelogs in `changelog.d/` directories with each app. To create a new changelog for your changes, run:

- `uv run scripts/changelog.py create --app APPNAME`
  - `APPNAME`: the name of an application directory

You will need to adjust permissions/ownership on the new file if you're using the Compose setup.

Then fill out the new file that was generated with information about your changes. **Do this before you put up a PR for your changes.**

A fragment ships in the same PR as the code it describes, and that PR must not touch the app's `CHANGELOG.md`. Folding fragments into `CHANGELOG.md` is what cutting a release does, and it happens in its own PR — see below. `uv run scripts/changelog.py check` enforces the split, so a reviewer reading a code PR only ever has to read the new fragments.

### Releases

Changelogs are maintained according to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning uses a date-based versioning scheme with incremental builds on the same day.
Version tags follow `{package-name}/v{version}` and are created by CI.

**A release is a version change merged to `main`.** There are no tags to push and
no release commands to run against the remote.

Cutting a release is its own PR, containing nothing but the release. The
fragments it collects were written earlier, each alongside the code change it
describes.

1. Start from an up-to-date `main` with no other work in progress.

2. Prepare the release on a branch:

   ```shell
   uv run scripts/release.py prepare --app APPNAME
   ```

   This bumps the app's version everywhere it is declared, folds its
   `changelog.d/` fragments into `CHANGELOG.md`, deletes them, and refreshes
   `uv.lock`.

3. Commit the result, open a PR, and merge it once CI is green. It needs no
   approval from anyone else — see below.

Once the checks pass on `main`, the `publish` job in
[the CI workflow](.github/workflows/ci.yml) builds every package whose version
is not yet on PyPI, uploads it, and then creates the version tag.

Do not add code to a release PR. CI rejects a PR that rewrites an app's
`CHANGELOG.md` while changing anything under that app other than the two files
that declare its version.

#### Release PRs approve themselves

A PR that contains nothing but a release is approved automatically by
[`release-auto-approve.yml`](.github/workflows/release-auto-approve.yml), so
cutting one does not need a second person to read a diff `prepare` generated.
`uv run scripts/changelog.py check-release-only` is what decides, and you can run
it on your branch to see what it sees.

It is stricter than the `changelog` job above in two ways. That job only looks
under `src/APPNAME/`, so anything else in the diff — a workflow, a script, the
root `pyproject.toml`, a second app's release — means no approval here. And it
exempts the two files that declare the version by path, where this one checks
what changed inside them: `mitol/APPNAME/__init__.py` may move its `__version__`
line and nothing else, the app's `pyproject.toml` may move its two version
declarations and nothing else, and `uv.lock` may record the new version and
nothing else. All three ship, so a path-level allowance is not enough.

Every push re-decides, and each run withdraws the previous approval before it
re-checks — so an approval on the PR means a complete run just verified the diff
as it stands. That also makes the approval best-effort rather than sticky: a run
that is cancelled or fails partway leaves a legitimate release PR unapproved
until the next push or a re-run. A PR that does not qualify is not broken; it
just needs a human, like any other.

If you would rather not use `prepare`, editing the version by hand works too —
the workflow only reads `[project] version` from the app's `pyproject.toml`. Keep
the other two declarations (`[tool.bumpver] current_version` and
`mitol/APPNAME/__init__.py`) in step, or `uv run scripts/version.py check` fails
CI.

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

A missing publisher does not fail the OIDC token exchange, because other
projects already trust this workflow. The upload fails instead:

| Upload error | Fix |
| --- | --- |
| `400 Non-user identities cannot create new projects` | The project is not on PyPI yet, and no pending publisher for it matches all four values. Add one, or replace a mismatched one, under *Your account → Publishing*. |
| `403 Invalid API Token: OIDC scoped token is not valid for project` | The project exists, but none of its publishers matches all four values. Add one under *Manage project → Publishing*. |

PyPI requires every field to match, so a publisher with the right workflow but a
different environment (such as `mitodl` instead of `pypi`) does not match. PyPI
cannot edit a publisher: add a corrected one, then remove the old one.

The publish job adds an error annotation naming the case that applies. Once the
publisher is registered, re-run the failed jobs (`gh run rerun <run-id> --failed`).
