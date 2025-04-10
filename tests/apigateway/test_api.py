"""Tests for the Apigateway API."""

import faker
import pytest
from django.conf import settings
from mitol.apigateway import api

from testapp.main.factories import SsoUserFactory
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
