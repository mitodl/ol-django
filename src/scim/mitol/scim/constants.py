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
