### Open Learning Django Apps

This repository is the home of MIT Open Learning's reusable django apps

### Releases

Changelogs are maintained according to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Version tags follow `{package-name}/v{major}.{minor}.{patch}`
To perform a release, run:
- `./pants run build-support/bin/release.py -- --app APP_NAME [--bump-major] [--bump-minor] [--bump-patch] [--version VERSION]`:
  - `APPNAME`: the name of an application directory
  - `VERSION`: a semantic version value
- `git push --tags`

### Navigating this repository

- Django applications follow the naming convention `mitol-django-{name}`, `pip` installable by the same name.
- Within each app, code is implemented under the [implicit namespace](https://www.python.org/dev/peps/pep-0420/) `mitol`
  - Module paths follow the pattern `mitol.{name}`
  - The app itself is installable to `INSTALLED_APPS` as `"{name}"`.

### Prerequisites

- Install `xmlsec` native libraries for your OS: https://xmlsec.readthedocs.io/en/stable/install.html

### Usage

We use [`pants`](https://www.pantsbuild.org/) to manage apps and releases.

**NOTE:** before running any pants commands, it's highly recommended to install and use [`pyenv`](https://github.com/pyenv/pyenv) to manage the python version as system python installs are often modified or broken versions. In particular, you'll probably end up seeing errors from C code from system pythons. If you have hit this issue but already run a pants command, install `pyenv` and then delete your `.pants.d/` directory to clear cached state.

Useful commands:
```shell
# run all tests
./pants test ::
# run only common app tests
./pants test tests/mitol/common:

# format code (isort + black)
./pants fmt ::

# run lints
./pants lint ::

# run django management scripts
./pants run tests/manage.py -- ARGS
# run a django shell
./pants run tests/manage.py -- shell  
# create migrations
./pants run tests/manage.py -- makemigrations  
# run a django migrate
./pants run tests/manage.py -- migrate  
```

### Migrations

To generate migrations for a reusable app, run the standard:

```
./pants run tests/manage.py -- makemigrations APP_NAME --name MIGRATION_NAME
```

where `APP_NAME` matches the `name` attribute from your `apps.py` app.

#### Adding a new app

- Create the project:
```shell
NAME="[APP-NAME]"
mkdir src/mitol/$NAME
./pants run :django-admin -- startapp $NAME src/mitol/$NAME
```
- Add a `BUILD` file, following using the same files from other projects as a guideline
- Add the project as a dependency in `src/BUILD`
- Add the project to the testapp
  - Add the project app in `tests/testapp/settings/shared.py` under `INSTALLED_APPS`
