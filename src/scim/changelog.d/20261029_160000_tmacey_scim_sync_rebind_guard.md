### Fixed

- `sync_users_to_scim_remote` no longer moves a user to a different Keycloak
  identity. It matches Keycloak users by email and wrote the match's id to
  `global_id` unconditionally, so a stale email could bind the account to
  someone else's Keycloak user (`global_id` is what SSO logs the user in by).
  A result whose id differs from the user's existing `global_id` is now
  returned as an error and the user is left unchanged. A bound user that the
  email search doesn't find is also returned as an error, instead of being
  created again in Keycloak as a second identity.
