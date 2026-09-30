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


@pytest.mark.parametrize("obj_type", ["request", "scope"])
@pytest.mark.parametrize(
    "raw_header",
    [
        "abcde",
        base64.b64encode(b"not json").decode(),
        base64.b64encode(b"\xff\xfe").decode(),
        base64.b64encode(json.dumps(["a", "list"]).encode()).decode(),
        base64.b64encode(json.dumps("a string").encode()).decode(),
        "!!!!" + base64.b64encode(json.dumps({"sub": "someone"}).encode()).decode(),
    ],
)
def test_decode_x_header_malformed(caplog, obj_type, raw_header):
    """A header that isn't a base64-encoded JSON object is treated as missing."""

    request = generate_apisix_request(obj_type, raw_header)

    assert api.decode_x_header(request) is None
    assert api.get_user_id_from_userinfo_header(request) is None
    assert any(record.levelname == "WARNING" for record in caplog.records)


def test_get_username_honors_lookup_field(settings):
    """The username lookup uses MITOL_APIGATEWAY_USER_LOOKUP_FIELD."""

    settings.MITOL_APIGATEWAY_USER_LOOKUP_FIELD = "scim_external_id"
    user = SsoUserFactory.create(scim_external_id=FAKE.unique.uuid4())
    _, user_info = generate_fake_apisix_payload(user=user)
    user_info[settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD] = user.scim_external_id
    payload = base64.b64encode(json.dumps(user_info).encode()).decode()

    request = generate_apisix_request("request", payload)

    assert api.get_username_from_userinfo_header(request) == user.username
