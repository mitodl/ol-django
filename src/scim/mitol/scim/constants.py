"""SCIM constants"""


class SchemaURI:
    BULK_REQUEST = "urn:ietf:params:scim:api:messages:2.0:BulkRequest"

    BULK_RESPONSE = "urn:ietf:params:scim:api:messages:2.0:BulkResponse"


SORT_MAPPING = {
    "id": "id",
    "userName": "username",
    "email": "email",
}

VALID_SORTS = SORT_MAPPING.keys()
