python_requirements(
    module_mapping={
        "django-anymail": ["anymail"],
        "django-oauth-toolkit": ["oauth2_provider"],
        "django-webpack-loader": ["webpack_loader"],
        "factory-boy": ["factory"],
        "GitPython": ["git"],
        "psycopg2-binary": ["psycopg2"],
        "python3-saml": ["onelogin"],
        "social-auth-app-django": ["social_django"],
        "setuptools": ["pkg_resources"],
        "edx-opaque-keys": ["opaque_keys"],
        "google-api-python-client": ["googleapiclient"],
        "pytest-lazy-fixture": ["pytest_lazyfixture"],
        "cybersource-rest-client-python": ["CyberSource"],
    },
)

resources(
    name="license",
    sources=["LICENSE"],
)

pex_binary(
    name="django-admin",
    dependencies=["//:django"],
    script="django-admin"
)