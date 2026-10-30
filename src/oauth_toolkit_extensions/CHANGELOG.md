# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses date-based versioning.

<!-- scriv-insert-here -->

<a id='changelog-2026.10.30'></a>
## [2026.10.30] - 2026-10-30

### Removed

- Removed support for Python 3.10

- Removed the `default_app_config` module attribute. Django deprecated it in 3.2 and dropped support in 4.1, so it has been dead for every version this package now supports.

### Added

- Added  support for django version to 5.2
- Add tox and expand gh action test matrix

### Changed

- Removed `pkg_resources.declare_namespace()` from the `mitol` namespace package declaration in favour of implicit namespace packages (PEP 420), eliminating the runtime dependency on `setuptools`/`pkg_resources`.

- Raised the minimum supported Django to 4.2. The previous `django>=3.0` had not been true for some time: CI's lowest matrix leg is already 4.2, and the last 3.x release (3.2 LTS) reached end-of-life in April 2024.

- Declare `certifi>=2026.10.19` as a direct dependency. certifi below that
  release still trusts the eMudhra root CAs whose intermediate private keys
  are publicly recoverable ([GHSA-6q48-6c7w-9gw2][advisory]). certifi arrives
  here transitively, and a transitive dependency carries no floor of its own,
  so without this declaration a consumer of this package can resolve a
  vulnerable certifi.

[advisory]: https://github.com/advisories/GHSA-6q48-6c7w-9gw2

<a id='changelog-2025.3.17'></a>
## [2025.3.17] - 2025-03-17

- Support for Python 3.13

### Changed

- Updated changelog management and versioning scheme.

- Updated requirements and lockfiles to support Django 4.
- Removed support for Django 2.2.

- Added posthog application.

- Update paths in pyproject.toml to ensure versioning continues to work.

- Removes unnecessary noqa's.

### added

### removed

- support for python 3.8 and 3.9.

<a id='changelog-2023.12.19.1'></a>
## [2023.12.19.1] - 2023-12-19

### Changed

- Updated changelog management and versioning scheme.

- Updated requirements and lockfiles to support Django 4.
- Removed support for Django 2.2.

<a id='changelog-2023.12.19'></a>
## [2023.12.19] - 2023-12-19

### Changed

- Updated changelog management and versioning scheme.

- Updated requirements and lockfiles to support Django 4.
- Removed support for Django 2.2.

## [1.3.0] - 2023-01-17

## [1.2.1] - 2022-10-31

## [1.2.0] - 2022-06-24

## [1.1.0] - 2022-05-12

### Changed
- Bump `mitol-django-common` to `2.2.0`.

## [1.0.1] - 2021-11-16

## [1.0.0] - 2021-11-04

### Added
- Support for Python 3.9

### Changed

- Allowed for a wider range of dependency versions

### Removed
- Support for Python 3.6

## [0.1.0] - 2021-01-21

### Added

- Added initial implementation of `mitol-django-oauth-toolkit-extensions` library

[Unreleased]: https://github.com/mitodl/ol-django/compare/mitol-django-oauth-toolkit-extensions/v1.3.0...HEAD
[1.3.0]: https://github.com/mitodl/ol-django/compare/mitol-django-oauth-toolkit-extensions/v1.2.1...mitol-django-oauth-toolkit-extensions/v1.3.0
[1.2.1]: https://github.com/mitodl/ol-django/compare/mitol-django-oauth-toolkit-extensions/v1.2.0...mitol-django-oauth-toolkit-extensions/v1.2.1
[1.2.0]: https://github.com/mitodl/ol-django/compare/mitol-django-oauth-toolkit-extensions/v1.1.0...mitol-django-oauth-toolkit-extensions/v1.2.0
[1.1.0]: https://github.com/mitodl/ol-django/compare/mitol-django-oauth-toolkit-extensions/v1.0.1...mitol-django-oauth-toolkit-extensions/v1.1.0
[1.0.1]: https://github.com/mitodl/ol-django/compare/mitol-django-oauth-toolkit-extensions/v1.0.0...mitol-django-oauth-toolkit-extensions/v1.0.1
[1.0.0]: https://github.com/mitodl/ol-django/compare/mitol-django-oauth-toolkit-extensions/v0.1.0...mitol-django-oauth-toolkit-extensions/v1.0.0
[0.1.0]: https://github.com/mitodl/ol-django/compare/ffca0142e4bfea14881047d3af168bd4aa32f6fa...mitol-django-oauth-toolkit-extensions/v0.1.0
