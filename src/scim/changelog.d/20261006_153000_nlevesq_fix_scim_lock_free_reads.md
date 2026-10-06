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
