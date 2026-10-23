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

- `MITOL_SCIM_USERNAME_UPDATES_USERNAME` (default `true`) controls whether an
  inbound `userName` overwrites an existing user's `username`. When it is
  `false`, PUT and PATCH write `userName` to `scim_username` only. `username`
  is still set from `userName` when a user is created.

- `UserAdapter.set_username()` is now the one place an inbound `userName` is
  applied, from both `from_dict()` and PATCH. Subclasses that override
  `from_dict()` should call it instead of assigning `username` directly. A
  PATCH of `userName` now goes through it even when the subclass's `ATTR_MAP`
  maps `userName`.

### Changed

- A PATCH of `userName` now also updates `scim_username`, which previously only
  `from_dict()` set.
