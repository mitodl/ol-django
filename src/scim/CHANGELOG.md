# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses date-based versioning.

<!-- scriv-insert-here -->

<a id='changelog-2026.10.9'></a>
## [2026.10.9] - 2026-10-09

### Changed

- Added `ScimLockingMixin`, which both takes the adapter's row lock and opens
  the transaction to hold it in, for one declared set of methods
  (`LOCKING_METHODS`). The two have to move together - a method that locks
  without a transaction raises, and a method that opens a transaction without
  locking pays for one it has no use for - so they are one mixin rather than
  two that can be applied independently. This replaces the four hand-written
  `transaction.atomic()` overrides on `UsersView`.

- Added `lock_free_adapter()`, which derives a non-locking subclass of an
  adapter class. Consumers that build adapters outside a request, and outside
  a transaction, can use it instead of passing `lock_user=False` at each call
  site.

- `InMemoryHttpRequest` now exposes an uppercase `method`, matching the
  invariant a real `HttpRequest` holds (HTTP methods are case-sensitive and
  uppercase, RFC 9110 9.1). `/Bulk` takes the verb straight from the operation
  payload and scim-for-keycloak sends it lowercase, so anything comparing
  `request.method` against a correctly spelled verb silently failed to match.

### Fixed

- SCIM read endpoints returned a 500 instead of a response. `UserAdapter`
  takes a `SELECT ... FOR UPDATE` when it is constructed, but only the
  mutating verbs on `UsersView` ran inside a transaction. `django_scim` builds
  one adapter per serialized object, so `GET /Users`, `GET /Users/<id>` and
  `POST /Users/.search` raised `TransactionManagementError: select_for_update
  cannot be used outside of a transaction` on any deployment that does not set
  `ATOMIC_REQUESTS`. Reads now build a lock-free adapter, which is also what
  they want on the merits - `to_dict()` only reads, and the lock meant
  re-fetching and locking every already-loaded row of a list or `.search`
  page (measured: 9 queries instead of 3 to serialize 5 users).

<a id='changelog-2026.10.6'></a>
## [2026.10.6] - 2026-10-06

### Removed

- Removed the `default_app_config` module attribute. Django deprecated it in 3.2 and dropped support in 4.1, so it has been dead for every version this package now supports.

### Added

- `UserState` now carries `response_body` (the echoed resource on a successful
  Bulk create) and `error` (the operation's error body on failure), so callers
  can verify what was actually stored without making additional API calls.

### Changed

- Added logging of global_id when a user is created/updated.

- SCIM user operations are now performed with a `select_for_update()`.

- **Breaking:** `sync_users_to_scim_remote` now yields `UserState` results as
  a generator instead of returning `None`. It does nothing until iterated -
  existing callers that discarded the return value (e.g.
  `sync_users_to_scim_remote_batch`) must now iterate or drain it (e.g.
  `deque(sync_users_to_scim_remote(users), maxlen=0)`) for the sync to run at
  all. A caller that needs a concrete list should wrap a single, bounded call
  in `list(...)` itself - materializing every `UserState` (each now carrying
  a full response body) for an unbounded `users` list risks exhausting
  memory, which this generator-based API avoids by construction.

- Raised the minimum supported Django to 4.2. The previous `django>=3.0` had not been true for some time: CI's lowest matrix leg is already 4.2, and the last 3.x release (3.2 LTS) reached end-of-life in April 2024.
- Replaced `re_path()` with `path()` where the route was a plain literal. The patterns are equivalent; the remaining `re_path()` entries genuinely need a regex and are untouched.

### Fixed

- `UserState.error` on a failed Bulk operation now holds the nested SCIM
  error body (`operation["response"]`) instead of the entire Bulk operation
  envelope, matching what's documented and what `response_body` already does
  for successful operations.

- `SCIMUser.from_dict` wrote `""` to `global_id` when the payload carried no `externalId`. Now that the field is unique, the second such user would have collided; it writes `None`.
- `sync_all_users_to_scim_remote(never_synced_only=True)` selected never-synced users with `global_id=""`. Most matched anyway through its other `scim_external_id=None` clause, but a user with `global_id` unset and a `scim_external_id` already populated would have stopped matching once unset became `NULL`. It now matches either empty representation of `global_id` directly.

- `UserAdapter`'s nested-path handler is now spelled
  `_handle_replace_nested_path`. It was `_handle_resplace_nested_path` - with
  the letters transposed - so a subclass that overrode it under the spelling
  the name reads never ran: a SCIM PATCH carrying an attribute that subclass
  was meant to handle returned 200 and silently wrote nothing. A subclass
  still matching the old misspelling keeps working and now raises a
  `DeprecationWarning`.

<a id='changelog-2026.4.29'></a>
## [2026.4.29] - 2026-04-29

### Removed

- Removed support for Python 3.10

### Added

- Added  support for django version to 5.2
- Add tox and expand gh action test matrix

### Changed

- Removed `pkg_resources.declare_namespace()` from the `mitol` namespace package declaration in favour of implicit namespace packages (PEP 420), eliminating the runtime dependency on `setuptools`/`pkg_resources`.

<a id='changelog-2025.7.29'></a>
## [2025.7.29] - 2025-07-29

### Fixed

- Batched up search requests to avoid timeouts (pagination wasn't enough).

<a id='changelog-2025.7.28'></a>
## [2025.7.28] - 2025-07-28

### Fixed

- Updated SCIM user serialization to return lowercase email

<a id='changelog-2025.7.25'></a>
## [2025.7.25] - 2025-07-25

### Fixed

- Added filtering to not deepcopy non-str values on the header dict `request.META`.

- Made searching for users by email case insensitive.

<a id='changelog-2025.7.21'></a>
## [2025.7.21] - 2025-07-21

### Fixed

- Added filtering to not deepcopy non-str values on the header dict `request.META`.

<a id='changelog-2025.6.10.2'></a>
## [2025.6.10.2] - 2025-06-10

### Fixed

- Fixed key name for `--never-synced-only` option.

<a id='changelog-2025.6.10.1'></a>
## [2025.6.10.1] - 2025-06-10

### Fixed

- Removed errant `type=` argument passed to scim_scim arg setup.

<a id='changelog-2025.6.10'></a>
## [2025.6.10] - 2025-06-10

### Added

- Added `--never-synced-only` option to `scim_sync` command.

### Changed

- Renamed `scim_push` command to `scim_sync`.

<a id='changelog-2025.5.30.2'></a>
## [2025.5.30.2] - 2025-05-30

### Fixed

- Address global_id not being updated

<a id='changelog-2025.5.30.1'></a>
## [2025.5.30.1] - 2025-05-30

### Fixed

- Fixed a duplicate user on sync error

<a id='changelog-2025.5.30'></a>
## [2025.5.30] - 2025-05-30

### Fixed

- Fixed status code handling for batch operations
- Fixed email case sensitivity issue with scim sync

<a id='changelog-2025.5.23'></a>
## [2025.5.23] - 2025-05-23

### Added

- Added functionality for syncing users from the application to another SCIM
  endpoint (e.g. Keycloak).

### Changed

- The SCIM adapter now sets `User.global_id`.

<a id='changelog-2025.3.31'></a>
## [2025.3.31] - 2025-03-31

### Added

- Add the mitol-django-scim app

- Added a minimum version for pyparsing.
