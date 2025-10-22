"""Tests for the logout view."""

import json
from base64 import b64encode

import pytest
from django.conf import settings
from mitol.common.factories import UserFactory

pytestmark = pytest.mark.django_db
INTERNAL_LOGOUT_URL_PATH = "/applogout"


@pytest.fixture
def user():
    """Create a user."""

    return UserFactory.create()


@pytest.fixture(autouse=True)
def apigateway_reqs():
    """
    Make sure our backend and middleware are in place.

    Replaces the backends with just the APISIX one, so we're not inadvertently
    testing other backends. The middleware just gets tacked on the end, though,
    because we do depend on some other middleware to be there. Resets things back
    once the test is done.
    """

    before_middleware = settings.MIDDLEWARE
    before_backends = settings.AUTHENTICATION_BACKENDS

    if "mitol.apigateway.backends.ApisixRemoteUserBackend" not in before_backends:
        settings.AUTHENTICATION_BACKENDS = (
            "mitol.apigateway.backends.ApisixRemoteUserBackend",
        )

    if "mitol.apigateway.middleware.ApisixUserMiddleware" not in before_middleware:
        settings.MIDDLEWARE.append("mitol.apigateway.middleware.ApisixUserMiddleware")

    yield

    settings.AUTHENTICATION_BACKENDS = before_backends
    settings.MIDDLEWARE = before_middleware


@pytest.mark.parametrize("has_apisix_header", [True, False])
def test_logout(client, user, has_apisix_header):
    """User should be properly redirected and logged out"""
    header_str = b64encode(
        json.dumps(
            {
                "username": user.username,
                "email": user.email,
                "global_id": user.global_id,
            }
        ).encode()
    )
    client.force_login(user)
    response = client.get(
        INTERNAL_LOGOUT_URL_PATH,
        follow=False,
        HTTP_X_USERINFO=header_str if has_apisix_header else None,
    )
    if has_apisix_header:
        assert response.url == settings.MITOL_APIGATEWAY_LOGOUT_URL
    else:
        assert response.url == (settings.MITOL_APIGATEWAY_DEFAULT_POST_LOGOUT_DEST)
