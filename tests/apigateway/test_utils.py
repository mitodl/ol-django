"""Tests for apigateway utils"""

from django.test import RequestFactory
from mitol.apigateway.utils import has_gateway_auth

from testapp.main.utils import generate_fake_apisix_payload


def test_has_gateway_auth():
    """has_gateway_auth returns a real bool keyed on the userinfo header"""
    payload, _ = generate_fake_apisix_payload()

    request = RequestFactory().get("/", HTTP_X_USERINFO=payload)
    assert has_gateway_auth(request) is True

    request = RequestFactory().get("/")
    assert has_gateway_auth(request) is False
