### Changed

- Moved into the ol-django monorepo from mitodl/edx-api-client, whose history stays in that repository. The PyPI name `edx-api-client`, the `edx_api` import path, semantic versioning and the AGPL-3.0 license are unchanged.
- Packaged with hatchling instead of setuptools, and declared `requires-python = ">=3.11"`.

### Removed

- The tests and their JSON fixtures no longer ship inside the package; they live in `tests/edx_api_client` in ol-django.
