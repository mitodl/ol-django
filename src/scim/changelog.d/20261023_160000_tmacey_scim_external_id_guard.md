### Added

- `UserAdapter.set_external_id()` applies an inbound `externalId`. It refuses
  with a 409 (`scimType: mutability`) when a PUT would change an existing
  user's non-empty `global_id` to a different value. `global_id` is what SSO
  logs a user in by, so a client that resolved the wrong user (e.g. through a
  stale email) would otherwise hand that account to another identity. A PUT
  carrying the user's own id, or binding a user that has no `global_id` yet,
  applies as before. Subclasses that override `from_dict()` should call it.

### Changed

- A PUT that would change an existing user's non-empty `global_id` to a
  different value now returns 409 instead of applying.

- A PATCH `add` of `externalId` now goes through `set_external_id()`, so it
  also sets `global_id` and gets the same 409 guard as a PUT.
