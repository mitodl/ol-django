"""Tests for the Apigateway API."""

import base64
import json

import faker
import pytest
from django.conf import settings
from mitol.apigateway import api
from mitol.common.factories.defaults import SsoUserFactory

from testapp.main.utils import generate_apisix_request, generate_fake_apisix_payload

FAKE = faker.Faker()
pytestmark = [pytest.mark.django_db]


@pytest.mark.parametrize("obj_type", ["request", "scope"])
def test_decode_x_header(obj_type):
    """Test decoding the userinfo header."""

    payload, user_info = generate_fake_apisix_payload()
    request = generate_apisix_request(obj_type, payload)

    decoded = api.decode_x_header(request)
    assert decoded == user_info


@pytest.mark.parametrize("obj_type", ["request", "scope"])
def test_get_user_id(obj_type):
    """Test getting the user ID (sub)."""

    payload, user_info = generate_fake_apisix_payload()
    request = generate_apisix_request(obj_type, payload)

    decoded = api.get_user_id_from_userinfo_header(request)
    assert decoded == user_info[settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD]


@pytest.mark.parametrize("obj_type", ["request", "scope"])
def test_get_username(obj_type):
    """Test getting the user ID (sub)."""

    user = SsoUserFactory.create()

    payload, user_info = generate_fake_apisix_payload(user=user)

    request = generate_apisix_request(obj_type, payload)

    decoded = api.get_username_from_userinfo_header(request)
    assert decoded != user_info[settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD]
    assert decoded == user.username


def test_create_userinfo_header():
    """Test that the userinfo header gets created properly."""

    user = SsoUserFactory.create()
    header_name = settings.MITOL_APIGATEWAY_USERINFO_HEADER_NAME.replace("HTTP_", "")
    header_data = api.create_userinfo_header(user)
    result = json.loads(base64.b64decode(header_data[header_name]).decode())

    assert result["sub"] == user.global_id


@pytest.mark.django_db
def test_get_username_honours_the_configured_lookup_field(settings):
    """
    The helper reads MITOL_APIGATEWAY_USER_LOOKUP_FIELD, not a hardcoded field.

    It queried global_id directly, so an app configuring a different lookup
    field could authenticate through the backend while this public helper
    looked up the wrong column.
    """
    settings.MITOL_APIGATEWAY_USER_LOOKUP_FIELD = "scim_external_id"
    settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD = "sub"

    test_user = SsoUserFactory.create()
    test_user.scim_external_id = test_user.global_id
    test_user.global_id = None
    test_user.save()

    payload, user_info = generate_fake_apisix_payload()
    user_info["sub"] = test_user.scim_external_id
    payload = base64.b64encode(json.dumps(user_info).encode()).decode()
    request = generate_apisix_request("request", payload)

    assert api.get_username_from_userinfo_header(request) == test_user.username
