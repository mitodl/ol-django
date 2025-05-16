from mitol.common.envs import get_int, get_string

MITOL_SCIM_REQUESTS_TIMEOUT_SECONDS = get_int(
    name="MITOL_SCIM_REQUESTS_TIMEOUT_SECONDS",
    default=60,
    description="Number of seconds to timeout requests to Keycloak",
)
MITOL_SCIM_KEYCLOAK_BATCH_SIZE = get_int(
    name="MITOL_SCIM_KEYCLOAK_BATCH_SIZE",
    default=250,
    description="Number of operations to send in a single batch request",
)

MITOL_SCIM_KEYCLOAK_BULK_OPERATIONS_COUNT = get_int(
    name="MITOL_SCIM_KEYCLOAK_BULK_OPERATIONS_COUNT",
    default=250,
    description="Number of operations to perform per bulk request",
    required=True,
)

MITOL_SCIM_KEYCLOAK_CLIENT_ID = get_string(
    name="MITOL_SCIM_KEYCLOAK_CLIENT_ID",
    description="The client id for the Keycloak service",
)
MITOL_SCIM_KEYCLOAK_CLIENT_SECRET = get_string(
    name="MITOL_SCIM_KEYCLOAK_CLIENT_SECRET",
    description="The client secret for the Keycloak service",
)

MITOL_SCIM_KEYCLOAK_BASE_URL = get_string(
    name="MITOL_SCIM_KEYCLOAK_BASE_URL",
    description="The base url for the upstream Keycloak service",
)

SCIM_SERVICE_PROVIDER = {
    "SCHEME": "https",
    # use default value,
    # this will be overridden by value returned by BASE_LOCATION_GETTER
    "NETLOC": "localhost",
    "AUTHENTICATION_SCHEMES": [
        {
            "type": "oauth2",
            "name": "OAuth 2",
            "description": "Oauth 2 implemented with bearer token",
            "specUri": "",
            "documentationUri": "",
        },
    ],
    "SERVICE_PROVIDER_CONFIG_MODEL": "mitol.scim.config.LearnSCIMServiceProviderConfig",
    "USER_ADAPTER": "mitol.scim.adapters.UserAdapter",
    "USER_MODEL_GETTER": "mitol.scim.adapters.get_user_model_for_scim",
    "USER_FILTER_PARSER": "mitol.scim.filters.UserFilterQuery",
    "GET_IS_AUTHENTICATED_PREDICATE": "mitol.scim.utils.is_authenticated_predicate",
}
