# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/mitodl/ol-django/compare/mitol-django-digital-credentials/v1.0.0...HEAD
[1.0.0]: https://github.com/mitodl/ol-django/compare/mitol-django-digital-credentials/v0.1.0...mitol-django-digital-credentials/v1.0.0
[0.3.0]: https://github.com/mitodl/ol-django/compare/mitol-django-digital-credentials/v0.1.0...mitol-django-digital-credentials/v0.3.0
[0.2.0]: https://github.com/mitodl/ol-django/compare/mitol-django-digital-credentials/v0.1.0...mitol-django-digital-credentials/v0.2.0
[0.1.0]: https://github.com/mitodl/ol-django/compare/ffca0142e4bfea14881047d3af168bd4aa32f6fa...mitol-django-digital-credentials/v0.1.0
