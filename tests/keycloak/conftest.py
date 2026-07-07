import pytest


@pytest.fixture
def keycloak_admin_settings(settings):
    """Fixture for a fully configured Keycloak admin client"""
    settings.MITOL_KEYCLOAK_BASE_URL = "http://keycloak.example.com"
    settings.MITOL_KEYCLOAK_REALM_NAME = "test-realm"
    settings.MITOL_KEYCLOAK_ADMIN_CLIENT_ID = "admin-client"
    settings.MITOL_KEYCLOAK_ADMIN_CLIENT_SECRET = "admin-secret"  # noqa: S105
    return settings
