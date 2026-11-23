### Added

- `create_scim_token` management command: creates or refreshes the django-oauth-toolkit access token a SCIM client (e.g. scim-for-keycloak's remote provider) sends as its bearer token, owned by a staff service account with no usable password. The account's email is `<username local part>@scim.invalid`, which marks it as a service account. Running it again with the same token value refreshes its scope and expiry instead of adding a row; without a token value it generates one and prints it. It refuses a `--username` that belongs to a person (an email outside `@scim.invalid`, a usable password, a past login, an SSO `global_id`, or inactive), a username whose service email another user already has, and a token value already issued to another user or OAuth application. `django-oauth-toolkit>=3.0` is now a declared dependency, since the SCIM views already authenticate through its access tokens.

### Changed

- `sync_users_to_scim_remote` (and so `scim_sync`) skips users whose email is under `@scim.invalid`. Syncing a service account would create a Keycloak user for it and write that user's id into its `global_id`, after which `create_scim_token` refuses to refresh its token.
