### Open Learning Django Apps

This repository is the home of MIT Open Learning's reusable django apps

### Changelogs

We maintain changelogs in `changelog.d/` directories with each app. To create a new changelog for your changes, run:

- `mkdir ./src/mitol/{APPNAME}/changelog.d`
- `rye run build changelog create --app APPNAME`
  - `APPNAME`: the name of an application directory

Then fill out the new file that was generated with information about your changes. These changes will all be merged down into `CHANGELOG.md` when a release is generated.

### Releases

Changelogs are maintained according to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning uses a date-based versioning scheme with incremental builds on the same day.
Version tags follow `{package-name}/v{version}`
To perform a release, run:
- `rye run build release create --app APPNAME --push`:
  - `APPNAME`: the name of an application directory

### Navigating this repository

- Django applications follow the naming convention `mitol-django-{name}`, `pip` installable by the same name.
- Within each app, code is implemented under the [implicit namespace](https://www.python.org/dev/peps/pep-0420/) `mitol`
  - Module paths follow the pattern `mitol.{name}`
  - The app itself is installable to `INSTALLED_APPS` as `"{name}"`.

### Prerequisites

#### Use the docker-compose container (recommended)

- You'll need to make sure other users (the docker container user), can write to the repo root directory. Run `chmod o+w .`
- Run `docker compose run --rm shell bash` to get a clean sandbox environment

#### Use on your host system

- Install `xmlsec` native libraries for your OS: https://xmlsec.readthedocs.io/en/stable/install.html
- Install `rye` following the instructions at https://rye.astral.sh/


### Usage

We use [`rye`](https://rye.astral.sh/) to manage apps and releases.

Useful commands:
```shell
# run all tests
rye test
# run only common app tests
rye test -p mitol-django-common

# build a package
rye build -p mitol-django-common

# format code (isort + black)
rye fmt

# run lints
rye lint

# run django management scripts
rye run tests/manage.py -- ARGS
# run a django shell
rye run tests/manage.py -- shell  
# create migrations
rye run tests/manage.py -- makemigrations  
# run a django migrate
rye run tests/manage.py -- migrate  
```

### Migrations

To generate migrations for a reusable app, run the standard:

```
rye run tests/manage.py -- makemigrations APP_NAME --name MIGRATION_NAME
```

where `APP_NAME` matches the `name` attribute from your `apps.py` app.

#### Adding a new app

- Create the project:
```shell
NAME="[APP-NAME]"
mkdir src/mitol/$NAME
pants run :django-admin -- startapp $NAME src/mitol/$NAME
```
- Add a `BUILD` file, following using the same files from other projects as a guideline
- Add the project as a dependency in `src/BUILD`
- Add the project to the testapp
  - Add the project app in `tests/testapp/settings/shared.py` under `INSTALLED_APPS`
