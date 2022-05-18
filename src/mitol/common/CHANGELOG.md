# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.2.1] - 2022-05-18

### Fixed

- Fixed an invalid import

## [2.2.0] - 2022-05-10

### Added

- Added `mitol.common.decorators.cache_control_max_age_jitter`.

## [2.1.0] - 2021-11-12

### Changed

- Added support for `added_attrs` argument for the `render_bundle` template tag.

## [2.0.0] - 2021-07-20

### Changed

- Added a required argument for `globals()` to `init_app_settings`

## [1.2.0] - 2021-06-28

### Changed

- Support newer versions of `factory_boy`

## [1.1.0] - 2021-06-24

### Changed

- Allowed for a wider range of dependency versions

## [1.0.0] - 2021-06-23

### Added
- Support for Python 3.9

### Removed
- Support for Python 3.6

## [0.7.0] - 2021-03-30

### Fixed
- Fixed a bug in `mitol.common.envs.init_app_settings` when `mitol.common.envs.validate` is called

## [0.6.0] - 2021-03-25

### Added
- Added `mitol.common.envs.init_app_settings` to support namespace and site name configuration
- Added `mitol.common.envs.import_settings_modules` to support dynamically importing a set of settings files

## [0.5.0] - 2021-01-29

### Added
- Added `admin.py` class for `TimestampedModel`
- Added more utilities from downstream apps, particularly `mitol.common.utils.webpack`
- Refactored `mitol.common.utils` into a set of smaller subpackages
- Configured `mitol.common.utils` to re-export utils for backwards compatibility (deprecated for the future though)

## [0.4.0] - 2021-01-15

### Added
- Support Django 3.x

## [0.3.0] - 2020-11-19

### Added
- Added `mitol.common.envs` module

## [0.2.0] - 2020-10-21
### Added
- Added `mitol.common.factories.UserFactory` for our apps to have a consistent place to find the user factory

## [0.1.1] - 2020-10-14

### Fixed
- Removed `LICENSE` explicitly added in `pyproject.toml`
- Added `py.typed` marker file per [PEP 561](https://www.python.org/dev/peps/pep-0561/#packaging-type-information)

## [0.1.0] - 2020-10-09

### Added
- Added the `mitol-django-common` app
