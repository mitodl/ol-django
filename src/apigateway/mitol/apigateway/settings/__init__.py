"""
Settings for the apigateway app. See the README.md for more detail.

These should be reasonable defaults - override (or pull from env) as necessary.
"""

# Redirect-related settings (MITOL_DEFAULT_POST_LOGOUT_URL,
# MITOL_ALLOWED_REDIRECT_HOSTS, MITOL_NEW_USER_LOGIN_URL) come from the
# authentication package so apps only need to import this module.
from mitol.authentication.settings.auth import *  # noqa: F403

# apigateway configuration

# Disable middleware. For local testing - you can have the middleware in place
# but not use it and use Django's built-in users instead.
MITOL_APIGATEWAY_DISABLE_MIDDLEWARE = False

# The header that contains the user data from the upstream API gateway.
MITOL_APIGATEWAY_USERINFO_HEADER_NAME = "HTTP_X_USERINFO"

# The header that contains the value we want for user ID.
# This should match with USERNAME_FIELD in the user model.
MITOL_APIGATEWAY_USERINFO_ID_FIELD = "sub"

# Maps user data from the upstream API gateway to the user model(s)
MITOL_APIGATEWAY_USERINFO_MODEL_MAP = {
    # Mappings to the user model.
    "user_fields": {
        # Keys are data returned from the API gateway.
        # Values are the user object field name.
        "preferred_username": "username",
        "email": "email",
        "sub": "global_id",
        "name": "name",
        "given_name": "first_name",
        "family_name": "last_name",
    },
    # Additional models to map in.
    # Key is the model name, then a list of tuples of header field name, model
    # field name, and default. The FK for the related user should be "user".
    "additional_models": {
        # Sample:
        # "users.UserProfile": [
        #     ("email_optin", "email_optin", False),  # noqa: ERA001
        #     ("country_code", "country_code", ""),  # noqa: ERA001
        # ],
        # ..then add additional ones here if needed
    },
}

# Set to True to create users that we see but aren't aware of.
# Set to False if you're managing that elsewhere (like with social-auth).
MITOL_APIGATEWAY_USERINFO_CREATE = True

# Set to True to update users we've seen before. If you set this to False, make
# sure there's a backchannel way to update the user data (SCIM, etc) or user
# info will fall out of sync with the IdP pretty quickly.
MITOL_APIGATEWAY_USERINFO_UPDATE = True

# This is the name of the field used to lookup the user
MITOL_APIGATEWAY_USER_LOOKUP_FIELD = "global_id"

# Set to True to also match users whose lookup field is unset (NULL or "") by
# email, backfilling the lookup field on first match. For migrating pre-SSO
# user bases. Fail-closed: an ambiguous match resolves to no user.
MITOL_APIGATEWAY_USERINFO_EMAIL_FALLBACK = False

# The header field to read the email from for the fallback lookup.
MITOL_APIGATEWAY_USERINFO_EMAIL_FIELD = "email"

# Dotted paths to callables invoked after a user is created or synced.
# Signature: hook(*, request, user, decoded_headers, created)
# Hooks run inside the sync transaction and own their own dirty-checking.
MITOL_APIGATEWAY_USERINFO_SYNC_HOOKS = []

# URL configuation

# Set to the URL that APISIX uses for logout (its logout_path).
MITOL_APIGATEWAY_LOGOUT_URL = "/logout/oidc"

# Cookie the middleware writes to preserve the "next" URL across the gateway's
# OIDC login redirect (the gateway drops the query string).
MITOL_APIGATEWAY_LOGIN_NEXT_URL_COOKIE_NAME = "next"
MITOL_APIGATEWAY_LOGIN_NEXT_URL_COOKIE_TTL = 30

# Cookie the logout view writes to preserve the "next" URL across the
# gateway/Keycloak logout hop (the gateway won't pass a redirect URL through).
MITOL_APIGATEWAY_LOGOUT_NEXT_URL_COOKIE_NAME = "logout-next"
MITOL_APIGATEWAY_LOGOUT_NEXT_URL_COOKIE_TTL = 60

# Set to False to stop the middleware from writing the login next-URL cookie.
MITOL_APIGATEWAY_SET_NEXT_COOKIE = True
