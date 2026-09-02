# apigateway: Support for APISIX Remote User Authentication

The `apigateway` app provides some common code for building in support for external authentication for OL applications that sit behind an API Gateway.

Applications that sit behind an API gateway (such as APISIX) need to be able to pull the authenticated user from headers that the gateway attaches to the request. For some apps, this also includes updating or creating the user object in the application.

The app accomplishes this with a set of API functions to parse the user data from the headers, an authentication backend that handles managing the user record, and a middleware that authenticates the user based on the header data.

The backend and middleware build upon existing Django classes. They should also work in sychrnonous (WSGI) and asynchronous (ASGI) modes. Separate middleware is included for use with Django Channels.

**The goal of apigateway is to lift authentication out of your Django app, and allow APISIX to manage it.** While your app will still maintain a session, it doesn't need to use it to handle authenticated user data. (Depending on how the app is structured, you could potentially not maintain a session at all.)

## Prerequisites

Your app will need to sit behind an APISIX gateway, with routes configured for OIDC authentication. You can find examples of this in the Learn, Learn AI, and Unified Ecommerce apps.

### APISIX Configuration/Routing

APISIX maintains its own routing configuration to determine what should service an incoming request. These routes can be configured to match various URI paths and hostnames, and can use any number of APISIX plugins to manipulate the request, including handling authentication.

Setting this up correctly is critical to making your app work properly using `apigateway`. Read through the `README-routing.md` for details and an example APISIX routing configuration.

### App Configuration

The `apigateway` app needs to be added to the `INSTALLED_APPS` in your Django project:

```python
INSTALLED_APPS = [
    ...
    "mitol.apigateway.apps.ApigatewayApp",
]
```

Then, add the backend and the middleware:

```python
# You may need to add authentication backends as-is

AUTHENTICATION_BACKENDS = [
    "mitol.apigateway.backends.ApisixRemoteUserBackend",
]

# Make sure the middleware goes after SessionMiddleware and AuthenticationMiddleware.

MIDDLEWARE = [
    ...
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    ...
    "mitol.apigateway.middleware.ApisixUserMiddleware",
    ...
]
```

> There is also a PersistentApisixUserMiddleware, which fulfills the same role as PersistentRemoteUserMiddleware. The difference is only that the Persistent version won't log the user out if the APISIX header disappears.

Finally, import the settings:

```python
# in your project's settings.py
from mitol.common.envs import import_settings_modules

import_settings_modules(globals(), "mitol.apigateway.settings")
```

### User Model Configuration

OL applications have standardized on adding a field called `global_id` to the `User` model to store the immutable ID that Keycloak generates for the user. This requires two things:

- Your app must have a custom user model so that the `global_id` field can be added.
- Your app's user model should specify `global_id` as the `USERNAME_FIELD` - otherwise, the base Django RemoteUserBackend won't be able to find the user.

You can use other fields, but you probably shouldn't. The immutable ID in Keycloak is the "Subscriber" field (sub) and it's a UUID that Keycloak generates when the user registers their account.

### Channels Configuration

If your app uses Django Channels, read the `README-channels.md` for additional considerations and setup. This is especially true if your app is _only_ Channels, or if that's the main way people access the app.

## Setup

Your application configuration will need some settings added to it. Reasonable defaults are provided in the settings that are included with the app; you should include that and then just change the things you need.

These settings are needed for your environment:

- `MITOL_APIGATEWAY_LOGOUT_URL` - the URL that APISIX uses for logout. This needs to be set in your APISIX configuration; the corresponding setting is `logout_path`. Defaults to `/logout/oidc`.
- `MITOL_DEFAULT_POST_LOGOUT_URL` - the URL that the logout view should send users when they log out by default. (You can programmatically set a destination but you should also have a default.) Defaults to `/app`. Env-configurable; provided by `mitol.authentication.settings.auth`, which this app's settings module re-exports.
- `MITOL_ALLOWED_REDIRECT_HOSTS` - hosts that `next` redirect URLs are allowed to point at. Relative URLs are always allowed. Defaults to `[]`. Env-configurable (as a Python list literal).
- `MITOL_NEW_USER_LOGIN_URL` - URL of the new-user onboarding flow used by the login view. Empty (the default) disables the onboarding redirect.

