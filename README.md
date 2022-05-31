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

### Usage

We use [`pants`](https://www.pantsbuild.org/) to manage apps and releases

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
./pants django-run tests: -- ARGS
# run a django shell
./pants django-run tests: -- shell  
# create migrations
./pants django-run tests: -- makemigrations  
# run a django migrate
./pants django-run tests: -- migrate  
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
cd src/mitol
django-admin startproject NAME && cd $NAME
```
- Remove the default app aside to use as the testapp: `rm -rf $NAME`
- Add a `BUILD` file, following using the same files from other projects as a guideline
- Add the project to the testapp
  - Add the project as a dependency in `tests/BUILD`
  - Add the project app in `tests/testapp/settings/shared.py` under `INSTALLED_APPS`
