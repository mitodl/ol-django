"""
Hubspot API tests
"""

import json
from collections.abc import Iterable

import pytest
from django.contrib.auth.models import Group, User
from django.contrib.contenttypes.models import ContentType
from faker import Faker
from hubspot.crm.objects import (
    ApiException,
    AssociatedId,
    SimplePublicObject,
    SimplePublicObjectInput,
)
from mitol.common.factories import UserFactory
from mitol.hubspot_api import api
from mitol.hubspot_api.factories import HubspotObjectFactory, SimplePublicObjectFactory
from mitol.hubspot_api.models import HubspotObject

# pylint: disable=redefined-outer-name

fake = Faker()

test_object_type = "deals"


@pytest.fixture
def property_group():
    """Return sample group JSON"""
    return {"name": "group_name", "label": "Group Label"}


@pytest.fixture
def content_type_obj():
    """Return a sample ContentType"""
    return ContentType.objects.get_for_model(Group)


@pytest.fixture
def mock_hubspot_api(mocker):
    """Mock the send hubspot request method"""
    return mocker.patch("mitol.hubspot_api.api.HubspotApi")


@pytest.fixture
def mock_search_object(mocker):
    """Return a mocked PublicObjectSearchRequest"""
    return mocker.patch("mitol.hubspot_api.api.PublicObjectSearchRequest")


def test_api_kwargs(settings):
    """HubSpot should be initialized with expected settings"""
    client = api.HubspotApi()
    assert client.access_token == settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN
    assert client.config["retry"].total == settings.MITOL_HUBSPOT_API_RETRIES


def test_api_get_all_objects(mocker, mock_hubspot_api):
    """HubspotApi.get_all_objects should yield expected results"""
    all_results = SimplePublicObjectFactory.create_batch(9)
    mock_hubspot_api.return_value.crm.objects.basic_api.get_page.side_effect = [
        mocker.Mock(
            paging=mocker.Mock(next=mocker.Mock(after=2)), results=all_results[0:3]
        ),
        mocker.Mock(
            paging=mocker.Mock(next=mocker.Mock(after=3)), results=all_results[3:6]
        ),
        mocker.Mock(paging=None, results=all_results[6:]),
    ]
    test_results = api.get_all_objects(api.HubspotObjectType.PRODUCTS.value, limit=3)
    assert isinstance(test_results, Iterable)
    assert list(test_results) == all_results


@pytest.mark.parametrize(
    "response, exists",  # noqa: PT006
    [
        [api.PropertiesApiException(), False],  # noqa: PT007
        [SimplePublicObject(id=1), True],  # noqa: PT007
    ],
)
def test_object_property_exists(mocker, response, exists):
    """Test that object_property_exists returns True if the property exists and False otherwise"""  # noqa: E501
    mock_get_object_property = mocker.patch(
        "mitol.hubspot_api.api.get_object_property", side_effect=[response]
    )
    assert api.object_property_exists("deals", "my_property") == exists
    mock_get_object_property.assert_called_once_with("deals", "my_property")


@pytest.mark.parametrize(
    "response, exists",  # noqa: PT006
    [
        [api.PropertiesApiException(), False],  # noqa: PT007
        [SimplePublicObject(id=1), True],  # noqa: PT007
    ],
)
def test_property_group_exists(mocker, response, exists):
    """Test that property_group_exists returns True if the group exists and False otherwise"""  # noqa: E501
    mock_get_property_group = mocker.patch(
        "mitol.hubspot_api.api.get_property_group", side_effect=[response]
    )
    assert api.property_group_exists("deals", "my_group") == exists
    mock_get_property_group.assert_called_once_with("deals", "my_group")


def test_get_property_group(mock_hubspot_api, property_group):
    """get_property_group should call send_hubspot_request with the correct arguments"""
    group_name = property_group["name"]
    api.get_property_group(test_object_type, group_name)
    assert mock_hubspot_api.called_with(  # noqa: PGH005
        group_name, f"/properties/v1/{test_object_type}/groups/named", "GET"
    )


