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

- Updated linter directives to handle new checks

- Raised the minimum supported Django to 4.2. The previous `django>=3.0` had not been true for some time: CI's lowest matrix leg is already 4.2, and the last 3.x release (3.2 LTS) reached end-of-life in April 2024.
- Converted the admin registration from `admin.site.register(Model, ModelAdmin)` to the `@admin.register(Model)` decorator. No behaviour change.

- Require `mitol-django-common>=2026.10.29`, the first release that declares
  the `certifi>=2026.10.19` floor for the eMudhra CA compromise
  ([GHSA-6q48-6c7w-9gw2][advisory]). This package reaches certifi only through
  `mitol-django-common`, so it inherits the floor rather than declaring one of
  its own — but the dependency was previously unpinned, which an older release
  predating the floor would have satisfied.

[advisory]: https://github.com/advisories/GHSA-6q48-6c7w-9gw2

<a id='changelog-2025.3.17'></a>
## [2025.3.17] - 2025-03-17

- Support for Python 3.13

### Added

- Added the `mitol-django-google-sheets-deferrals` app

### added

### removed

- support for python 3.8 and 3.9.

<a id='changelog-2025.2.3'></a>
## [2025.2.3] - 2025-02-03

### Added

- Added the `mitol-django-google-sheets-deferrals` app

- Added implementation of filter_ignored_rows to request handler

- Added DeferralRequestAdmin

### Changed

- Updated release version format

- Set default_auto_field in app config

- Added posthog application.

- Allow for newer pluggy versions than 0.13.1

- Update paths in pyproject.toml to ensure versioning continues to work.

- Removes unnecessary noqa's.

- Updated pluggy dependency (from 0.13 to anything 0.13 up)

<a id='changelog-2023.12.19'></a>
## [2023.12.19] - 2023-12-19

### Added

- Added the `mitol-django-google-sheets-deferrals` app

- Added implementation of filter_ignored_rows to request handler

- Added DeferralRequestAdmin

### Changed

- Updated release version format

- Set default_auto_field in app config

- Updated requirements and lockfiles to support Django 4.
- Removed support for Django 2.2.

<a id='changelog-2023.6.9'></a>
## [2023.6.9] - 2023-06-09

### Added

- Added the `mitol-django-google-sheets-deferrals` app

- Added implementation of filter_ignored_rows to request handler

- Added DeferralRequestAdmin

### Changed

- Updated release version format

- Set default_auto_field in app config

<a id='changelog-2023.5.30'></a>
## [2023.5.30] - 2023-05-30

### Added

- Added the `mitol-django-google-sheets-deferrals` app

- Added implementation of filter_ignored_rows to request handler

### Changed

- Updated release version format

- Set default_auto_field in app config

<a id='changelog-2023.5.25'></a>
## [2023.5.25] - 2023-05-25

### Added

- Added the `mitol-django-google-sheets-deferrals` app

### Changed

- Updated release version format

- Set default_auto_field in app config

<a id='changelog-2023.5.23'></a>
## [2023.5.23] - 2023-05-23

### Added

- Added the `mitol-django-google-sheets-deferrals` app

### Changed

- Updated release version format
