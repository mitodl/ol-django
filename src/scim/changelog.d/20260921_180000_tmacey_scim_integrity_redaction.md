### Fixed

- A SCIM write that failed a database constraint returned the driver's error text in the 409 body. On Postgres that includes the `DETAIL` line, which echoes the colliding key for a unique violation and the entire failing row (email, names, flags, timestamps) for a `NOT NULL` one. `EXPOSE_SCIM_EXCEPTIONS` did not gate it, because `django_scim` casts the error to `django_scim.exceptions.IntegrityError`, which is already a `SCIMException` and so skips the redacting branch in `SCIMView.dispatch`. Writes now answer with a fixed detail string and log the database text at `ERROR` instead. Set `EXPOSE_SCIM_EXCEPTIONS` to `True` to get the old behaviour, which is what that setting means everywhere else.
- An integrity error on `PATCH` was a 500. `django_scim`'s `PatchView` has no `IntegrityError` handling at all, so it reached `dispatch` as an unhandled exception. It is now the same 409 as `POST` and `PUT`, which matters because `scim-for-keycloak` retries a 500 and a payload that violates a constraint never succeeds on a retry.
- `mitol.scim.urls` mounts `django_scim.urls` alongside its own patterns, so `/Groups` was served by the stock `django_scim` view and leaked the same way. It now goes through a `GroupsView` of ours, which also brings group writes under the transaction wrapping that user writes already had. `/Groups/.search` still resolves to `django_scim`'s `GroupSearchView`.

### Changed

- `mitol.scim.views` logs to `mitol.scim.views` rather than to the root logger. The new integrity-error record carries the database text, including whatever user data the driver put in it, and on the root logger a consumer had no way to route or filter it separately.