def test_get_object_property(mock_hubspot_api):
    """get_object_property should call send_hubspot_request with the correct arguments"""  # noqa: E501
    property_name = "y"
    api.get_object_property(test_object_type, property_name)
    assert mock_hubspot_api.called_with(  # noqa: PGH005
        f"named/{property_name}", f"/properties/v1/{test_object_type}/properties", "GET"
    )


@pytest.mark.parametrize("is_valid", [True, False])
@pytest.mark.parametrize("object_exists", [True, False])
def test_sync_object_property(mocker, mock_hubspot_api, object_exists, is_valid):
    """sync_object_property should call send_hubspot_request with the correct arguments"""  # noqa: E501
    mocker.patch(
        "mitol.hubspot_api.api.object_property_exists", return_value=object_exists
    )
    mock_properties = {
        "name": "property_name",
        "label": "Property Label",
        "groupName": "Property Group",
        "description": "Property description",
        "field_type": "text",
        "type": "string",
    }

    if not is_valid:
        mock_properties.pop("name")
        with pytest.raises(KeyError):
            api.sync_object_property(test_object_type, mock_properties)
    else:
        api.sync_object_property(test_object_type, mock_properties)
        if object_exists:
            mock_hubspot_api.return_value.crm.properties.core_api.update.assert_called_once_with(
                test_object_type, mock_properties["name"], mock_properties
            )
        else:
            mock_hubspot_api.return_value.crm.properties.core_api.create.assert_called_once_with(
                test_object_type, mock_properties
            )


@pytest.mark.parametrize("object_exists", [True, False])
def test_sync_property_group(mocker, mock_hubspot_api, object_exists, property_group):
    """sync_object_property should call send_hubspot_request with the correct arguments"""  # noqa: E501
    mock_create = mock_hubspot_api.return_value.crm.properties.groups_api.create
    mock_update = mock_hubspot_api.return_value.crm.properties.groups_api.update
    mocker.patch(
        "mitol.hubspot_api.api.property_group_exists", return_value=object_exists
    )
    group_name = property_group["name"]
    group_label = property_group["label"]

    api.sync_property_group(test_object_type, group_name, group_label)

    if object_exists:
        mock_update.assert_called_once_with(
            test_object_type, group_name, property_group
        )
    else:
        mock_create.assert_called_once_with(test_object_type, property_group)


def test_delete_property_group(mock_hubspot_api, property_group):
    """delete_property_group should call send_hubspot_request with the correct arguments"""  # noqa: E501
    mock_archive = mock_hubspot_api.return_value.crm.properties.groups_api.archive
    mock_archive.return_value = 204
    result = api.delete_property_group(test_object_type, property_group["name"])
    mock_archive.assert_called_once()
    assert result == 204  # noqa: PLR2004


def test_delete_object_property(mock_hubspot_api, property_group):
    """delete_object_property should call send_hubspot_request with the correct arguments"""  # noqa: E501
    mock_archive = mock_hubspot_api.return_value.crm.properties.core_api.archive
    mock_archive.return_value = 204
    result = api.delete_object_property(test_object_type, property_group["name"])
    mock_archive.assert_called_once()
    assert result == 204  # noqa: PLR2004


@pytest.mark.django_db
def test_get_hubspot_id():
    """Return the hubspot id if any for the specified content type and object ID"""
    hubspot_obj = HubspotObjectFactory.create()
    assert (
        api.get_hubspot_id(hubspot_obj.object_id, hubspot_obj.content_type)
        == hubspot_obj.hubspot_id
    )


@pytest.mark.parametrize("prefix", ["APP-1", "APP-2"])
def test_format_app_id(settings, prefix):
    """The specified object id should have the correct prefix"""
    settings.MITOL_HUBSPOT_API_ID_PREFIX = prefix
    object_id = 123
    assert api.format_app_id(object_id) == f"{prefix}-{object_id}"


@pytest.mark.django_db
def test_upsert_object_request_new(mock_hubspot_api, content_type_obj):
    """A HubspotObject should be created after an object is synced for the first time"""
    hubspot_id = "123456789"
    object_id = 123
    mock_create = mock_hubspot_api.return_value.crm.objects.basic_api.create
    mock_create.return_value = SimplePublicObject(id=hubspot_id)
    body = {"properties": {"foo": "bar"}}
    api.upsert_object_request(
        content_type_obj, api.HubspotObjectType.DEALS.value, object_id, body=body
    )
    mock_create.assert_called_once()
    assert (
        HubspotObject.objects.get(
            content_type=content_type_obj, object_id=object_id
        ).hubspot_id
        == hubspot_id
    )