These settings are likely to need adjustment for your environment:

- `MITOL_APIGATEWAY_USERINFO_CREATE` - controls if the backend will create _new_ users or not. If set to False, users will have to be pre-created within the system before they can be authenticated.
- `MITOL_APIGATEWAY_USERINFO_UPDATE` - controls if the backend will update _existing_ users or not.
- `MITOL_APIGATEWAY_USERINFO_EMAIL_FALLBACK` - if True, users whose lookup field is unset (NULL or `""`) can also be matched by email; the lookup field is backfilled on first match. Use this when migrating a pre-SSO user base. Ambiguous matches fail closed (the request stays anonymous). Defaults to False.
- `MITOL_APIGATEWAY_USERINFO_SYNC_HOOKS` - a list of dotted import paths of callables invoked after a user is created or synced. Each is called as `hook(request=..., user=..., decoded_headers=..., created=...)`, inside the sync transaction (an exception rolls the whole sync back and the request stays anonymous). Use this for project-specific side effects - profile syncing, analytics events, welcome emails - without adding dependencies to this package. Hooks should do their own dirty-checking. Defaults to `[]`.

These settings are unlikely to need adjustment:

- `MITOL_APIGATEWAY_USERINFO_HEADER_NAME` - the name of the header the API gateway will use to attach user data to the request. For APISIX's `openid-connect` plugin, this will be `HTTP_X_USERINFO` and it isn't changeable (at time of writing). **This should be formatted as it will be after Django normalizes the header names.**
- `MITOL_APIGATEWAY_USERINFO_ID_FIELD` - the name of the field to use to identify the user. This will depend on your SSO provider; for Keycloak, this is usually `sub`. You should use whatever immutable ID is available for this - email and username are not good choices unless there's no other option.
- `MITOL_APIGATEWAY_USERINFO_EMAIL_FIELD` - the userinfo field to read the email from for the email fallback lookup. Defaults to `email`.
- `MITOL_APIGATEWAY_LOGIN_NEXT_URL_COOKIE_NAME` / `MITOL_APIGATEWAY_LOGIN_NEXT_URL_COOKIE_TTL` - the short-lived cookie the middleware writes so a `?next=` param survives the gateway's OIDC login redirect (which drops the query string). Defaults: `next`, 30 seconds. Disable the write entirely with `MITOL_APIGATEWAY_SET_NEXT_COOKIE = False`.
- `MITOL_APIGATEWAY_LOGOUT_NEXT_URL_COOKIE_NAME` / `MITOL_APIGATEWAY_LOGOUT_NEXT_URL_COOKIE_TTL` - the short-lived cookie the logout view writes so a `?next=` param survives the gateway/Keycloak logout hop. Defaults: `logout-next`, 60 seconds.


> ### Account management considerations
>
> The _tl;dr_: if your app's user database gets populated through a back-channel (for example, via SCIM), you can set the `CREATE_USER` and `UPDATE_USER` options to `False`. If it doesn't, then set them both to `True`.
>
> Remote users are matched to users in the app database based on the `ID_FIELD` setting above. If the middleware can't find the user, it can optionally create a new user. You may want to turn this off if the application syncs the user database with the identity provider in some way (e.g. SCIM) or if users have to be vetted through some other means. This does mean that users will either be denied access to the system or will be unrecognized (and thus anonymous) until their accounts are created.
>
> When an existing user is matched to the remote user, the backend can update the user's data with what has been attached to the request. This is an easy way to keep your user database up to date. However, if you have a process that manages that for you, you may want to turn this off to prevent potential conflicts. (But be warned: if you do turn this off, you should make sure to configure the back-channel update process or your userdata will fall out of sync quickly.)

_If you've turned on user creation or update_, you should additionally check the field mappings. The fields present in the user info attached to the request are often not a 1-to-1 map to what's in your `User` model, so the backend uses a setting that contains a map between the userinfo field and the `User` model field. This mapping is in `MITOL_APIGATEWAY_USERINFO_MODEL_MAP`.

