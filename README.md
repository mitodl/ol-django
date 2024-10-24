### Open Learning Django Apps

This repository is the home of MIT Open Learning's reusable django apps.

### Getting Started

This set of libraries is managed using [uv](https://docs.astral.sh/uv/).

#### Use on your host system

- Install `xmlsec` native libraries for your OS: https://xmlsec.readthedocs.io/en/stable/install.html
- Install `uv` as described in the manual: https://docs.astral.sh/uv/
- Bootstrap the `uv` environment: `uv python install 3.11 ; uv sync`

> [!WARNING]
> If you're running `uv` locally, any calls to the `build` command will need help.
> Prepend `PYTHONPATH=build-support/bin` to the command so uv will launch it properly.

#### Use the Docker Compose environment (recommended)

The Compose environment includes a container for general use called `shell` and one specifically for building releases called `release`. In either case, you'll get a shell with `uv` already set up, and with a PostgreSQL database available.

- Ensure that 'other' users can write to the repo directory: `chmod -R o+w .` 
- Build the containers: `docker compose build`
- Get a shell in the `shell` container: `docker compose run --rm -ti shell bash`

#### Using the `release` container

The `release` container is special and is set up to run `build` commands, including generating releases. It's special because it _does not_ mount your local copy of the codebase (mainly because of file permission issues). So, it requires a bit more care before using.

**One-time setup:**
1. Copy the SSH private key you use for GitHub to the `ssh` folder and name it appropriately (e.g. `id_ed25519`, etc.)
2. Set permissions on the key so that it is group-readable (`0640`).

**Using:**
1. Build the images, so the source code in the image is up to date: `docker compose build`
2. Get a shell: `docker compose run --rm -ti release bash`
3. Run your command: `uv run build release create etc. etc. etc.`
4. If you've done things that involve Git, make sure you `git pull` when you leave the session.

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
6. Add the app to `testapp/settings/shared.py`
   * You must add it to `INSTALLED_APPS`.
   * If your app has configuration settings, add to the `import_settings_module` call at the top too.

You can now add your code and tests.

If you need to run Django commands, 

### Running tests

Run `uv run pytest`. This should run all the tests. If you want to run a specific one, specify with a file path as per usual. Use the whole path (so `tests/mitol/<appname>/etc`).

### Changelogs

We maintain changelogs in `changelog.d/` directories with each app. To create a new changelog for your changes, run:

- `uv run build changelog create --app APPNAME`
  - `APPNAME`: the name of an application directory

Note warning above about `PYTHONPATH`. You will need to adjust permissions/ownership on the new file if you're using the Compose setup.

Then fill out the new file that was generated with information about your changes. These changes will all be merged down into `CHANGELOG.md` when a release is generated. **Do this before you put up a PR for your changes.**

### Releases

Changelogs are maintained according to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning uses a date-based versioning scheme with incremental builds on the same day.
Version tags follow `{package-name}/v{version}`
To perform a release, run:
- `uv run build release create --app APPNAME --push`:
  - `APPNAME`: the name of an application directory

`release` expects to be run on the `main` branch and it expects you to not have changes pending.

You should probably avoid running this within the `shell` container - Git will be pretty unhappy about the permissions of the `.git` folder and you may run into other permissions issues. Either run this on your local machine or use the `release` container for this as described above. 

Supplying the `--push` flag will tag the release appropriately and push it, and a GitHub action should publish it to PyPI.