@pytest.mark.django_db
def test_upsert_object_request_exists(mock_hubspot_api):
    """upsert_object_request should try a patch hubspot API call if there's an existing Hubspot object"""  # noqa: E501
    hs_obj = HubspotObjectFactory.create()
    mock_update = mock_hubspot_api.return_value.crm.objects.basic_api.update
    mock_update.return_value = SimplePublicObject(id=hs_obj.hubspot_id)
    body = {"properties": {"foo": "bar"}}
    api.upsert_object_request(
        hs_obj.content_type,
        api.HubspotObjectType.DEALS.value,
        hs_obj.object_id,
        body=body,
    )
    mock_update.assert_called_once()


@pytest.mark.parametrize(
    "status, message",  # noqa: PT006
    [
        [409, "Dupe error. Existing ID: {}"],  # noqa: PT007
        [400, "Dupe error. {} already has that value."],  # noqa: PT007
    ],
)
@pytest.mark.parametrize(
    "hs_type",
    [
        api.HubspotObjectType.PRODUCTS.value,
        api.HubspotObjectType.CONTACTS.value,
    ],
)
@pytest.mark.django_db
def test_upsert_object_request_missing_id(  # noqa: PLR0913
    mocker, mock_hubspot_api, content_type_obj, status, message, hs_type
):
    """If an object exists in Hubspot but missing a HubspotObject in Django, retry upsert w/patch instead of post"""  # noqa: E501
    hubspot_id = "123456789"
    object_id = 123
    new_email = "test@test.edu"
    mock_update = mock_hubspot_api.return_value.crm.objects.basic_api.update
    mock_update.return_value = SimplePublicObject(id=hubspot_id)
    mock_create = mock_hubspot_api.return_value.crm.objects.basic_api.create
    mock_create.side_effect = ApiException(
        http_resp=mocker.Mock(
            data=json.dumps(
                {
                    "message": message.format(hubspot_id),
                }
            ),
            reason="",
            status=status,
        )
    )
    body = SimplePublicObjectInput(properties={"email": new_email})
    api.upsert_object_request(
        content_type_obj,
        hs_type,
        object_id=object_id,
        body=body,
    )
    mock_update.assert_called_once()
    mock_create.assert_called_once()
    assert (
        HubspotObject.objects.get(
            content_type=content_type_obj, object_id=object_id
        ).hubspot_id
        == hubspot_id
    )


@pytest.mark.django_db
def test_upsert_object_request_other_error(mocker, mock_hubspot_api, content_type_obj):
    """If a non-dupe ApIException happens, raise it"""
    object_id = 123
    mock_create = mock_hubspot_api.return_value.crm.objects.basic_api.create
    mock_create.side_effect = ApiException(
        http_resp=mocker.Mock(
            data=json.dumps(
                {
                    "message": "something bad happened",
                }
            ),
            reason="",
            status=400,
        )
    )
    body = {"properties": {"foo": "bar"}}
    with pytest.raises(Exception):  # noqa: B017, PT011
        api.upsert_object_request(
            content_type_obj,
            api.HubspotObjectType.CONTACTS.value,
            object_id=object_id,
            body=body,
        )


