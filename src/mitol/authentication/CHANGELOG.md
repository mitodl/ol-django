# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses date-based versioning.

<!-- scriv-insert-here -->

## [1.6.0] - 2023-01-17

## [1.5.1] - 2022-10-31

## [1.5.0] - 2022-06-24

## [1.4.1] - 2022-05-16

## [1.4.0] - 2022-05-12

### Changed
- Bump `mitol-django-common` to `2.2.0`.

## [1.3.1] - 2021-11-16

## [1.3.0] - 2021-10-28

### Added
- Added custom `djoser` views and emails for password and email resets

## [1.2.0] - 2021-07-01

### Changed

- Support newer versions of `factory_boy`

### Added
- Support for Python 3.9

### Changed

- Allowed for a wider range of dependency versions

### Removed
- Support for Python 3.6

## [1.1.0] - 2021-04-07

### Changed
- Added usage of `SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_NAME` to `SOCIAL_AUTH_SAML_ENABLED_IDPS`

## [1.0.0] - 2021-03-31

### Changed
- Bumped `mitol-django-mail` to `^1.0.0`

## [0.7.0] - 2021-03-30

### Changed
- Bumped `mitol-django-common` requirement to `~0.7.0`

## [0.6.0] - 2021-03-29

### Added
- Support django 3.x

## [0.5.0] - 2021-03-29
### Fixed
- App configuration import error fixed

## [0.4.0] - 2021-03-29
### Fixed
- Fix app configuration w/ namespace packages

## [0.3.0] - 2021-03-29

### Fixed
- Don't install test/dev dependencies

## [0.2.0] - 2021-03-29

### Added
- Barebones implementation of authentication app
- SAML metadata endpoint and boilerplate configuration