"""
Hubspot CRM API utilities

https://developers.hubspot.com/docs/api/overview
"""
import json
import logging
import re
from enum import Enum
from typing import Dict, Iterable, List

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from hubspot import HubSpot
from hubspot.crm.objects import (
    ApiException,
    PublicObjectSearchRequest,
    SimplePublicObject,
    SimplePublicObjectInput,
)
from hubspot.crm.properties import ApiException as PropertiesApiException
from urllib3 import Retry

from mitol.common.utils.collections import replace_null_values
from mitol.hubspot_api.models import HubspotObject

log = logging.getLogger()

HUBSPOT_EXISTING_ID = r"Existing ID:\s*(\d+)|(\d+) already has that value"


class HubspotObjectType(Enum):
    """Enum of possible row results"""

    CONTACTS = "contacts"
    DEALS = "deals"
    LINES = "line_items"
    PRODUCTS = "products"
    PROPERTIES = "properties"


class HubspotAssociationType(Enum):
    """Enum of hubspot_api associations"""

    DEAL_CONTACT = "deal_to_contact"
    LINE_DEAL = "line_item_to_deal"
    DEAL_LINE = "deal_to_line_item"


HUBSPOT_TYPE_ID_MAPPING = {
    HubspotObjectType.CONTACTS.value: "contact_id",
    HubspotObjectType.DEALS.value: "deal_id",
    HubspotObjectType.LINES.value: "line_id",
    HubspotObjectType.PRODUCTS.value: "product_id",
    HubspotObjectType.PROPERTIES.value: "property_id",
}

HUBSPOT_MAX_BATCH_SIZE = {
    HubspotObjectType.CONTACTS.value: 10,
    HubspotObjectType.DEALS.value: 100,
    HubspotObjectType.LINES.value: 100,
    HubspotObjectType.PRODUCTS.value: 100,
}


class HubspotApi(HubSpot):
    """Hubspot API Client"""

    def __init__(
        self,
        access_token=settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN,
        retry: Retry = None,
        **kwargs,
    ):
        """Set an authenticated client"""
        if not retry:
            # Use some default retry settings
            retry = Retry(
                total=settings.MITOL_HUBSPOT_API_RETRIES,
                backoff_factor=0.3,
                status_forcelist=(429, 500, 502, 504),
            )
        super().__init__(access_token=access_token, retry=retry, **kwargs)


def create_filter(name: str, operator: str, value: str or int) -> dict:
    """
    Return a filter dict for use in hubspot api searches

    name(str): The hubspot object propertyName
    operator(str): api filter operater (like 'EQ')
    value(str): The hubspot object property's value

    Returns:
        dict: The search filter
    """
    return {"propertyName": name, "operator": operator, "value": value}


def get_all_objects(
    object_type: str, limit: int = 100, **kwargs
) -> Iterable[SimplePublicObject]:
    """
    Yield objects instead of returning all at once like client.crm.objects.get_all does

    Args:
        object_type(str): The hubspot_api object type (deals, products, etc)
        limit(int): The number of results to return per page/request (max 100)

    Yields:
        iterable[SimplePublicObject]: Hubspot objects of the specified type
    """
    after = None
    basic_api = HubspotApi().crm.objects.basic_api
    while True:
        page = basic_api.get_page(object_type, after=after, limit=limit, **kwargs)
        for result in page.results:
            yield result
        if page.paging is None:
            break
        after = page.paging.next.after


def get_hubspot_id(object_id: int, content_type: ContentType) -> str:
    """
    Return the hubspot_api id if any for an object w/the specified id and content type

    Args:
        object_id(int): Django id for the object
        content_type(ContentType): the content type of the object

    Returns:
        str: The Hubspot id
    """
    hubspot_obj = HubspotObject.objects.filter(
        object_id=object_id, content_type=content_type
    ).first()
    if hubspot_obj:
        return hubspot_obj.hubspot_id


def format_app_id(object_id: int) -> str:
    """
    Return a formatted custom app-object ID for an object
    Args:
        object_id(int): The object id

    Returns:
        str: The hubspot_api id
    """
    return "{}-{}".format(settings.MITOL_HUBSPOT_API_ID_PREFIX, object_id)


