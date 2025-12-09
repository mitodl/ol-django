"""Tests for the logout view."""

import json
from base64 import b64encode

import pytest
from django.urls import reverse
from mitol.common.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    """Create a user."""

    return UserFactory.create()


@pytest.fixture(autouse=True)
def _apigateway_reqs(settings):
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
@pytest.mark.parametrize("next_url", ["/search", None])
def test_logout(settings, next_url, client, user, has_apisix_header):
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
        f"{reverse('logout')}/?next={next_url or ''}",
        follow=False,
        HTTP_X_USERINFO=header_str if has_apisix_header else None,
    )
    if has_apisix_header:
        assert response.url == settings.MITOL_APIGATEWAY_LOGOUT_URL
        if next_url:
            assert response.cookies.get("next")
            assert response.cookies["next"].value == (
                next_url if next_url else settings.MITOL_DEFAULT_POST_LOGOUT_URL
            )
    else:
        assert response.url == (
            next_url if next_url else settings.MITOL_DEFAULT_POST_LOGOUT_URL
        )


@pytest.mark.parametrize("is_authenticated", [True])
@pytest.mark.parametrize("has_next", [False])
@pytest.mark.parametrize("next_host_is_invalid", [True, False])
def test_next_logout(  # noqa: PLR0913
    settings, mocker, client, user, is_authenticated, has_next, next_host_is_invalid
):
    """Test logout redirect cache assignment"""
    next_url = "https://ocw.mit.edu"
    mock_request = mocker.MagicMock(
        GET={"next": next_url if has_next else None},
    )
    settings.MITOL_ALLOWED_REDIRECT_HOSTS = [
        "testserver",
        "invalid.com" if next_host_is_invalid else "ocw.mit.edu",
    ]
    if is_authenticated:
        client.force_login(user)
        mock_request.user = user
        mock_request.META = {
            "HTTP_X_USERINFO": b64encode(
                json.dumps(
                    {
                        "username": user.username,
                        "email": user.email,
                        "global_id": user.global_id,
                    }
                ).encode()
            ),
        }
    url_params = f"?next={next_url}" if has_next else ""
    resp = client.get(
        f"{reverse('logout')}/{url_params}",
        request=mock_request,
        follow=False,
        HTTP_X_USERINFO=b64encode(
            json.dumps(
                {
                    "username": user.username,
                    "email": user.email,
                    "global_id": user.global_id,
                }
            ).encode()
        ),
    )
    assert resp.status_code == 302  # noqa: PLR2004
    if is_authenticated:
        # APISIX header is present, so user should be logged out there
        assert resp.url == settings.MITOL_APIGATEWAY_LOGOUT_URL
    elif next_host_is_invalid:
        # If host isn't in the allow list, this should always go to the default.
        assert resp.url.endswith(settings.MITOL_DEFAULT_POST_LOGOUT_URL)
    else:
        assert resp.url.endswith(
            next_url if has_next else settings.MITOL_DEFAULT_POST_LOGOUT_URL
        )
