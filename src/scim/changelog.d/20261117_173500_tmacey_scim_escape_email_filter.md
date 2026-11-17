### Fixed

- The client-side sync's search quotes each email in the SCIM filter as a JSON string (RFC 7644 3.4.2.2). An email with a `"` in its local part, which Django's `EmailValidator` accepts, used to end the comparison value early and rewrite the rest of the filter.

### Changed

- Documented why `sync_all_users_to_scim_remote` syncs active users only: a user with no Keycloak match is created in Keycloak, so syncing a retired or merged account would create a Keycloak identity for it.
