import json
from http import HTTPStatus
from uuid import uuid4

import pytest
from mitol.keycloak import api
from mitol.keycloak.data_models import UserAttributes
from responses import RequestsMock

from keycloak import KeycloakAdmin


@pytest.mark.usefixtures("keycloak_admin_settings")
def test_get_admin_client():
    """Returns a KeycloakAdmin whose connection reflects the configured settings"""
    client = api.get_admin_client()

    assert isinstance(client, KeycloakAdmin)
    assert client.connection.server_url == "http://keycloak.example.com"
    assert client.connection.realm_name == "test-realm"
    assert client.connection.client_id == "admin-client"
    assert client.connection.client_secret_key == "admin-secret"  # noqa: S105


@pytest.mark.usefixtures("keycloak_admin_settings")
def test_is_admin_client_configured_returns_true():
    """Returns True when all required settings are configured"""
    assert api.is_admin_client_configured() is True


@pytest.mark.parametrize(
    "missing_setting",
    [
        "MITOL_KEYCLOAK_BASE_URL",
        "MITOL_KEYCLOAK_REALM_NAME",
        "MITOL_KEYCLOAK_ADMIN_CLIENT_ID",
        "MITOL_KEYCLOAK_ADMIN_CLIENT_SECRET",
    ],
)
def test_is_admin_client_configured_returns_false_when_missing(
    keycloak_admin_settings, missing_setting
):
    """Returns False when any required connection setting is None"""
    setattr(keycloak_admin_settings, missing_setting, None)

    assert api.is_admin_client_configured() is False


def test_update_user(responses: RequestsMock, settings):
    """Test that update user makes API calls correctly"""
    uuid = uuid4()
    initial = {
        "email": "test@example.com",
        "attributes": {
            "fullName": ["old_name"],
        },
    }

    user_get = responses.add(
        responses.GET,
        f"{settings.MITOL_KEYCLOAK_BASE_URL}/admin/realms/olapps/users/{uuid}?userProfileMetadata=False",
        json=initial,
    )
    user_put = responses.add(
        responses.PUT,
        f"{settings.MITOL_KEYCLOAK_BASE_URL}/admin/realms/olapps/users/{uuid}",
        status=HTTPStatus.NO_CONTENT,
    )

    api.update_user(uuid, attributes=UserAttributes())

    assert user_get.call_count == 1
    assert user_put.call_count == 1
    assert json.loads(user_put.calls[0].request.body) == initial

    api.update_user(uuid, attributes=UserAttributes(full_name="new_name"))

    assert user_get.call_count == 2  # noqa: PLR2004
    assert user_put.call_count == 2  # noqa: PLR2004
    assert json.loads(user_put.calls[1].request.body) == {
        **initial,
        "attributes": {
            **initial["attributes"],
            "fullName": ["new_name"],
        },
    }

    api.update_user(uuid, attributes=UserAttributes(email_optin=True))

    assert user_get.call_count == 3  # noqa: PLR2004
    assert user_put.call_count == 3  # noqa: PLR2004
    assert json.loads(user_put.calls[2].request.body) == {
        **initial,
        "attributes": {
            **initial["attributes"],
            "emailOptIn": [1],
        },
    }

    api.update_user(
        uuid, attributes=UserAttributes(full_name="new_name", email_optin=False)
    )

    assert user_get.call_count == 4  # noqa: PLR2004
    assert user_put.call_count == 4  # noqa: PLR2004
    assert json.loads(user_put.calls[3].request.body) == {
        **initial,
        "attributes": {
            **initial["attributes"],
            "fullName": ["new_name"],
            "emailOptIn": [0],
        },
    }
