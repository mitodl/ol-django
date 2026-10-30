# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses date-based versioning.

<!-- scriv-insert-here -->

<a id='changelog-2026.10.30'></a>
## [2026.10.30] - 2026-10-30

### Removed

- Removed the `default_app_config` module attribute. Django deprecated it in 3.2 and dropped support in 4.1, so it has been dead for every version this package now supports.

### Changed

- Updated linter directives to handle new checks

- Raised the minimum supported Django to 4.2. The previous `django>=3.0` had not been true for some time: CI's lowest matrix leg is already 4.2, and the last 3.x release (3.2 LTS) reached end-of-life in April 2024.
- Converted the admin registration from `admin.site.register(Model, ModelAdmin)` to the `@admin.register(Model)` decorator. No behaviour change.

- Declare `certifi>=2026.10.19` as a direct dependency. certifi below that
  release still trusts the eMudhra root CAs whose intermediate private keys
  are publicly recoverable ([GHSA-6q48-6c7w-9gw2][advisory]). certifi arrives
  here transitively, and a transitive dependency carries no floor of its own,
  so without this declaration a consumer of this package can resolve a
  vulnerable certifi.

[advisory]: https://github.com/advisories/GHSA-6q48-6c7w-9gw2

<a id='changelog-2026.7.9'></a>
## [2026.7.9] - 2026-07-09

### Fixed

- `sync_object_property` no longer attempts to update properties with a read-only definition (e.g. properties created with `hasUniqueValue=True`), which previously raised a 400 `PROPERTY_INVALID` error from Hubspot on re-runs.

<a id='changelog-2026.5.6'></a>
## [2026.5.6] - 2026-05-06

### Removed

- Removed support for Python 3.10

### Added

- Added  support for django version to 5.2
- Add tox and expand gh action test matrix

### Changed

- Removed `pkg_resources.declare_namespace()` from the `mitol` namespace package declaration in favour of implicit namespace packages (PEP 420), eliminating the runtime dependency on `setuptools`/`pkg_resources`.

<a id='changelog-2025.12.18'></a>
## [2025.12.18] - 2025-12-18

### Fixed

- Hubspot Basic API create paramter name

<a id='changelog-2025.9.16'></a>
## [2025.9.16] - 2025-09-16

### Changed

- update dependency hubspot-api-client to v12

<a id='changelog-2025.3.17'></a>
## [2025.3.17] - 2025-03-17

- Support for Python 3.13

### Added

- Handle hubspot contacts with multiple emails

### Changed

- Updated changelog management and versioning scheme.

- Fixed a bug in hubspot error handling when performing upserts

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

### Added

- Handle hubspot contacts with multiple emails

### Changed

- Updated changelog management and versioning scheme.

- Fixed a bug in hubspot error handling when performing upserts

- Updated requirements and lockfiles to support Django 4.
- Removed support for Django 2.2.

<a id='changelog-2023.5.22'></a>
## [2023.5.22] - 2023-05-22

### Added

- Handle hubspot contacts with multiple emails

### Changed

- Updated changelog management and versioning scheme.

- Fixed a bug in hubspot error handling when performing upserts

<a id='changelog-2023.5.10'></a>
## [2023.5.10] - 2023-05-10

### Added

- Handle hubspot contacts with multiple emails

### Changed

- Updated changelog management and versioning scheme.
# [Unreleased]

## [1.0.0] - 2022-07-22

### Added
- Added `mitol.hubspot_api` Hubspot API library.
