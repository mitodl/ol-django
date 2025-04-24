"""
Settings for the apigateway app. See the README.md for more detail.

These should be reasonable defaults - override (or pull from env) as necessary.
"""

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

# URL configuation

# Set to the URL that APISIX uses for logout.
MITOL_APIGATEWAY_LOGOUT_URL = "/logout"

# Set to the default URL the user should be sent to when logging out.
# If there's no redirect URL specified otherwise, the user gets sent here.
MITOL_APIGATEWAY_DEFAULT_POST_LOGOUT_DEST = "/app"

# Set to the list of hosts the app is allowed to redirect to.
MITOL_APIGATEWAY_ALLOWED_REDIRECT_HOSTS = [
    "localhost",
]
