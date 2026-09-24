# Matches python-keycloak's own default, so upgrading to a version of this
# package that honours MITOL_KEYCLOAK_ADMIN_TIMEOUT changes nothing until an app
# lowers it.
DEFAULT_ADMIN_TIMEOUT = 60

READONLY_USER_ATTRIBUTES = (
    "userProfileMetadata",
    "access",
    "notBefore",
    "totp",
    "disableableCredentialTypes",
    "requiredActions",
    "createdTimestamp",
)
REQUIRED_CLIENT_SETTINGS = (
    "server_url",
    "realm_name",
    "client_id",
    "client_secret_key",
)
