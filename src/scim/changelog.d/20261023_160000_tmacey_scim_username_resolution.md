### Added

- `MITOL_SCIM_USERNAME_FILTER_FIELDS` lists user fields that a `userName`
  filter also matches, case-insensitively, alongside `username`. It defaults to
  empty, so nothing changes unless an app sets it.

  scim-for-keycloak looks up a user it has no stored id for with
  `userName eq "<Keycloak username>"`. When the app's `username` is a different
  value, the lookup finds nobody. The plugin then POSTs a create, the create
  fails on uniqueness with a 409, and the plugin queues the operation to retry
  forever. Setting this to e.g. `scim_username,email` lets the lookup find the
  existing user. If a value matches two users, the response lists both, and the
  plugin rejects it instead of guessing.

  scim-for-keycloak resolves a user this way after a POST returns 409, then
  sends a full PUT. An app that overrides `from_dict()` therefore has to call
  `set_username()` and `set_external_id()` before it turns this on.

- `MITOL_SCIM_USERNAME_UPDATES_USERNAME` (default `true`) controls whether an
  inbound `userName` overwrites an existing user's `username`. When it is
  `false`, PUT and PATCH write `userName` to `scim_username` only. `username`
  is still set from `userName` when a user is created.

- `UserAdapter.set_username()` is now the one place an inbound `userName` is
  applied, from both `from_dict()` and PATCH. Subclasses that override
  `from_dict()` should call it instead of assigning `username` directly. A
  PATCH of `userName` now goes through it even when the subclass's `ATTR_MAP`
  maps `userName`.

- `UserAdapter.set_external_id()` applies an inbound `externalId`. It refuses
  with a 409 (`scimType: mutability`) when a PUT would change an existing
  user's non-empty `global_id` to a different value. `global_id` is what SSO
  logs a user in by, so a client that resolved the wrong user (e.g. through a
  stale email) would otherwise hand that account to another identity. A PUT
  carrying the user's own id, or binding a user that has no `global_id` yet,
  applies as before. Subclasses that override `from_dict()` should call it.

### Changed

- A PATCH of `userName` now also updates `scim_username`, which previously only
  `from_dict()` set.

- A PUT that would change an existing user's non-empty `global_id` to a
  different value now returns 409 instead of applying (see `set_external_id()`).
