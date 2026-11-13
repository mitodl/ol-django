# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses date-based versioning.

<!-- scriv-insert-here -->

<a id='changelog-2026.11.13'></a>
## [2026.11.13] - 2026-11-13

### Changed

- Raised the minimum supported Django to 5.2. Django 4.2 reached end of life on
  2026-04-07, and 5.0 and 5.1 before it (2025-04-02 and 2025-12-03), leaving
  5.2 as the only supported LTS, so the 4.2, 5.0 and 5.1 CI legs are gone.
- `CheckConstraint` now passes `condition=` directly. The version gate that
  chose between `check=` and `condition=` picked `check=` only below Django
  5.1, which a 5.2 floor excludes, so that branch was unreachable. The same
  gate is removed from the historical `0001_add_geoip_tables` migration, which
  produces the identical constraint.

- Added a `default_auto_field` setting to the geoip/apps.py so other apps (mitxonline) will stop trying to make migrations.

<a id='changelog-2026.10.30'></a>
## [2026.10.30] - 2026-10-30

### Removed

- Removed support for Python 3.10

- Removed the `default_app_config` module attribute. Django deprecated it in 3.2 and dropped support in 4.1, so it has been dead for every version this package now supports.

### Changed

- Removed `pkg_resources.declare_namespace()` from the `mitol` namespace package declaration in favour of implicit namespace packages (PEP 420), eliminating the runtime dependency on `setuptools`/`pkg_resources`.

- Raised the minimum supported Django to 4.2. The previous `django>=3.0` had not been true for some time: CI's lowest matrix leg is already 4.2, and the last 3.x release (3.2 LTS) reached end-of-life in April 2024.

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

### added

### removed

- support for python 3.8 and 3.9.

<a id='changelog-2024.11.5'></a>
## [2024.11.5] - 2024-11-05

### Changed

- Removes unnecessary noqa's.

### Fixed

- Adding migrations to rename the maxmind indexes to geoip.

<a id='changelog-2024.10.25'></a>
## [2024.10.25] - 2024-10-25

### Changed

- Updated faker dependency to start at 4.17 (rather than requiring it)
