### Open Learning Django Apps

This repository is the home of MIT Open Learning's reusable django apps

### Changelogs

We maintain changelogs in `changelog.d/` directories with each app. To create a new changelog for your changes, run:

- `pants ol-project changelog create --app APPNAME`
  - `APPNAME`: the name of an application directory

Then fill out the new file that was generated with information about your changes. These changes will all be merged down into `CHANGELOG.md` when a release is generated.

### Releases

Changelogs are maintained according to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning uses a date-based versioning scheme with incremental builds on the same day.
Version tags follow `{package-name}/v{version`
To perform a release, run:
- `pants ol-project release create --app APPNAME --push`:
  - `APPNAME`: the name of an application directory

### Navigating this repository

- Django applications follow the naming convention `mitol-django-{name}`, `pip` installable by the same name.
- Within each app, code is implemented under the [implicit namespace](https://www.python.org/dev/peps/pep-0420/) `mitol`
  - Module paths follow the pattern `mitol.{name}`
  - The app itself is installable to `INSTALLED_APPS` as `"{name}"`.

### Prerequisites

#### Use the docker-compose container (recommended)

- Run `docker compose run --rm shell bash` to get a clean sandbox environment

#### Use on your host system

- Install `xmlsec` native libraries for your OS: https://xmlsec.readthedocs.io/en/stable/install.html
- Install `pants` (this is actually `scie-pants`, a context-aware wrapper script that bootstraps the correct `pants` version and its depenencies):
  - Use their installer script: https://www.pantsbuild.org/docs/installation
  - Alternatively, if you don't want to pipe a script from the internet directly into `bash`, you can download the latest release of `scie-pants` for your os/arch and put it somewhere on your `PATH` (the installer script puts it in `~/bin`): https://github.com/pantsbuild/scie-pants/releases


### Usage

We use [`pants`](https://www.pantsbuild.org/) to manage apps and releases.

**NOTE:** before running any pants commands, it's highly recommended to install and use [`pyenv`](https://github.com/pyenv/pyenv) to manage the python version as system python installs are often modified or broken versions. In particular, you'll probably end up seeing errors from C code from system pythons. If you have hit this issue but already run a pants command, install `pyenv` and then delete your `.pants.d/` directory to clear cached state.

Useful commands:
```shell
# run all tests
pants test ::
# run only common app tests
pants test tests/mitol/common:

# format code (isort + black)
pants fmt ::

# run lints
pants lint ::

# run django management scripts
pants run tests/manage.py -- ARGS
# run a django shell
pants run tests/manage.py -- shell  
# create migrations
pants run tests/manage.py -- makemigrations  
# run a django migrate
pants run tests/manage.py -- migrate  
```

### Migrations

To generate migrations for a reusable app, run the standard:

```
pants run tests/manage.py -- makemigrations APP_NAME --name MIGRATION_NAME
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
