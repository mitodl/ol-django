# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses date-based versioning.

<!-- scriv-insert-here -->

<a id='changelog-2026.9.8'></a>
## [2026.9.8] - 2026-09-08

### Removed

- Removed the `default_app_config` module attribute. Django deprecated it in 3.2 and dropped support in 4.1, so it has been dead for every version this package now supports.

### Changed

- `MITOL_APIGATEWAY_USERINFO_CREATE` and `MITOL_APIGATEWAY_USERINFO_UPDATE` are now read from the environment, so they can be configured per-deployment without a settings override.
- **Breaking:** `MITOL_APIGATEWAY_USERINFO_UPDATE` now defaults to `False`. The userinfo the gateway attaches to a request is only refreshed at login, so updating on every request clobbers newer user data written by a backchannel process (SCIM, etc). Apps that rely on the middleware to keep users in sync must now set `MITOL_APIGATEWAY_USERINFO_UPDATE=True` explicitly.

- Raised the minimum supported Django to 4.2. The previous `django>=3.0` had not been true for some time: CI's lowest matrix leg is already 4.2, and the last 3.x release (3.2 LTS) reached end-of-life in April 2024.

### Fixed

- Fixed `ApisixRemoteUserBackend.aauthenticate` always returning `None`: it awaited nothing (missing `await`) and wrapped async ORM calls in a sync `transaction.atomic()`, which raises `SynchronousOnlyOperation` under a real event loop. Now delegates to the tested sync `authenticate()` via `sync_to_async`.

<a id='changelog-2026.4.29'></a>
## [2026.4.29] - 2026-04-29

### Removed

- Removed support for Python 3.10

### Added

- Added  support for django version to 5.2
- Add tox and expand gh action test matrix

### Changed

- Removed `pkg_resources.declare_namespace()` from the `mitol` namespace package declaration in favour of implicit namespace packages (PEP 420), eliminating the runtime dependency on `setuptools`/`pkg_resources`.

<a id='changelog-2025.8.14'></a>
## [2025.8.14] - 2025-08-14

### Changed

- Gateway middleware no longer updates the user on every request. Updates now only occur when `request.user` changes

<a id='changelog-2025.8.7'></a>
## [2025.8.7] - 2025-08-07

### Added

- Added a new `override` flag to configure_user,
allowing to set the flag to 'False' to prevent overriding existing value.

<a id='changelog-2025.4.25.1'></a>
## [2025.4.25.1] - 2025-04-25

### Fixed

- Made authentication for users transactional to avoid incomplete state.

<a id='changelog-2025.4.25'></a>
## [2025.4.25] - 2025-04-25

### Changed

- Switch the backend to lookup the user based off a configurable field,
  defaulting to `global_id`.

<a id='changelog-2025.4.15'></a>
## [2025.4.15] - 2025-04-15

### Added

- Added create_userinfo_header to assist with creating test clients.

<a id='changelog-2025.4.4.1'></a>
## [2025.4.4.1] - 2025-04-04

### Added

- Adds the apigateway app to pull API gateway (APISIX) authentication code into one reusable implementation.

<a id='changelog-2024.10.24'></a>
## [2024.10.24] - 2024-10-24

### Added

- Added this test/template app.
