### Added

- `mitol.authentication.views.auth`: `AuthRedirectView` (param/cookie-driven redirects with allowed-host validation and cookie cleanup), `LoginRedirectView` (post-login redirect with overridable onboarding hooks: `is_first_login`, `should_skip_onboarding`, `get_onboarding_url`, `handle_first_login`), and `LogoutRedirectView` (Django logout + redirect). All are exported from `mitol.authentication.views`.
- `mitol.authentication.urls.auth`: anchored `/login` and `/logout` routes. Include either this module or `mitol.apigateway.urls` - not both.
- `mitol.authentication.settings.auth`: env-wired `MITOL_DEFAULT_POST_LOGOUT_URL` (default `/app`), `MITOL_ALLOWED_REDIRECT_HOSTS` (default `[]`), and `MITOL_NEW_USER_LOGIN_URL` (default empty = onboarding disabled).
- `mitol.authentication.utils.get_redirect_url` for extracting a validated redirect URL from request params/cookies.

### Fixed

- Removed the duplicate `mitol-django-common` dependency declaration.
