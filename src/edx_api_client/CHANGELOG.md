# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses semantic versioning.

<!-- scriv-insert-here -->

<a id='changelog-1.15.0'></a>
## [1.15.0] - 2026-10-29

### Removed

- The tests and their JSON fixtures no longer ship inside the package; they live in `tests/edx_api_client` in ol-django.

### Added

- `EdxApi.enrollments_v2`, a client for `/api/enrollment/v2/`. v2 accepts only JWT or session auth, so it sends the access token under the `JWT` scheme. Its list methods follow v2's page-number pagination, and `get_student_enrollments` takes a `username` and drops inactive enrollments and enrollments in deleted courses unless `include_inactive=True`, which matches what v1 returned. openedx/openedx-platform#39128 deprecates `/api/enrollment/v1/` and removes it one named release after Willow, the first named release that ships v2.

### Changed

- Moved into the ol-django monorepo from mitodl/edx-api-client, whose history stays in that repository. The PyPI name `edx-api-client`, the `edx_api` import path, semantic versioning and the AGPL-3.0 license are unchanged.
- Packaged with hatchling instead of setuptools, and declared `requires-python = ">=3.11"`.