def upsert_object_request(
    content_type: ContentType,
    hubspot_type: str,
    object_id: int = None,
    body: SimplePublicObjectInput = None,
    ignore_conflict=False,
) -> SimplePublicObject:
    """
    Update or create an object in Hubspot via the CRM API

     Args:
        content_type(ContentType): The object content type
        hubspot_type(str): The hubspot_api type (deals, contacts, etc)
        object_id(int): The database id of the object
        body(SimplePublicObjectInput): The properties of the object to set in Hubspot
        ignore_conflict(bool): If true, a conflict error on create will be retried as an update

    Returns:
        SimplePublicObject: The Hubspot object returned from the API
    """
    hubspot_id = get_hubspot_id(object_id, content_type)
    api = HubspotApi().crm.objects.basic_api
    if hubspot_id:
        result = api.update(
            simple_public_object_input=body,
            object_id=hubspot_id,
            object_type=hubspot_type,
        )
    else:
        try:
            result = api.create(
                simple_public_object_input=body, object_type=hubspot_type
            )
        except ApiException as err:  # pylint:disable=broad-except
            # Handle cases where an object already exists but hubspot_id is not in db (redo as a PATCH)
            if err.status in (400, 409):
                details = json.loads(err.body)
                message = details.get("message", "")
                hubspot_id_matches = [
                    match
                    for match in list(sum(re.findall(HUBSPOT_EXISTING_ID, message), ()))
                    if match
                ]
                if hubspot_id_matches:
                    hubspot_id = hubspot_id_matches[0]
                    if object_id and not ignore_conflict:
                        HubspotObject.objects.update_or_create(
                            object_id=object_id,
                            content_type=content_type,
                            hubspot_id=hubspot_id,
                        )
                        return upsert_object_request(
                            content_type, hubspot_type, object_id=object_id, body=body
                        )
                    elif ignore_conflict:
                        return SimplePublicObject(id=hubspot_id)
            raise
    if object_id and not hubspot_id:
        HubspotObject.objects.update_or_create(
            object_id=object_id, content_type=content_type, hubspot_id=result.id
        )
    return result


def associate_objects_request(
    from_type: str, from_id: str, to_type: str, to_id: str, assoc_type: str
) -> SimplePublicObject:
    """
    Make an association between two objects

    Args:
        from_type(str): The hubspot_api object type to associate from
        from_id(str): The hubspot_api id of the object to associate from
        to_type(str): The hubspot_api object type to associate to
        to_id(str): The hubspot_api id of the object to associate to
        assoc_type(str): The type of association (HubspotAssociationType)

    Returns:
        SimplePublicObject: The Hubspot association object returned from the API
    """
    return HubspotApi().crm.objects.associations_api.create(
        from_type, from_id, to_type, to_id, assoc_type
    )


def make_object_properties_message(properties: dict) -> SimplePublicObjectInput:
    """
    Create data for object sync message

    Args:
        properties (dict): dict of properties to be synced

    Returns:
        SimplePublicObjectInput: input object to create/update data in Hubspot
    """
    return SimplePublicObjectInput(properties=replace_null_values(properties, ""))


def transform_object_properties(object_data: dict, mapping: dict) -> dict:
    """
    Replace model attribute names with hubspot_api property names, skip any that don't match


    Args:
        object_data (dict): serialized object data
        mapping (dict): key-value pairs of serializer to hubspot_api field names

    Returns:
        dict:  object data with hubspot_api keys


    """
    hubspot_dict = {}
    for key in object_data.keys():
        value = object_data.get(key)
        hubspot_key = mapping.get(key)
        if hubspot_key:
            hubspot_dict[hubspot_key] = value
    return hubspot_dict


def sync_object_property(object_type: str, property_dict: str) -> SimplePublicObject:
    """
    Create or update a new object property


    Args:
        object_type (str): The object type of the property (ie "deals")
        property_dict (dict): The attributes of the property

    Returns:
        SimplePublicObject:  the created/updated object returned from Hubspot
    """
    required_fields = {"name", "label", "groupName"}

    missing_fields = required_fields.difference(property_dict.keys())
    if missing_fields:
        raise KeyError(
            "The following property attributes are required: {}".format(
                ",".join(missing_fields)
            )
        )

    for key in property_dict.keys():
        if property_dict[key] is None:
            property_dict[key] = ""

    exists = object_property_exists(object_type, property_dict["name"])

    if exists:
        return HubspotApi().crm.properties.core_api.update(
            object_type, property_dict["name"], property_dict
        )
    else:
        return HubspotApi().crm.properties.core_api.create(object_type, property_dict)


