from mitol.common.envs import get_bool, get_string

MITOL_KEYCLOAK_BASE_URL = get_string(
    name="MITOL_KEYCLOAK_BASE_URL",
    default="http://mit-keycloak-base-url.edu",
    description="Base URL for the Keycloak instance.",
)

MITOL_KEYCLOAK_REALM_NAME = get_string(
    name="MITOL_KEYCLOAK_REALM_NAME",
    default="olapps",
    description="Name of the realm the app uses in Keycloak.",
)

MITOL_KEYCLOAK_CLIENT_ID = get_string(
    name="MITOL_KEYCLOAK_CLIENT_ID",
    default=None,
    description="The client name for mitxonline.",
)

MITOL_KEYCLOAK_CLIENT_SECRET = get_string(
    name="MITOL_KEYCLOAK_CLIENT_SECRET",
    default=None,
    description="The client secret for mitxonline.",
)

MITOL_KEYCLOAK_DISCOVERY_URL = get_string(
    name="MITOL_KEYCLOAK_DISCOVERY_URL",
    default=None,
    description="The OpenID discovery URL for the Keycloak realm.",
)

MITOL_KEYCLOAK_ADMIN_CLIENT_ID = get_string(
    name="MITOL_KEYCLOAK_ADMIN_CLIENT_ID",
    default=None,
    description="The client name for the admin client.",
)

MITOL_KEYCLOAK_ADMIN_CLIENT_SECRET = get_string(
    name="MITOL_KEYCLOAK_ADMIN_CLIENT_SECRET",
    default=None,
    description="The client secret for the admin client.",
)

MITOL_KEYCLOAK_ADMIN_CLIENT_SCOPES = get_string(
    name="MITOL_KEYCLOAK_ADMIN_CLIENT_SCOPES",
    default=None,
    description="The OpenID scopes to use for the admin client.",
)

MITOL_KEYCLOAK_ADMIN_CLIENT_NO_VERIFY_SSL = get_bool(
    name="MITOL_KEYCLOAK_ADMIN_CLIENT_NO_VERIFY_SSL",
    default=False,
    description="If true, do not verify SSL certificates for the admin client.",
)
