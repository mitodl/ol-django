### Fixed

- `sync_users_to_scim_remote` no longer moves a user to a different Keycloak
  identity. It matches Keycloak users by email and wrote the match's id to
  `global_id` unconditionally, so a stale email could bind the account to
  someone else's Keycloak user (`global_id` is what SSO logs the user in by).
  A result whose id differs from the user's existing `global_id` is now
  returned as an error and the user is left unchanged. A bound user that the
  email search doesn't find is also returned as an error, instead of being
  created again in Keycloak as a second identity.
- A user whose email matches more than one Keycloak user is now one error
  result listing every matching id, and is left unbound. Before, each hit was
  a separate result and whichever Keycloak listed last was written to
  `global_id`. A user already bound to one of the matches keeps that binding,
  and the other ids are logged at `WARNING`.
- A Keycloak id that another user already holds as `global_id` is now an
  error result for the user it would have bound, and that user is left
  unbound. Before, the write broke the unique constraint and the
  `IntegrityError` aborted the rest of the sync.