def get_object_property(object_type: str, property_name: str) -> SimplePublicObject:
    """
    Get a Hubspot object property.

    Args:
        object_type (str): The object type of the property (ie "deals")
        property_name (str): The property name

    Returns:
        SimplePublicObject:  the  object returned from Hubspot
    """
    return HubspotApi().crm.properties.core_api.get_by_name(object_type, property_name)


def object_property_exists(object_type: str, property_name: str) -> bool:
    """
    Return True if the specified property exists, False otherwise

    Args:
        object_type (str): The object type of the property (ie "deals")
        property_name (str): The property name

    Returns:
        boolean:  True if the property exists otherwise False
    """
    try:
        get_object_property(object_type, property_name)
        return True
    except PropertiesApiException:
        return False


def delete_object_property(object_type: str, property_name: str) -> SimplePublicObject:
    """
    Delete a property from Hubspot

    Args:
        object_type (str): The object type of the property (ie "deals")
        property_name (str): The property name

    Returns:
        SimplePublicObject:  the archived object returned from Hubspot
    """
    return HubspotApi().crm.properties.core_api.archive(object_type, property_name)


def get_property_group(object_type: str, group_name: str) -> SimplePublicObject:
    """
    Get a Hubspot property group.

    Args:
        object_type (str): The object type of the group (ie "deals")
        group_name (str): The group name

    Returns:
        SimplePublicObject:  the group object returned from Hubspot
    """
    return HubspotApi().crm.properties.groups_api.get_by_name(object_type, group_name)


def property_group_exists(object_type: str, group_name: str) -> bool:
    """
    Return True if the specified group exists (status=200), False otherwise

    Args:
        object_type (str): The object type of the group (ie "deals")
        group_name (str): The group name

    Returns:
        boolean:  True if the group exists otherwise False
    """
    try:
        get_property_group(object_type, group_name)
        return True
    except PropertiesApiException:
        return False


def sync_property_group(object_type: str, name: str, label: str) -> SimplePublicObject:
    """
    Create or update a property group for an object type

    Args:
        object_type (str): The object type of the group (ie "deals")
        name (str): The group name
        label (str): The group label

    Returns:
        SimplePublicObject:  the  created/updated object returned from Hubspot

    """
    body = {"name": name, "label": label}
    exists = property_group_exists(object_type, name)

    if exists:
        return HubspotApi().crm.properties.groups_api.update(object_type, name, body)
    else:
        return HubspotApi().crm.properties.groups_api.create(object_type, body)


def delete_property_group(object_type: str, group_name: str) -> SimplePublicObject:
    """
    Delete a group from Hubspot

    Args:
        object_type (str): The object type of the group (ie "deals")
        group_name (str): The group name

    Returns:
        SimplePublicObject:  the archived object returned from Hubspot
    """
    return HubspotApi().crm.properties.groups_api.archive(object_type, group_name)


def find_contact(email: str) -> SimplePublicObject:
    """
    Get the hubspot_api id for a contact by email

    Args:
        email(str): The email of the user to find

    Returns:
        SimplePublicObject: The Hubspot contact returned by the API
    """
    return HubspotApi().crm.contacts.basic_api.get_by_id(email, id_property="email")


def find_objects(
    object_type: str,
    query: str = None,
    filters: List[Dict] = None,
    properties: List[Dict] = None,
    sorts: List[Dict] = None,
) -> List[SimplePublicObject]:
    """
    Given an object_type and optional params, return search results from Hubspot.

    Args:
        object_type(str): The hubspot_api type to query (deals, products, etc)
        query(str): The text search to use in the query
        filters(dict): Filters to use for the query.
        properties(list[str]): The specific object properties to return
        sorts(list[dict]): The sorting order(s) to return results in

    Returns:
        list[SimplePublicObject]: The Hubspot objects returned by the API
    """
    return (
        HubspotApi()
        .crm.objects.search_api.do_search(
            public_object_search_request=PublicObjectSearchRequest(
                filter_groups=[{"filters": filters}],
                properties=properties,
                sorts=sorts,
                query=query,
            ),
            object_type=object_type,
        )
        .results
    )


