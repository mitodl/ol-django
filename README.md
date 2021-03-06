### Open Learning Django Apps

This repository is the home of MIT Open Learning's reusable django apps:

| App | Description | Status |
| --- | --- | --- |
| [`mitol-django-mail`](mitol-django-mail/) | Mail app and APIs | ![CI Status](https://img.shields.io/github/workflow/status/mitodl/ol-django/ci) ![Codecov](https://img.shields.io/codecov/c/github/mitodl/ol-django?flag=mitol_django_mail) |

### Releases

Changelogs are maintained according to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Version tags follow `{package-name}-v{major}.{minor}.{patch}`
To perform a release, run:
- `invoke release APPNAME VERSION`:
  - `APPNAME`: the name of an application directory
  - `VERSION`: a [`poetry version`](https://python-poetry.org/docs/cli/#version) arg value
- `git push --tags`

### Navigating this repository

- Django applications follow the naming convention `mitol-django-{name}`, `pip` installable by the same name.
- Within each app, code is implemented under the [implicit namespace](https://www.python.org/dev/peps/pep-0420/) `mitol`
  - Module paths follow the pattern `mitol.{name}`
  - The app itself is installable to `INSTALLED_APPS` as `"{name}"`.
- Within each app there is also a `testapp` directory that contains a full django app that tests integration of the reusable app. This app also functions as an example of how to use the app.

### Usage

We use `poetry` and `invoke` to manage apps and releases

- Install [`poetry`](https://python-poetry.org/docs/#installation) (best practice is to not use `pip install`)
- Install `invoke` and other repo-level deps via `pip install -r requirements.build.txt`
- Install `tox` and other testing deps via `pip install -r requirements.test.txt`

In each project, you'll want to:

```
poetry install -E test -E dev
```

### Migrations

To generate migrations for a reusable app, run the standard:

```
poetry run python manage.py makemigrations APP_NAME --name MIGRATION_NAME
```

where `APP_NAME` matches the `name` attribute from your `apps.py` app.

### Testing and Linting
In each reusable app:
```
poetry run pytest
poetry run black .
poetry run isort -y
poetry run mypy --show-error-codes mitol/
```

To run the full test suite against all python/django versions, you should run `tox` instead of `pytest` directly.

You'll also need to install the necessary versions of python if they're not already installed locally. `pyenv` is a good tool to manage these and you can set the versions used locally in this project using `pyenv local 3.6.10 3.7.7 3.8.2` for example. `tox-pyenv` is in the dependency list so it'll pick these up if you use it.

#### Adding a new app

- Create the project: `django-admin startproject mitol-django-$NAME && cd mitol-django-$NAME`
- Move the default app aside to use as the testapp: `mv mitol-django-$NAME testapp`
- Initialize poetry project: `poetry init`
- Create the reuseable app:
  - `mkdir mitol`
  - `./manage.py startapp $NAME`
  - `mv $NAME mitol/`
