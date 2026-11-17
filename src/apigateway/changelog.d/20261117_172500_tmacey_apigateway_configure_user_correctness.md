### Fixed

- `ApisixRemoteUserBackend.configure_user` skips a mapped userinfo key that is absent from the header instead of writing `None` to the field (a `NOT NULL` column raised, which failed the login). On an existing `additional_models` row an absent key now leaves the field alone; its default applies only when the row is created.
- `configure_user` writes the user only when a mapped value differs from what it holds, and then saves only the changed columns plus any `auto_now` timestamp (a full save still happens when a mapped settable property changed). With `MITOL_APIGATEWAY_USERINFO_UPDATE` on it runs on every request, so it used to write the whole row each time and could overwrite concurrent writes to unmapped columns. `additional_models` rows are dirty-checked the same way.
- A user created from the gateway is inserted with its mapped header values, an unusable password and `is_active=True`. It used to be inserted with only the lookup field and filled in afterward, so the row briefly held `username=""`, two concurrent first logins collided on it, and Django counted the empty password as usable.

### Changed

- An unknown gateway identity whose email (matched case-insensitively on the user model's `EMAIL_FIELD`) belongs to an inactive account is refused, logged as `refused_inactive_email_match`, rather than given a new active account. Reactivating or relinking the old account is left to an administrator.
- `RemoteUserCustomFieldBackend` creates users through two new overridable methods, `get_or_create_user()` and `new_user_defaults()`.