def find_object(
    object_type: str,
    filters: List[Dict],
    query: str = None,
    properties: List[str] = None,
    raise_count_error=True,
) -> SimplePublicObject:
    """
    Find and retrieve a single object from Hubspot.

    Args:
        object_type(str): The hubspot_api type to query (deals, products, etc)
        filters(dict): Filters to use for the query.
        query(str): text search to use for the query.
        properties(list[str]): The specific object properties to return
        raise_count_error(bool): If true, raise error if <>1 object returned
    Returns:
        SimplePublicObject: The Hubspot object returned by the API
    """
    results = find_objects(
        object_type, filters=filters, query=query, properties=properties
    )
    count = len(results)
    if count != 1 and raise_count_error:
        raise ValueError(
            f"Expected 1 result but found {count} for {object_type} search w/filter {filters}",
        )
    return None if count == 0 else results[0]


def find_product(
    name: str, price: str = None, raise_count_error: bool = True
) -> SimplePublicObject:
    """
    Find the hubspot_api id for a product by name and optionally price

    Args:
        name(str): The product name to search for
        price(str): The product price (as formatted string) to search for
        raise_count_error(bool): If true, raise error if <>1 object returned
    Returns:
        SimplePublicObject: The Hubspot product returned by the API
    """
    filters = [create_filter("name", "EQ", name)]
    if price:
        filters.append(create_filter("price", "EQ", price))
    return find_object(
        HubspotObjectType.PRODUCTS.value, filters, raise_count_error=raise_count_error
    )


def find_deal(
    name, amount: str = None, raise_count_error: bool = True
) -> SimplePublicObject:
    """
    Find the hubspot_api id for a deal by name and optionally price

    Args:
        name(str): The deal name to search for
        amount(str): The deal amount (as formatted string) to search for
        raise_count_error(bool): If true, raise error if <>1 object returned
    Returns:
        SimplePublicObject: The Hubspot deal returned by the API
    """
    filters = [create_filter("dealname", "EQ", name)]
    if amount:
        filters.append(create_filter("amount", "EQ", amount))
    return find_object(
        HubspotObjectType.DEALS.value, filters, raise_count_error=raise_count_error
    )


def get_line_items_for_deal(hubspot_id: str) -> List[SimplePublicObject]:
    """
    Given the hubspot_api id for a deal, return all its line items

    Args:
        hubspot_id(str): The deal's hubspot_api id
    Returns:
        list[SimplePublicObject]: The Hubspot line items returned by the API

    """
    client = HubspotApi()
    line_items = []
    associations = client.crm.deals.associations_api.get_all(
        hubspot_id, HubspotObjectType.LINES.value
    ).results
    for association in associations:
        line_items.append(client.crm.line_items.basic_api.get_by_id(association.id))
    return line_items


def find_line_item(
    deal_id: str,
    hs_product_id: str = None,
    quantity: int = None,
    raise_count_error=True,
) -> SimplePublicObject:
    """
    Find a specific line item for a deal, optionally with product and quantity filters

    Args:
        deal_id(str): The deal hubspot_api id
        hs_product_id(str): The product hubspot_api id of the line item to search for
        quantity(int): The line item quantity to search for
        raise_count_error(bool): If true, raise error if <>1 object returned
    Returns:
        SimplePublicObject: The Hubspot line item returned by the API
    """
    line_items = get_line_items_for_deal(deal_id)
    if hs_product_id:
        line_items = [
            item
            for item in line_items
            if item.properties["hs_product_id"] == hs_product_id
        ]
    if quantity:
        line_items = [
            item for item in line_items if item.properties["quantity"] == str(quantity)
        ]
    if len(line_items) != 1 and raise_count_error:
        raise ValueError(
            f"Expected 1 line_item match for deal {deal_id}, hs_prod_id {hs_product_id} but found {len(line_items)}"
        )
    return next(iter(line_items), None)
