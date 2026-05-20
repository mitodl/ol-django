from django.conf import settings
from mitol.keycloak.constants import READONLY_USER_ATTRIBUTES, REQUIRED_CLIENT_SETTINGS
from mitol.keycloak.data_models import UserAttributes

from keycloak import KeycloakAdmin
from keycloak.openid_connection import KeycloakOpenIDConnection


def get_admin_client() -> KeycloakAdmin:
    connection = KeycloakOpenIDConnection(
        server_url=settings.MITOL_KEYCLOAK_BASE_URL,
        realm_name=settings.MITOL_KEYCLOAK_REALM_NAME,
        client_id=settings.MITOL_KEYCLOAK_ADMIN_CLIENT_ID,
        client_secret_key=settings.MITOL_KEYCLOAK_ADMIN_CLIENT_SECRET,
    )
    return KeycloakAdmin(connection=connection)


def is_admin_client_configured() -> bool:
    """
    Return True if the admin client is configured
    """
    client = get_admin_client()

    for prop in REQUIRED_CLIENT_SETTINGS:
        if getattr(client, prop, None) is None:
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

    payload["attributes"].update(attributes.model_dump(exclude_none=True))

    client.update_user(uuid, payload)
