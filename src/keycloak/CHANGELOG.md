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

- Declare `certifi>=2026.10.19` as a direct dependency. certifi below that
  release still trusts the eMudhra root CAs whose intermediate private keys
  are publicly recoverable ([GHSA-6q48-6c7w-9gw2][advisory]). certifi arrives
  here transitively, and a transitive dependency carries no floor of its own,
  so without this declaration a consumer of this package can resolve a
  vulnerable certifi.

[advisory]: https://github.com/advisories/GHSA-6q48-6c7w-9gw2

<a id='changelog-2026.7.14'></a>
## [2026.7.14] - 2026-07-14

### Fixed

- Fixed `UserAttributes.email_optin` serializing to a raw boolean instead of the int (0/1) Keycloak expects.

<a id='changelog-2026.7.13'></a>
## [2026.7.13] - 2026-07-13

### Added

- Added the initial implementation of `mitol-django-keycloak`.
