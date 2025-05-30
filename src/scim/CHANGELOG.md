# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses date-based versioning.

<!-- scriv-insert-here -->

<a id='changelog-2025.5.30'></a>
## [2025.5.30] - 2025-05-30

### Fixed

- Fixed status code handling for batch operations
- Fixed email case sensitivity issue with scim sync

<a id='changelog-2025.5.23'></a>
## [2025.5.23] - 2025-05-23

### Added

- Added functionality for syncing users from the application to another SCIM
  endpoint (e.g. Keycloak).

### Changed

- The SCIM adapter now sets `User.global_id`.

<a id='changelog-2025.3.31'></a>
## [2025.3.31] - 2025-03-31

### Added

- Add the mitol-django-scim app

- Added a minimum version for pyparsing.
