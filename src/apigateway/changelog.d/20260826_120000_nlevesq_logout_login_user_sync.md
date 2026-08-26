### Changed

- `ApiGatewayLogoutView` is now based on `mitol.authentication.views.LogoutRedirectView` (requires a matching `mitol-django-authentication` release, now a declared dependency). It logs the user out of Django, preserves the `next` URL across the gateway/Keycloak hop via the `logout-next` cookie (`MITOL_APIGATEWAY_LOGOUT_NEXT_URL_COOKIE_NAME`/`_TTL`), and deletes the cookie after use.
- `MITOL_APIGATEWAY_LOGOUT_URL` default changed from `/logout` to `/logout/oidc`, matching how deployments configure APISIX's `logout_path` and avoiding a redirect loop with the app-owned `/logout` route.
- The package URL module now serves anchored `/logout` and `/login` routes; the new `ApiGatewayLoginView` handles post-login redirects (reading the middleware-written login cookie) and exposes onboarding hooks via `mitol.authentication.views.LoginRedirectView`.
- The middleware's next-URL cookie is now settings-driven (`MITOL_APIGATEWAY_LOGIN_NEXT_URL_COOKIE_NAME`/`_TTL`, gated by `MITOL_APIGATEWAY_SET_NEXT_COOKIE`) and sets `secure` from the request.
- Authenticated requests whose session already matches the gateway header no longer go through a logout/login cycle each request: the session key is kept, `last_login` only changes on real logins, and with `MITOL_APIGATEWAY_USERINFO_UPDATE` off no auth work runs at all.
- User sync is dirty-checked: users and `additional_models` rows are only saved when a mapped value actually changed, using `save(update_fields=...)` (including `updated_on` when the model has it). Header keys absent from the userinfo payload no longer overwrite fields with `None`.
- `ApisixRemoteUserBackend` reads `MITOL_APIGATEWAY_USER_LOOKUP_FIELD`, `MITOL_APIGATEWAY_USERINFO_CREATE`, and `MITOL_APIGATEWAY_USERINFO_UPDATE` at call time instead of import time, so overrides and test fixtures take effect.
- Newly created gateway users get an unusable password and `is_active=True`.

### Added

- `MITOL_APIGATEWAY_USERINFO_EMAIL_FALLBACK` (default `False`): match users whose lookup field is unset (NULL or `""`) by email, backfilling the lookup field on first match; ambiguous matches fail closed. The email header field is configurable via `MITOL_APIGATEWAY_USERINFO_EMAIL_FIELD`.
- `MITOL_APIGATEWAY_USERINFO_SYNC_HOOKS`: dotted-path callables invoked after a user is created or synced (inside the sync transaction), for project-specific side effects like profile sync or analytics events.
- The default userinfo map now includes `given_name`/`family_name` -> `first_name`/`last_name`.
- `has_gateway_auth()` utility returning whether the request carries the gateway userinfo header.

### Removed

- `MITOL_APIGATEWAY_DEFAULT_POST_LOGOUT_DEST` and `MITOL_APIGATEWAY_ALLOWED_REDIRECT_HOSTS`: replaced by `MITOL_DEFAULT_POST_LOGOUT_URL` and `MITOL_ALLOWED_REDIRECT_HOSTS` from `mitol.authentication.settings.auth` (re-exported by this package's settings module). Update any env vars using the old names.
- `MITOL_APIGATEWAY_HEADER_NAME` (short-lived duplicate of `MITOL_APIGATEWAY_USERINFO_HEADER_NAME`).
