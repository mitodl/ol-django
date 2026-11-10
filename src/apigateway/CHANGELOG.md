# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses date-based versioning.

<!-- scriv-insert-here -->

<a id='changelog-2026.11.10'></a>
## [2026.11.10] - 2026-11-10

### Changed

- Depends on `mitol-django-common>=2026.10.23`, which provides the `SettingsRef` descriptor the backend flags now use. `mitol.apigateway.settings` already imported `mitol.common.envs` without declaring it.

- Raised the minimum supported Django to 5.2. Django 4.2 reached end of life on
  2026-04-07, and 5.0 and 5.1 before it (2025-04-02 and 2025-12-03), leaving
  5.2 as the only supported LTS, so the 4.2, 5.0 and 5.1 CI legs are gone.

### Fixed

- `decode_x_header` now logs a warning and treats a userinfo header that isn't strictly base64-encoded JSON (characters outside the base64 alphabet are rejected rather than skipped), or that decodes to something other than a JSON object, as missing. It used to raise out of the middleware as a 500. The middleware still sets `REMOTE_USER` to `None` for such a header, so a logged-in session is logged out, even under `PersistentApisixUserMiddleware` (the same as for a header without the ID field).
- `ApisixRemoteUserBackend` now looks users up on `MITOL_APIGATEWAY_USER_LOOKUP_FIELD` instead of a hardcoded `global_id`, including when `MITOL_APIGATEWAY_USERINFO_CREATE` is off (it used `get_by_natural_key`, which matched the gateway ID against `USERNAME_FIELD`). `get_username_from_userinfo_header` honors the setting too.
- `ApisixRemoteUserBackend` reads `MITOL_APIGATEWAY_USER_LOOKUP_FIELD`, `MITOL_APIGATEWAY_USERINFO_CREATE` and `MITOL_APIGATEWAY_USERINFO_UPDATE` when it uses them rather than when it is created, so `override_settings` and test fixtures take effect. Assigning `lookup_field`, `create_unknown_user` or `update_known_user` on a backend instance still overrides the setting for that instance, and deleting it (or leaving a `mock.patch.object` block) falls back to the setting.
- The Channels middleware now resolves the gateway user. The backend read `request.user`, which a Channels scope dict doesn't have, so authentication always failed and the scope user resolved to `None` rather than a user. A header user the backend rejects now resolves to `AnonymousUser` instead of `None`.
- `RemoteUserCustomFieldBackend.aauthenticate` delegates to the sync `authenticate()`. It called `aconfigure_user`, which doesn't exist before Django 5.2 and passes `created` positionally, which a keyword-only `configure_user` rejects.
- `ApisixUserMiddleware` keeps the session when the session user already matches the header on `MITOL_APIGATEWAY_USER_LOOKUP_FIELD`. `RemoteUserMiddleware` compares on `USERNAME_FIELD`, so where the two differ it logged the session out and back in on every request, flushing session data and rotating the session key and CSRF token. The matching user still goes through `authenticate()` on every request, so `configure_user` (and any subclass override of it) keeps running mid-session. With `MITOL_APIGATEWAY_USERINFO_UPDATE` off that costs one `transaction.atomic()` block (a savepoint when nested, `BEGIN`/`COMMIT` otherwise) and no lookup query.
- `ApisixUserMiddleware` works under an async handler. `__call__` treated the coroutine from the async path as a response and failed with an `AttributeError`. It also defines `aprocess_request`, which Django 6.1's `RemoteUserMiddleware` calls instead of an overridden `process_request`.

<a id='changelog-2026.9.8'></a>
## [2026.9.8] - 2026-09-08

### Removed

- Removed the `default_app_config` module attribute. Django deprecated it in 3.2 and dropped support in 4.1, so it has been dead for every version this package now supports.

### Changed

- `MITOL_APIGATEWAY_USERINFO_CREATE` and `MITOL_APIGATEWAY_USERINFO_UPDATE` are now read from the environment, so they can be configured per-deployment without a settings override.
- **Breaking:** `MITOL_APIGATEWAY_USERINFO_UPDATE` now defaults to `False`. The userinfo the gateway attaches to a request is only refreshed at login, so updating on every request clobbers newer user data written by a backchannel process (SCIM, etc). Apps that rely on the middleware to keep users in sync must now set `MITOL_APIGATEWAY_USERINFO_UPDATE=True` explicitly.

- Raised the minimum supported Django to 4.2. The previous `django>=3.0` had not been true for some time: CI's lowest matrix leg is already 4.2, and the last 3.x release (3.2 LTS) reached end-of-life in April 2024.

### Fixed

- Fixed `ApisixRemoteUserBackend.aauthenticate` always returning `None`: it awaited nothing (missing `await`) and wrapped async ORM calls in a sync `transaction.atomic()`, which raises `SynchronousOnlyOperation` under a real event loop. Now delegates to the tested sync `authenticate()` via `sync_to_async`.

<a id='changelog-2026.4.29'></a>
## [2026.4.29] - 2026-04-29

### Removed

- Removed support for Python 3.10

### Added

- Added  support for django version to 5.2
- Add tox and expand gh action test matrix

### Changed

- Removed `pkg_resources.declare_namespace()` from the `mitol` namespace package declaration in favour of implicit namespace packages (PEP 420), eliminating the runtime dependency on `setuptools`/`pkg_resources`.

<a id='changelog-2025.8.14'></a>
## [2025.8.14] - 2025-08-14

### Changed

- Gateway middleware no longer updates the user on every request. Updates now only occur when `request.user` changes

<a id='changelog-2025.8.7'></a>
## [2025.8.7] - 2025-08-07

### Added

- Added a new `override` flag to configure_user,
allowing to set the flag to 'False' to prevent overriding existing value.

<a id='changelog-2025.4.25.1'></a>
## [2025.4.25.1] - 2025-04-25

### Fixed

- Made authentication for users transactional to avoid incomplete state.

<a id='changelog-2025.4.25'></a>
## [2025.4.25] - 2025-04-25

### Changed

- Switch the backend to lookup the user based off a configurable field,
  defaulting to `global_id`.

<a id='changelog-2025.4.15'></a>
## [2025.4.15] - 2025-04-15

### Added

- Added create_userinfo_header to assist with creating test clients.

<a id='changelog-2025.4.4.1'></a>
## [2025.4.4.1] - 2025-04-04

### Added

- Adds the apigateway app to pull API gateway (APISIX) authentication code into one reusable implementation.

<a id='changelog-2024.10.24'></a>
## [2024.10.24] - 2024-10-24

### Added

- Added this test/template app.
