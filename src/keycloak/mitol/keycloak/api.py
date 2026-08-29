from django.conf import settings
from mitol.keycloak.constants import (
    DEFAULT_ADMIN_TIMEOUT,
    READONLY_USER_ATTRIBUTES,
    REQUIRED_CLIENT_SETTINGS,
)
from mitol.keycloak.data_models import UserAttributes

from keycloak import KeycloakAdmin
from keycloak.openid_connection import KeycloakOpenIDConnection


def get_admin_client(*, timeout: int | None = None) -> KeycloakAdmin:
    """
    Return a Keycloak admin client built from the configured settings.

    Args:
        timeout: seconds to wait on a request before giving up. Defaults to
            MITOL_KEYCLOAK_ADMIN_TIMEOUT, itself defaulting to
            DEFAULT_ADMIN_TIMEOUT. Callers that reach the Admin API while
            serving a request should keep this well below their own request
            timeout, since python-keycloak's default lets a slow or
            misconfigured Keycloak hold the request open for a full minute.
    """
    if timeout is None:
        # getattr, not settings.X: an app can install this package without
        # pulling in mitol.keycloak.settings.keycloak.
        timeout = getattr(
            settings, "MITOL_KEYCLOAK_ADMIN_TIMEOUT", DEFAULT_ADMIN_TIMEOUT
        )

    connection = KeycloakOpenIDConnection(
        server_url=settings.MITOL_KEYCLOAK_BASE_URL,
        realm_name=settings.MITOL_KEYCLOAK_REALM_NAME,
        client_id=settings.MITOL_KEYCLOAK_ADMIN_CLIENT_ID,
        client_secret_key=settings.MITOL_KEYCLOAK_ADMIN_CLIENT_SECRET,
        verify=not settings.MITOL_KEYCLOAK_ADMIN_CLIENT_NO_VERIFY_SSL,
        timeout=timeout,
    )
    return KeycloakAdmin(connection=connection)


def is_admin_client_configured() -> bool:
    """
    Return True if the admin client is configured
    """
    try:
        client = get_admin_client()
    except ValueError:
        return False

    for prop in REQUIRED_CLIENT_SETTINGS:
        if getattr(client.connection, prop, None) is None:
            return False
    return True


def update_user(uuid: str, *, attributes: UserAttributes):
    """
    Update a user
    """
    client = get_admin_client()

    # Keycloak doesn't support PATCH, instead it only has PUT which overwrites the user
    # with whatever payload we send. So we mimic what would happen in a keycloak admin
    # ui by loading the profile and then updating the attributes.
    payload = client.get_user(uuid)

    for attr in READONLY_USER_ATTRIBUTES:
        payload.pop(attr, None)

    payload.setdefault("attributes", {}).update(
        attributes.model_dump(exclude_none=True)
    )

    client.update_user(uuid, payload)
