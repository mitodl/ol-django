mitol-django-authentication
---

This is the Open Learning Django Authentication app. It provides a few key features around authentication:

- Password reset via extended [Djoser](https://djoser.readthedocs.io/en/latest/) views
- Login/logout redirect views with validated `next` URL handling

## Redirect views

`mitol.authentication.views` exports three class-based views:

- `AuthRedirectView` - base view that redirects based on a `next` URL taken from GET params and/or cookies, validated against `MITOL_ALLOWED_REDIRECT_HOSTS`, falling back to `MITOL_DEFAULT_POST_LOGOUT_URL`. Cookies it consumes are deleted on the redirect response.
- `LoginRedirectView` - post-login redirect with optional onboarding: when `is_first_login()` returns True for an authenticated user, the user is sent to `MITOL_NEW_USER_LOGIN_URL` with a `next` param (taken from `?signup_next=`, falling back to `?next=`), unless `?skip_onboarding=1` is passed or no onboarding URL is configured. Override the hooks to wire up project behavior:
  - `is_first_login(request)` - defaults to False (plain redirect)
  - `should_skip_onboarding(request)` - defaults to reading `?skip_onboarding`
  - `get_onboarding_url(request)` - defaults to `MITOL_NEW_USER_LOGIN_URL`
  - `handle_first_login(request)` - one-shot side effects (set flags, send a welcome email)
- `LogoutRedirectView` - logs the user out of Django, then redirects like `AuthRedirectView`.

## URLs

`mitol.authentication.urls.auth` provides anchored `/login` and `/logout` routes named `login` and `logout`. Include it only if your app is **not** behind an API gateway; gateway apps should include `mitol.apigateway.urls` instead (its views subsume these). Never include both - the route names collide.

## Settings

Import `mitol.authentication.settings.auth` (apps using `mitol.apigateway.settings` get these transitively):

- `MITOL_DEFAULT_POST_LOGOUT_URL` (env var of the same name, default `/app`) - fallback redirect target.
- `MITOL_ALLOWED_REDIRECT_HOSTS` (env var of the same name, a Python list literal, default `[]`) - hosts absolute `next` URLs may point at; relative URLs are always allowed.
- `MITOL_NEW_USER_LOGIN_URL` (env var of the same name, default empty = disabled) - the onboarding flow URL for first-time logins.

## Djoser settings

Import `mitol.authentication.settings.djoser_settings` and configure `MITOL_AUTHENTICATION_FROM_EMAIL` / `MITOL_AUTHENTICATION_REPLY_TO_ADDRESS` for the password reset emails.
