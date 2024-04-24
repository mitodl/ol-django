python_requirements(
    name="reqs",
    source="build-support/requirements/requirements.txt",
    module_mapping={
        "cybersource-rest-client-python": ["CyberSource"],
        "django-anymail": ["anymail"],
        "django-oauth-toolkit": ["oauth2_provider"],
        "django-webpack-loader": ["webpack_loader"],
        "edx-opaque-keys": ["opaque_keys"],
        "factory-boy": ["factory"],
        "GitPython": ["git"],
        "google-api-python-client": ["googleapiclient"],
        "google-auth": ["google.auth", "google.oauth2"],
        "google-auth-oauthlib": ["google_auth_oauthlib"],
        "hubspot-api-client": ["hubspot"],
        "psycopg2-binary": ["psycopg2"],
        "pytest-lazy-fixture": ["pytest_lazyfixture"],
        "python3-saml": ["onelogin"],
        "social-auth-app-django": ["social_django"],
        "named-enum": ["enum"],
        "setuptools": ["pkg_resources"],
        "olposthog": ["olposthog"]
    }
)

python_requirements(
    name="reqs-testing",
    source="build-support/requirements/requirements-testing.txt",
    module_mapping={
        "factory-boy": ["factory"],
        "pytest-lazy-fixture": ["pytest_lazyfixture"],
        "setuptools": ["pkg_resources"],
    },
)

python_requirements(
    name="reqs-build-support",
    source="build-support/requirements/requirements-build-support.txt",
    module_mapping={
        "GitPython": ["git"],
        "setuptools": ["pkg_resources"],
    },
)


resources(
    name="license",
    sources=["LICENSE"],
)

pex_binary(name="django-admin", dependencies=["//:reqs#django"], script="django-admin")
