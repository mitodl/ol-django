"""Tests for the apigateway login/logout views."""

import pytest
from django.urls import reverse
from mitol.common.factories import UserFactory

from testapp.main.utils import generate_fake_apisix_payload

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
    """User should be logged out of Django and properly redirected"""
    payload, _ = generate_fake_apisix_payload(user=user)
    client.force_login(user)

    response = client.get(
        f"{reverse('logout')}?next={next_url or ''}",
        follow=False,
        HTTP_X_USERINFO=payload if has_apisix_header else None,
    )

    assert response.status_code == 302  # noqa: PLR2004
    assert "_auth_user_id" not in client.session

    expected_next = next_url or settings.MITOL_DEFAULT_POST_LOGOUT_URL

    if has_apisix_header:
        # bounced through the gateway logout, preserving next via cookie
        assert response.url == settings.MITOL_APIGATEWAY_LOGOUT_URL
        cookie = response.cookies[settings.MITOL_APIGATEWAY_LOGOUT_NEXT_URL_COOKIE_NAME]
        assert cookie.value == expected_next
        assert cookie["max-age"] == settings.MITOL_APIGATEWAY_LOGOUT_NEXT_URL_COOKIE_TTL
    else:
        assert response.url == expected_next


def test_logout_return_hop(settings, client):
    """The gateway-logout return hop should redirect to the cookie and clear it"""
    cookie_name = settings.MITOL_APIGATEWAY_LOGOUT_NEXT_URL_COOKIE_NAME
    client.cookies[cookie_name] = "/search"

    response = client.get(reverse("logout"), follow=False)

    assert response.url == "/search"
    # cookie is deleted on the response
    assert response.cookies[cookie_name].value == ""
    assert response.cookies[cookie_name]["max-age"] == 0


@pytest.mark.parametrize("next_host_is_valid", [True, False])
def test_logout_next_host_validation(settings, client, next_host_is_valid):
    """An absolute next URL is only honored if its host is allowed"""
    settings.MITOL_ALLOWED_REDIRECT_HOSTS = [
        "ocw.mit.edu" if next_host_is_valid else "other.example.com",
    ]
    next_url = "https://ocw.mit.edu"

    response = client.get(f"{reverse('logout')}?next={next_url}", follow=False)

    if next_host_is_valid:
        assert response.url == next_url
    else:
        assert response.url == settings.MITOL_DEFAULT_POST_LOGOUT_URL


def test_logout_next_cookie_host_validation(settings, client):
    """A disallowed host in the logout cookie falls back to the default"""
    settings.MITOL_ALLOWED_REDIRECT_HOSTS = []
    cookie_name = settings.MITOL_APIGATEWAY_LOGOUT_NEXT_URL_COOKIE_NAME
    client.cookies[cookie_name] = "https://evil.example.com"

    response = client.get(reverse("logout"), follow=False)

    assert response.url == settings.MITOL_DEFAULT_POST_LOGOUT_URL


def test_login_redirects_to_next_param(settings, client, user):
    """Login redirects to the next param and writes the login cookie"""
    payload, _ = generate_fake_apisix_payload(user=user)

    response = client.get(
        f"{reverse('login')}?next=/dashboard",
        follow=False,
        HTTP_X_USERINFO=payload,
    )

    assert response.url == "/dashboard"
    # the middleware preserves the next param for the gateway login bounce
    cookie = response.cookies[settings.MITOL_APIGATEWAY_LOGIN_NEXT_URL_COOKIE_NAME]
    assert cookie.value == "/dashboard"
    assert cookie["max-age"] == settings.MITOL_APIGATEWAY_LOGIN_NEXT_URL_COOKIE_TTL


def test_login_redirects_to_cookie(settings, client, user):
    """Without a next param, login falls back to the middleware-written cookie"""
    payload, _ = generate_fake_apisix_payload(user=user)
    cookie_name = settings.MITOL_APIGATEWAY_LOGIN_NEXT_URL_COOKIE_NAME
    client.cookies[cookie_name] = "/dashboard"

    response = client.get(reverse("login"), follow=False, HTTP_X_USERINFO=payload)

    assert response.url == "/dashboard"
    # consumed cookie is deleted on the response
    assert response.cookies[cookie_name].value == ""
    assert response.cookies[cookie_name]["max-age"] == 0


def test_login_param_beats_cookie(settings, client):
    """The next param takes precedence over the cookie"""
    client.cookies[settings.MITOL_APIGATEWAY_LOGIN_NEXT_URL_COOKIE_NAME] = "/cookie"

    response = client.get(f"{reverse('login')}?next=/param", follow=False)

    assert response.url == "/param"


def test_login_default_redirect(settings, client):
    """With no next param or cookie, login redirects to the default"""
    response = client.get(reverse("login"), follow=False)

    assert response.url == settings.MITOL_DEFAULT_POST_LOGOUT_URL
