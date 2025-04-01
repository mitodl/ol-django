"""Tests for the logout view."""

import json
from base64 import b64encode

import pytest
from django.conf import settings
from mitol.common.factories import UserFactory

pytestmark = pytest.mark.django_db
INTERNAL_LOGOUT_URL_PATH = "/applogout"


@pytest.fixture()
def user():
    """Create a user."""

    return UserFactory.create()


@pytest.mark.parametrize("has_apisix_header", [True, False])
@pytest.mark.parametrize("next_url", ["/search", None])
def test_logout(next_url, client, user, has_apisix_header):
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
        f"{INTERNAL_LOGOUT_URL_PATH}/?next={next_url or ''}",
        follow=False,
        HTTP_X_USERINFO=header_str if has_apisix_header else None,
    )
    if has_apisix_header:
        assert response.url == settings.MITOL_APIGATEWAY_LOGOUT_URL
    else:
        assert response.url == (
            next_url if next_url else settings.MITOL_APIGATEWAY_DEFAULT_POST_LOGOUT_DEST
        )


@pytest.mark.parametrize("is_authenticated", [True])
@pytest.mark.parametrize("has_next", [False])
@pytest.mark.parametrize("next_host_is_invalid", [True, False])
def test_next_logout(  # noqa: PLR0913
    mocker, client, user, is_authenticated, has_next, next_host_is_invalid
):
    """Test logout redirect cache assignment"""
    next_url = "https://ocw.mit.edu"
    mock_request = mocker.MagicMock(
        GET={"next": next_url if has_next else None},
    )
    settings.MITOL_APIGATEWAY_ALLOWED_REDIRECT_HOSTS = [
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
        f"{INTERNAL_LOGOUT_URL_PATH}/{url_params}",
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
        assert resp.url.endswith(settings.MITOL_APIGATEWAY_DEFAULT_POST_LOGOUT_DEST)
    else:
        assert resp.url.endswith(
            next_url if has_next else settings.MITOL_APIGATEWAY_DEFAULT_POST_LOGOUT_DEST
        )
