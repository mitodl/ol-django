# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses date-based versioning.

<!-- scriv-insert-here -->

<a id='changelog-2025.8.19'></a>
## [2025.8.19] - 2025-08-19

### Fixed

- Improved username collision detection regex to be more precise and avoid false matches
- Added proper error handling for username suffix extraction in `_find_available_username`

<a id='changelog-2025.8.1'></a>
## [2025.8.1] - 2025-08-01

### Changed

- Updated `django-redis` to version 6.x.

<a id='changelog-2025.6.20'></a>
## [2025.6.20] - 2025-06-20

### Added

username generation functionality:

- usernameify() - Generate usernames from full names with email fallback
- create_user_with_generated_username() - Create users with automatic username collision handling
- _find_available_username() - Handle username conflicts by appending numeric suffixes
- _reformat_for_username() - Clean and format strings for username use
- is_duplicate_username_error() - Detect database integrity errors for username collisions

<a id='changelog-2025.5.23'></a>
## [2025.5.23] - 2025-05-23

### Added

- Added utilies and settings to look up the configured celery app.
- Added a `UserGlobalIdMixin` for a common definition of `global_id` on users.

<a id='changelog-2025.4.2'></a>
## [2025.4.2] - 2025-04-02

### Added

- Added `with_scim` trait to `UserFactory`

<a id='changelog-2025.3.17'></a>
## [2025.3.17] - 2025-03-17

- Support for Python 3.13

### Added

- Added `mitol.common.envs.get_crontab_kwargs` for crontab parsing from environment variables.

### Changed

- Updated changelog management and versioning scheme.

- Updated `pytest` dependency to allow versions `>=7.0.0`.

- Updated requirements and lockfiles to support Django 4.
- Removed support for Django 2.2.

- Added posthog application.

- Update paths in pyproject.toml to ensure versioning continues to work.

- Removes unnecessary noqa's.

### added

### removed

- support for python 3.8 and 3.9.

<a id='changelog-2023.12.19'></a>
## [2023.12.19] - 2023-12-19

### Added

- Added `mitol.common.envs.get_crontab_kwargs` for crontab parsing from environment variables.

### Changed

- Updated changelog management and versioning scheme.

- Updated `pytest` dependency to allow versions `>=7.0.0`.

- Updated requirements and lockfiles to support Django 4.
- Removed support for Django 2.2.

<a id='changelog-2023.6.27.1'></a>
## [2023.6.27.1] - 2023-06-27

### Added

- Added `mitol.common.envs.get_crontab_kwargs` for crontab parsing from environment variables.

### Changed

- Updated changelog management and versioning scheme.

- Updated `pytest` dependency to allow versions `>=7.0.0`.

<a id='changelog-2023.01.17'></a>
## [2023.01.17] - 2023-06-27

### Added

- Added `mitol.common.envs.get_crontab_kwargs` for crontab parsing from environment variables.

### Changed

- Updated changelog management and versioning scheme.

- Updated `pytest` dependency to allow versions `>=7.0.0`.

## [2.7.0] - 2023-01-17

## [2.6.1] - 2023-01-13

## [2.6.0] - 2022-10-28

## [2.5.2] - 2022-08-30

## [2.5.1] - 2022-08-19

## [2.5.0] - 2022-06-24

## [2.4.0] - 2022-06-23

## [2.2.4] - 2022-05-27

### Added

- Added `SingletonModel`

## [2.2.3] - 2022-05-23

### Fixed

- Fixed cache control issue for no cache

## [2.2.2] - 2022-05-19

### Fixed

- Fixed an invalid import


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
