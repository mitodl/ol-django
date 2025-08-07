# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses date-based versioning.

<!-- scriv-insert-here -->

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