@pytest.mark.parametrize("is_primary_email", [True, False])
@pytest.mark.django_db
def test_upsert_object_contact_dupe_email(mocker, mock_hubspot_api, is_primary_email):
    """If single hubspot contact has multiple emails matching 2+ django users, delete the other email"""  # noqa: E501
    dupe_hubspot_id = "123456789"
    new_hubspot_id = "222222222"
    old_user = UserFactory.create(email="old@test.edu")
    new_user = UserFactory.create(email="new@test.edu")
    ct = ContentType.objects.get_for_model(User)
    old_hso = HubspotObjectFactory.create(
        content_type=ct,
        hubspot_id=dupe_hubspot_id,
        object_id=old_user.id,
        content_object=old_user,
    )
    mocker.patch(
        "mitol.hubspot_api.api.find_contact",
        return_value=SimplePublicObject(
            id=dupe_hubspot_id,
            properties={
                "email": new_user.email if is_primary_email else old_user.email,
                "hs_additional_emails": old_user.email
                if is_primary_email
                else new_user.email,
            },
        ),
    )
    mock_create = mock_hubspot_api.return_value.crm.objects.basic_api.create
    mock_update = mock_hubspot_api.return_value.crm.objects.basic_api.update
    mock_exc = ApiException(
        http_resp=mocker.Mock(
            data=json.dumps(
                {
                    "message": f"Existing ID: {dupe_hubspot_id}",
                }
            ),
            reason="",
            status=409,
        )
    )
    mock_create.side_effect = (
        mock_exc
        if is_primary_email
        else [
            mock_exc,
            SimplePublicObject(id=new_hubspot_id, properties={"email": new_user.email}),
        ]
    )
    mock_update.return_value = SimplePublicObject(
        id=dupe_hubspot_id if is_primary_email else new_hubspot_id
    )
    mock_secondary = mocker.patch("mitol.hubspot_api.api.delete_secondary_email")
    body = SimplePublicObjectInput(properties={"email": new_user.email})
    api.upsert_object_request(
        ct,
        api.HubspotObjectType.CONTACTS.value,
        object_id=new_user.id,
        body=body,
    )
    if is_primary_email:
        mock_secondary.assert_called_once_with(old_user.email, old_hso.hubspot_id)
        assert (
            HubspotObject.objects.filter(
                content_type=ct, object_id=old_user.id
            ).exists()
            is False
        )
        assert (
            HubspotObject.objects.get(
                content_type=ct, hubspot_id=dupe_hubspot_id
            ).object_id
            == new_user.id
        )
    else:
        mock_secondary.assert_called_once_with(new_user.email, dupe_hubspot_id)
        assert (
            HubspotObject.objects.get(
                content_type=ct, hubspot_id=dupe_hubspot_id
            ).object_id
            == old_user.id
        )
        assert (
            HubspotObject.objects.get(
                content_type=ct, hubspot_id=new_hubspot_id
            ).object_id
            == new_user.id
        )


def test_associate_objects_request(mock_hubspot_api):
    """An API call should be be made with correct URL to set associations"""
    from_type = api.HubspotObjectType.DEALS.value
    from_id = 123
    to_type = api.HubspotObjectType.CONTACTS.value
    to_id = 456
    assoc_type = api.HubspotAssociationType.DEAL_CONTACT.value
    mock_create = mock_hubspot_api.return_value.crm.objects.associations_api.create

    api.associate_objects_request(from_type, from_id, to_type, to_id, assoc_type)
    mock_create.assert_called_once_with(from_type, from_id, to_type, to_id, assoc_type)


def test_make_object_properties_message(mocker):
    """make_object_properties_message should return expected JSON"""
    test_dict = {"foo": "bar"}
    mock_sanitize = mocker.patch(
        "mitol.hubspot_api.api.replace_null_values", return_value=test_dict
    )
    assert api.make_object_properties_message(test_dict).properties == test_dict
    mock_sanitize.assert_called_once()


def test_transform_object_properties():
    """transform_object_properties should update dict keys as expected"""
    test_mapping = {"title": "name", "product": "product_id", "postal_code": "zip"}
    test_dict = {
        "title": "My Title",
        "product": None,
        "postal_code": "03082",
        "city": "city",
    }
    assert api.transform_object_properties(test_dict, test_mapping) == {
        "name": "My Title",
        "product_id": None,
        "zip": "03082",
    }


def test_find_contact(mock_hubspot_api):
    """find_contact should make the appropriate api call"""
    email = "testmail@mit.edu"
    mock_get_by_id = mock_hubspot_api.return_value.crm.contacts.basic_api.get_by_id
    api.find_contact(email)
    mock_get_by_id.assert_called_once_with(
        email, id_property="email", properties=["email", "hs_additional_emails"]
    )


