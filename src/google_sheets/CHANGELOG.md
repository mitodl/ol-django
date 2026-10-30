# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses date-based versioning.

<!-- scriv-insert-here -->

<a id='changelog-2026.10.29'></a>
## [2026.10.29] - 2026-10-29

### Removed

- Removed support for Python 3.10

- Removed the `default_app_config` module attribute. Django deprecated it in 3.2 and dropped support in 4.1, so it has been dead for every version this package now supports.

### Added

- Added  support for django version to 5.2
- Add tox and expand gh action test matrix

### Changed

- Removed `pkg_resources.declare_namespace()` from the `mitol` namespace package declaration in favour of implicit namespace packages (PEP 420), eliminating the runtime dependency on `setuptools`/`pkg_resources`.

- Updated linter directives to handle new checks

- Raised the minimum supported Django to 4.2. The previous `django>=3.0` had not been true for some time: CI's lowest matrix leg is already 4.2, and the last 3.x release (3.2 LTS) reached end-of-life in April 2024.

- Declare `certifi>=2026.10.19` as a direct dependency. certifi below that
  release still trusts the eMudhra root CAs whose intermediate private keys
  are publicly recoverable ([GHSA-6q48-6c7w-9gw2][advisory]). certifi arrives
  here transitively, and a transitive dependency carries no floor of its own,
  so without this declaration a consumer of this package can resolve a
  vulnerable certifi.

[advisory]: https://github.com/advisories/GHSA-6q48-6c7w-9gw2

<a id='changelog-2025.6.13'></a>
## [2025.6.13] - 2025-06-13

### Fixed

- Added a missing default setting for auto-incrementing primary key in app config

<a id='changelog-2025.3.17'></a>
## [2025.3.17] - 2025-03-17

- Support for Python 3.13

<a id='changelog-2025.2.27'></a>
## [2025.2.27] - 2025-02-27

### Changed

- Add a migration to swap in `BigAutoField` for the `filewatchrenewalattempt`, `googleapiauth`, and `googlefilewatch` models.

### removed

- support for python 3.8 and 3.9.

### added

<a id='changelog-2025.2.4'></a>
## [2025.2.4] - 2025-02-04

### Changed

- Update paths in pyproject.toml to ensure versioning continues to work.

- Removes unnecessary noqa's.

- Bumped Google Python API package versions

<a id='changelog-2024.7.3'></a>
## [2024.7.3] - 2024-07-03

### Changed

- Updated README with instructions for setup.

- Updated requirements and lockfiles to support Django 4.
- Removed support for Django 2.2.

- Added posthog application.

<a id='changelog-2023.12.19.1'></a>
## [2023.12.19.1] - 2023-12-19

### Changed

- Updated README with instructions for setup.

- Updated requirements and lockfiles to support Django 4.
- Removed support for Django 2.2.

<a id='changelog-2023.12.19'></a>
## [2023.12.19] - 2023-12-19

### Changed

- Updated README with instructions for setup.

- Updated requirements and lockfiles to support Django 4.
- Removed support for Django 2.2.

## [0.1.0] - 2022-06-22

### Added
- Added `mitol.google_sheets` core Google Sheets library.
- Added the `mitol-django-google-sheets` app
