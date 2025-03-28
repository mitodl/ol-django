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