@pytest.mark.parametrize(
    "query,filters,sorts,properties",  # noqa: PT006
    [
        [  # noqa: PT007
            None,
            [{"propertyName": "name", "operator": "EQ", "value": "XPRO-ORDER-1"}],
            None,
            None,
        ],
        ["", [], [{"propertyName": "name", "direction": "DESCENDING"}], []],  # noqa: PT007
        ["XPRO-ORDER-1", None, [], ["name", "amount"]],  # noqa: PT007
    ],
)
def test_find_objects(  # noqa: PLR0913
    mocker, mock_hubspot_api, mock_search_object, query, filters, sorts, properties
):
    """The search API call should be made with correct parameters"""
    mock_results = SimplePublicObjectFactory.create_batch(2)
    mock_hubspot_api.return_value.crm.objects.search_api.do_search.return_value = (
        mocker.Mock(results=mock_results)
    )
    results = api.find_objects(
        api.HubspotObjectType.DEALS.value,
        query=query,
        filters=filters,
        sorts=sorts,
        properties=properties,
    )
    mock_search_object.assert_called_once_with(
        filter_groups=[{"filters": filters}],
        properties=properties,
        sorts=sorts,
        query=query,
    )
    mock_hubspot_api.return_value.crm.objects.search_api.do_search.assert_called_once_with(
        public_object_search_request=mock_search_object.return_value,
        object_type=api.HubspotObjectType.DEALS.value,
    )
    assert results == mock_results


def test_find_object(mocker, mock_hubspot_api, mock_search_object):
    """find_object should return the expected result and make expected api calls"""
    mock_result = SimplePublicObjectFactory.create()
    mock_hubspot_api.return_value.crm.objects.search_api.do_search.return_value = (
        mocker.Mock(results=[mock_result])
    )

    query = "test query"
    filters = [{"propertyName": "name", "operator": "EQ", "value": "XPRO-ORDER-1"}]
    properties = ["name", "coupon"]
    results = api.find_object(
        api.HubspotObjectType.DEALS.value, filters, query=query, properties=properties
    )
    mock_search_object.assert_called_once_with(
        filter_groups=[{"filters": filters}],
        properties=properties,
        query=query,
        sorts=None,
    )
    mock_hubspot_api.return_value.crm.objects.search_api.do_search.assert_called_once_with(
        public_object_search_request=mock_search_object.return_value,
        object_type=api.HubspotObjectType.DEALS.value,
    )
    assert results == mock_result


@pytest.mark.parametrize("count", [0, 2])
def test_find_object_raise_errors(mocker, mock_hubspot_api, count):
    """An error should be raised when results count is not 1"""
    mock_results = [SimplePublicObjectFactory.create() for _ in range(count)]
    mock_hubspot_api.return_value.crm.objects.search_api.do_search.return_value = (
        mocker.Mock(results=mock_results)
    )
    filters = [{"propertyName": "amount", "operator": "EQ", "value": "0.00"}]
    with pytest.raises(ValueError) as err:  # noqa: PT011
        api.find_object(api.HubspotObjectType.PRODUCTS.value, filters)
    assert err.value.args == (
        f"Expected 1 result but found {count} for {api.HubspotObjectType.PRODUCTS.value} search w/filter {filters}",  # noqa: E501
    )


@pytest.mark.parametrize("count", [0, 2])
def test_find_object_no_raise(mocker, mock_hubspot_api, count):
    """An error should not be raised if results count is not 1 but raise_count_error=False"""  # noqa: E501
    mock_results = [SimplePublicObjectFactory.create() for _ in range(count)]
    mock_hubspot_api.return_value.crm.objects.search_api.do_search.return_value = (
        mocker.Mock(results=mock_results)
    )
    filters = [{"propertyName": "price", "operator": "EQ", "value": "0.00"}]
    result = api.find_object(
        api.HubspotObjectType.PRODUCTS.value, filters, raise_count_error=False
    )
    assert result is (None if count == 0 else mock_results[0])


