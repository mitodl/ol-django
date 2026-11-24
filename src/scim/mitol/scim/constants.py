"""SCIM constants"""

from django_scim import constants as djs_constants


class SchemaURI(djs_constants.SchemaURI):
    BULK_REQUEST: str = "urn:ietf:params:scim:api:messages:2.0:BulkRequest"
    BULK_RESPONSE: str = "urn:ietf:params:scim:api:messages:2.0:BulkResponse"


SORT_MAPPING = {
    "id": "id",
    "userName": "username",
    "email": "email",
}

VALID_SORTS = SORT_MAPPING.keys()

# Email domain of the service accounts create_scim_token makes, and the marker
# that identifies them. A reserved TLD (RFC 2606), so it never belongs to a
# person; the client sync skips these accounts.
SERVICE_ACCOUNT_EMAIL_DOMAIN = "scim.invalid"


def is_service_account_email(email: str | None) -> bool:
    """Return whether an email marks a create_scim_token service account."""
    return bool(email) and email.lower().endswith(f"@{SERVICE_ACCOUNT_EMAIL_DOMAIN}")
