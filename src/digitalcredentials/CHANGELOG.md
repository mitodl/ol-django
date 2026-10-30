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
- Converted all 3 admin registrations from `admin.site.register(Model, ModelAdmin)` to the `@admin.register(Model)` decorator. No behaviour change.

- Declare `certifi>=2026.10.19` as a direct dependency. certifi below that
  release still trusts the eMudhra root CAs whose intermediate private keys
  are publicly recoverable ([GHSA-6q48-6c7w-9gw2][advisory]). certifi arrives
  here transitively, and a transitive dependency carries no floor of its own,
  so without this declaration a consumer of this package can resolve a
  vulnerable certifi.

[advisory]: https://github.com/advisories/GHSA-6q48-6c7w-9gw2

### Fixed

- Restored the distribution name to `mitol-django-digital-credentials`. It was
  changed to `mitol-django-digitalcredentials` during the Pants-to-Rye
  migration, and because PEP 503 normalization does not collapse that hyphen
  the two names are different PyPI projects. The renamed project was never
  created, so every release since 2023-12-19 failed silently while version tags
  continued to be pushed. Install the package as
  `mitol-django-digital-credentials`.

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

<a id='changelog-2023.12.19'></a>
## [2023.12.19] - 2023-12-19

### Changed

- Updated changelog management and versioning scheme.

- Updated requirements and lockfiles to support Django 4.
- Removed support for Django 2.2.

## [3.3.0] - 2023-01-17

## [3.2.1] - 2022-10-31

## [3.2.0] - 2022-06-24

## [3.1.0] - 2022-05-12

### Changed
- Bump `mitol-django-common` to `2.2.0`.

## [3.0.1] - 2021-11-16

## [3.0.0] - 2021-11-04

### Changed

- Support newer versions of `factory_boy`

### Added
- Support for Python 3.9

### Changed

- Allowed for a wider range of dependency versions

### Removed
- Support for Python 3.6

## [2.0.0] - 2021-06-01

## [1.4.1] - 2021-03-23

## [1.4.0] - 2021-03-22

- Added `mitol.digitalcredentials.mixinxs.DigitalCredentialsRequestViewSetMixin` DRF view mixin

## [1.3.0] - 2021-02-09

### Changed

- Made all settings optional instead of required

## [1.2.0] - 2021-02-08

### Changed

- Narrowed oauth scope requirements for credential endpoint to not require read/write scopes.

## [1.1.0] - 2021-01-21

### Changed
- Updated `mitol-django-common` to `0.4.0`

### Added
- Support Django 3.x

## [1.0.0] - 2020-12-08
### Changed
- Renamed generic relation `courseware_object` to `credentialed_object` on `mitol.digitalcredentials.models.DigitalCredentialRequest`
- Renamed generic relation `courseware_object` to `credentialed_object` on `mitol.digitalcredentials.models.DigitalCredential`

## [0.3.0] - 2020-11-19

### Added
- Added boilerplate settings/environment variable parsing as `mitol.digitalcredentials.settings`

### Changed
- `mitol.digitalcredentials.apps.DigitalCredentialsApp` now validates required settings

## [0.2.0] - 2020-11-16

### Changed
- Changed minimum `djangorestframework` requirement from 3.10 to 3.9 to allow for `djoser` compatibility

## [0.1.0] - 2020-11-16

### Added
- Added HMAC Signature + Digest Headers support
- Added `mitol-django-digital-credentials` app
