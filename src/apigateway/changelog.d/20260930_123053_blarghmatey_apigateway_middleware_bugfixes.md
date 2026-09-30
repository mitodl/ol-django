### Fixed

- A userinfo header that isn't base64-encoded JSON, or that decodes to something other than a JSON object, is now logged as a warning and treated as a missing header. It used to raise out of the middleware as a 500.
- `ApisixRemoteUserBackend` now looks users up on `MITOL_APIGATEWAY_USER_LOOKUP_FIELD` instead of a hardcoded `global_id`, including when `MITOL_APIGATEWAY_USERINFO_CREATE` is off (it used `get_by_natural_key`, which matched the gateway ID against `USERNAME_FIELD`). `get_username_from_userinfo_header` honors the setting too.
- `ApisixRemoteUserBackend` reads `MITOL_APIGATEWAY_USER_LOOKUP_FIELD`, `MITOL_APIGATEWAY_USERINFO_CREATE` and `MITOL_APIGATEWAY_USERINFO_UPDATE` when it uses them rather than when it is created, so `override_settings` and test fixtures take effect.
- The Channels middleware now resolves the gateway user. The backend read `request.user`, which a Channels scope dict doesn't have, so every websocket connection came through as anonymous.
- `RemoteUserCustomFieldBackend.aauthenticate` delegates to the sync `authenticate()`. It called `aconfigure_user`, which doesn't exist before Django 5.2 and passes `created` positionally, which a keyword-only `configure_user` rejects.