@pytest.mark.parametrize("price", [None, 0.00, 400.23])
@pytest.mark.parametrize("raise_error", [True, False])
def test_find_product(mocker, price, raise_error):
    """find_product should call find_object with the appropriate args and kwargs"""
    mock_result = SimplePublicObjectFactory.create()
    mock_find_object = mocker.patch(
        "mitol.hubspot_api.api.find_object", return_value=mock_result
    )
    name = "Course MITx-1.00"
    expected_filters = [{"propertyName": "name", "operator": "EQ", "value": name}]
    if price:
        expected_filters.append(
            {"propertyName": "price", "operator": "EQ", "value": price}
        )
    result = api.find_product(name, price=price, raise_count_error=raise_error)
    mock_find_object.assert_called_once_with(
        api.HubspotObjectType.PRODUCTS.value,
        expected_filters,
        raise_count_error=raise_error,
    )
    assert result == mock_result


@pytest.mark.parametrize("amount", [None, 0.00, 400.23])
@pytest.mark.parametrize("raise_error", [True, False])
def test_find_deal(mocker, amount, raise_error):
    """find_deal should call find_object with the appropriate args and kwargs"""
    mock_result = SimplePublicObjectFactory.create()
    mock_find_object = mocker.patch(
        "mitol.hubspot_api.api.find_object", return_value=mock_result
    )
    name = "MIT-ORDER-111"
    expected_filters = [{"propertyName": "dealname", "operator": "EQ", "value": name}]
    if amount:
        expected_filters.append(
            {"propertyName": "amount", "operator": "EQ", "value": amount}
        )
    result = api.find_deal(name, amount=amount, raise_count_error=raise_error)
    mock_find_object.assert_called_once_with(
        api.HubspotObjectType.DEALS.value,
        expected_filters,
        raise_count_error=raise_error,
    )
    assert result == mock_result


@pytest.mark.parametrize(
    "product_id,quantity,raise_error",  # noqa: PT006
    [
        [None, 3, True],  # noqa: PT007
        ["123456", None, False],  # noqa: PT007
        ["nomatch", 10, True],  # noqa: PT007
        ["nomatch", 23, False],  # noqa: PT007
    ],
)
def test_find_line_item(mocker, product_id, quantity, raise_error):
    """find_line_item should make expected api calls and return expected result"""
    mock_lines = [
        SimplePublicObjectFactory(
            properties={"hs_product_id": "123456", "quantity": "2"}
        ),
        SimplePublicObjectFactory(
            properties={"hs_product_id": "654321", "quantity": "3"}
        ),
    ]
    expected_result = (
        mock_lines[0]
        if product_id == "123456"
        else mock_lines[1]
        if quantity == 3  # noqa: PLR2004
        else None
    )
    mock_get_lines_for_deal = mocker.patch(
        "mitol.hubspot_api.api.get_line_items_for_deal", return_value=mock_lines
    )
    deal_id = "1111222"
    if product_id == "nomatch" and raise_error:
        with pytest.raises(ValueError):  # noqa: PT011
            api.find_line_item(
                deal_id,
                hs_product_id=product_id,
                quantity=quantity,
                raise_count_error=raise_error,
            )
    else:
        result = api.find_line_item(
            deal_id,
            hs_product_id=product_id,
            quantity=quantity,
            raise_count_error=raise_error,
        )
        assert result == expected_result
    mock_get_lines_for_deal.assert_called_once_with(deal_id)


def test_get_line_items_for_deal(mocker, mock_hubspot_api):
    """get_line_items_for_deal should make expected api calls and return expected results"""  # noqa: E501
    mock_lines = SimplePublicObjectFactory.create_batch(2)
    mock_hubspot_api.return_value.crm.deals.associations_api.get_all.return_value = (
        mocker.Mock(
            results=[
                AssociatedId(id=line.id, type="deal_to_line_item")
                for line in mock_lines
            ]
        )
    )
    mock_hubspot_api.return_value.crm.line_items.basic_api.get_by_id.side_effect = (
        mock_lines[0],
        mock_lines[1],
    )
    deal_id = "111123"
    results = api.get_line_items_for_deal(deal_id)
    mock_hubspot_api.return_value.crm.deals.associations_api.get_all.assert_called_once_with(
        deal_id, api.HubspotObjectType.LINES.value
    )
    assert (
        mock_hubspot_api.return_value.crm.line_items.basic_api.get_by_id.call_count == 2  # noqa: PLR2004
    )
    for line in mock_lines:
        mock_hubspot_api.return_value.crm.line_items.basic_api.get_by_id.assert_any_call(
            line.id
        )
    assert results == mock_lines
