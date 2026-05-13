from django.conf import settings
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


def update_user(uuid: str, *, attributes: UserAttributes):
    """
    Update a user
    """
    client = get_admin_client()
    client.update_user(uuid, {attributes: attributes.model_dump(exclude_none=True)})
