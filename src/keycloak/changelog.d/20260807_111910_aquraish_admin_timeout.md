### Added

- Added `MITOL_KEYCLOAK_ADMIN_TIMEOUT` and a `timeout` argument to `get_admin_client()`, so apps calling the Admin API while serving a request can bound how long a slow Keycloak holds that request. Defaults to python-keycloak's own 60 seconds, so existing behaviour is unchanged.
