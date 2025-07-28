# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses date-based versioning.

<!-- scriv-insert-here -->

<a id='changelog-2025.7.28'></a>
## [2025.7.28] - 2025-07-28

### Fixed

- Updated SCIM user serialization to return lowercase email

<a id='changelog-2025.7.25'></a>
## [2025.7.25] - 2025-07-25

### Fixed

- Added filtering to not deepcopy non-str values on the header dict `request.META`.

- Made searching for users by email case insensitive.

<a id='changelog-2025.7.21'></a>
## [2025.7.21] - 2025-07-21

### Fixed

- Added filtering to not deepcopy non-str values on the header dict `request.META`.

<a id='changelog-2025.6.10.2'></a>
## [2025.6.10.2] - 2025-06-10

### Fixed

- Fixed key name for `--never-synced-only` option.

<a id='changelog-2025.6.10.1'></a>
## [2025.6.10.1] - 2025-06-10

### Fixed

- Removed errant `type=` argument passed to scim_scim arg setup.

<a id='changelog-2025.6.10'></a>
## [2025.6.10] - 2025-06-10

### Added

- Added `--never-synced-only` option to `scim_sync` command.

### Changed

- Renamed `scim_push` command to `scim_sync`.

<a id='changelog-2025.5.30.2'></a>
## [2025.5.30.2] - 2025-05-30

### Fixed

- Address global_id not being updated

<a id='changelog-2025.5.30.1'></a>
## [2025.5.30.1] - 2025-05-30

### Fixed

- Fixed a duplicate user on sync error

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