The `MITOL_APIGATEWAY_USERINFO_MODEL_MAP` is a dict with two root keys:

- `user_fields`: Maps data into the user model. Contains a dict.
   - Keys are the userinfo field name and values are the target user model field.
   - Ex: `{ "preferred_username": "username", }` maps the `preferred_username` field from your IdP to the `username` field in the user model.
- `additional_models`: Maps additional data into related models. These will be `update_or_create`d when the user data is updated. Contains a dict.
   - Keys are the model name (like you'd specify a foreign key without directly importing the model class). E.g.: `users.UserProfile`
   - Values are a list of tuples that represent the field maps. The tuples should contain `("userinfo_field", "model_field", "default value")`.
   - Defaults can be specified mainly for `CharField` (since setting these `null=True` is not recommended).
   - The target model's reference to the user model should be called `user`.

## Using

At its core, this is the `RemoteUserMiddleware` that comes with Django, so you can use any of the normal methods to control access to routes or retrieve user information. The authenticated user will be attached to the request as per usual.

A request whose session already belongs to the user in the gateway header is a no-op for authentication: the session is not cycled, `last_login` is not rewritten, and (when `MITOL_APIGATEWAY_USERINFO_UPDATE` is on) the user sync is dirty-checked so nothing is saved unless a mapped value actually changed.

### Logging Out and User Sessions

By default, if the user's APISIX session disappears, it will stop putting the userinfo header in the request. When this happens, the middleware will log the user out. Your application should handle this gracefully.

If the user wishes to log out explictly, you'll need to set up a logout view that's within your application. It is important _not_ to send the user to the APISIX logout URL (configured with `logout_path`) directly. Instead, use `ApiGatewayLogoutView`. This view explicitly logs the user out of their Django session, and checks to see if the user has an active APISIX session as well. It will send the user through the APISIX logout if there's an APISIX session. At the end, it will send the user to a URL defined either in the query string, a cookie, or in the settings.

The check for an APISIX session is important - APISIX will _always_ send the user through SSO to log them out in the identity provider, even if they don't have a session to log out. Keycloak will raise an error message if you try to log out with no active session.

Include `mitol.apigateway.urls` in your `urlconf` to get `/logout` (`ApiGatewayLogoutView`) and `/login` (`ApiGatewayLoginView`) routes named `logout` and `login`. The app owns `/login` and `/logout`; APISIX owns the `logout_path` (`/logout/oidc` by default) and never routes it to Django. Don't also include `mitol.authentication.urls.auth` - the apigateway views subsume those.

#### Next-URL cookies

Two short-lived cookies carry the `next` URL across gateway redirects that would otherwise drop it:

- The **login cookie** (`MITOL_APIGATEWAY_LOGIN_NEXT_URL_COOKIE_NAME`, default `next`) is written by the middleware whenever a request carries a `?next=` param, and read by `ApiGatewayLoginView` after the OIDC login bounce.
- The **logout cookie** (`MITOL_APIGATEWAY_LOGOUT_NEXT_URL_COOKIE_NAME`, default `logout-next`) is written by `ApiGatewayLogoutView` before it bounces the user through the gateway logout, and read by the same view on the return hop (when the userinfo header is gone).

Both views delete the cookie they consumed on the redirect response.

#### Login and onboarding

`ApiGatewayLoginView` is a plain redirect out of the box. To route first-time logins through an onboarding flow, set `MITOL_NEW_USER_LOGIN_URL` and subclass the view, overriding the hooks from `mitol.authentication.views.LoginRedirectView`:

```python
class MyLoginView(ApiGatewayLoginView):
    def is_first_login(self, request):
        return not request.user.profile.has_logged_in

    def handle_first_login(self, request):
        request.user.profile.has_logged_in = True
        request.user.profile.save()
```

The view honors `?signup_next=` (falling back to `?next=`) for the post-onboarding destination and `?skip_onboarding=1` to bypass the onboarding redirect.

> If your app uses Django Channels, make sure to read through the `README-channels.md` too.
