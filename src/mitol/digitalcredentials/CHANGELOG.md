# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/mitodl/ol-django/compare/mitol-django-digitalcredentials/v3.2.1...HEAD
[3.2.1]: https://github.com/mitodl/ol-django/compare/mitol-django-digitalcredentials/v3.2.0...mitol-django-digitalcredentials/v3.2.1
[3.2.0]: https://github.com/mitodl/ol-django/compare/mitol-django-digitalcredentials/v3.1.0...mitol-django-digitalcredentials/v3.2.0
[3.1.0]: https://github.com/mitodl/ol-django/compare/mitol-django-digitalcredentials/v3.0.1...mitol-django-digitalcredentials/v3.1.0
[3.0.1]: https://github.com/mitodl/ol-django/compare/mitol-django-digitalcredentials/v3.0.0...mitol-django-digitalcredentials/v3.0.1
[3.0.0]: https://github.com/mitodl/ol-django/compare/mitol-django-digitalcredentials/v2.0.0...mitol-django-digitalcredentials/v3.0.0
[2.0.0]: https://github.com/mitodl/ol-django/compare/mitol-django-digital-credentials/v0.1.0...mitol-django-digital-credentials/v2.0.0
[1.4.1]: https://github.com/mitodl/ol-django/compare/mitol-django-digital-credentials/v0.1.0...mitol-django-digital-credentials/v1.4.1
[1.4.0]: https://github.com/mitodl/ol-django/compare/mitol-django-digital-credentials/v0.1.0...mitol-django-digital-credentials/v1.4.0
[1.3.0]: https://github.com/mitodl/ol-django/compare/mitol-django-digital-credentials/v0.1.0...mitol-django-digital-credentials/v1.3.0
[1.2.0]: https://github.com/mitodl/ol-django/compare/mitol-django-digital-credentials/v0.1.0...mitol-django-digital-credentials/v1.2.0
[1.1.0]: https://github.com/mitodl/ol-django/compare/mitol-django-digital-credentials/v0.1.0...mitol-django-digital-credentials/v1.1.0
[1.0.0]: https://github.com/mitodl/ol-django/compare/mitol-django-digital-credentials/v0.1.0...mitol-django-digital-credentials/v1.0.0
[0.3.0]: https://github.com/mitodl/ol-django/compare/mitol-django-digital-credentials/v0.1.0...mitol-django-digital-credentials/v0.3.0
[0.2.0]: https://github.com/mitodl/ol-django/compare/mitol-django-digital-credentials/v0.1.0...mitol-django-digital-credentials/v0.2.0
[0.1.0]: https://github.com/mitodl/ol-django/compare/ffca0142e4bfea14881047d3af168bd4aa32f6fa...mitol-django-digital-credentials/v0.1.0
