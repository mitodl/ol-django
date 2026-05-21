# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses date-based versioning.

<!-- scriv-insert-here -->

<a id='changelog-2026.5.21.1'></a>
## [2026.5.21.1] - 2026-05-21

### Removed

- Removed support for Python 3.10

### Added

- Added  support for django version to 5.2
- Add tox and expand gh action test matrix

- `media_convert_job()` and `make_media_convert_job()` now accept an optional `template_path` argument that overrides `settings.TRANSCODE_JOB_TEMPLATE` for a single call. This lets a project dispatch jobs through multiple templates (e.g. landscape vs. portrait pipelines) without mutating settings.

### Changed

- Removed `pkg_resources.declare_namespace()` from the `mitol` namespace package declaration in favour of implicit namespace packages (PEP 420), eliminating the runtime dependency on `setuptools`/`pkg_resources`.

<a id='changelog-2026.5.21'></a>
## [2026.5.21] - 2026-05-21

### Removed

- Removed support for Python 3.10

### Added

- Added  support for django version to 5.2
- Add tox and expand gh action test matrix

### Changed

- Removed `pkg_resources.declare_namespace()` from the `mitol` namespace package declaration in favour of implicit namespace packages (PEP 420), eliminating the runtime dependency on `setuptools`/`pkg_resources`.

<a id='changelog-2025.5.21'></a>
## [2025.5.21] - 2025-05-21

### Changed

- removed exception handling for transcoding app

<a id='changelog-2025.5.9'></a>
## [2025.5.9] - 2025-05-09

### Added

- Added filter for thumbnail groupss

### Changed

- Made boto3 versioning flexible

<a id='changelog-2025.4.23'></a>
## [2025.4.23] - 2025-04-23

### Fixed

- Fixed thumbnail path in s3

<a id='changelog-2025.4.10'></a>
## [2025.4.10] - 2025-04-10

### Fixed

- Fixed the exclude mp4 param for group settings

-->

### Security

- A bullet item for the Security category.

-->

<a id='changelog-2025.4.8'></a>
## [2025.4.8] - 2025-04-09

### Changed

- Updated handling for multiple profiles in transcoding job

- Added handling to exclude file group with hls groups

<a id='changelog-2025.3.17'></a>
## [2025.3.17] - 2025-03-17

- Support for Python 3.13

<a id='changelog-2025.3.12'></a>
## [2025.3.12] - 2025-03-12

### Changed

- Updated boto3 version

### removed

- support for python 3.8 and 3.9.

### added

<a id='changelog-2025.2.25'></a>
## [2025.2.25] - 2025-02-26

### Removed

- Removed unnecessary package `edx-opaque-keys`

### Changed

- Locked `mitol-django-common` @ `2023.12.19`

<a id='changelog-2025.2.22'></a>
## [2025.2.22] - 2025-02-22

### Added

- Added Transcoding App

### Fixed

- Fixed version tags

<a id='changelog-2025.2.21'></a>
## [2025.2.21] - 2025-2-21

### Added

- Added Transcoding App
