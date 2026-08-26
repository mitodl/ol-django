"""Tests for the authentication redirect views"""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.urls import reverse
from mitol.authentication.views import (
    AuthRedirectView,
    LoginRedirectView,
)
from mitol.common.factories import UserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.urls("mitol.authentication.urls.auth")]


@pytest.fixture
def user():
    """Create a user."""
    return UserFactory.create()


def _make_request(path="/login", user=None):
    """Build a request with an explicit user"""
    request = RequestFactory().get(path)
    request.user = user or AnonymousUser()
    return request


class CookieRedirectView(AuthRedirectView):
    """Redirect view that also reads a cookie"""

    next_url_cookie_names = ["test-next"]


class FirstLoginRedirectView(LoginRedirectView):
    """Login view where every login is a first login"""

    def is_first_login(self, request):  # noqa: ARG002
        """Treat every login as a first login"""
        return True

    def handle_first_login(self, request):
        """Record the invocation on the request"""
        request.first_login_handled = getattr(request, "first_login_handled", 0) + 1


def test_logout_redirects_and_terminates_session(client, user):
    """Logout redirects to next and ends the Django session"""
    client.force_login(user)

    response = client.get(f"{reverse('logout')}?next=/search", follow=False)

    assert response.url == "/search"
    assert "_auth_user_id" not in client.session


def test_logout_anonymous(client, settings):
    """Logout for an anonymous user just redirects"""
    response = client.get(reverse("logout"), follow=False)

    assert response.url == settings.MITOL_DEFAULT_POST_LOGOUT_URL


def test_logout_disallowed_host(client, settings):
    """A next URL with a disallowed host falls back to the default"""
    settings.MITOL_ALLOWED_REDIRECT_HOSTS = []

    response = client.get(
        f"{reverse('logout')}?next=https://evil.example.com", follow=False
    )

    assert response.url == settings.MITOL_DEFAULT_POST_LOGOUT_URL


def test_auth_redirect_cookie_consumed():
    """A consumed cookie is deleted on the redirect response"""
    request = _make_request("/logout")
    request.COOKIES["test-next"] = "/from-cookie"

    response = CookieRedirectView.as_view()(request)

    assert response.url == "/from-cookie"
    assert response.cookies["test-next"].value == ""
    assert response.cookies["test-next"]["max-age"] == 0


def test_auth_redirect_cookie_name_setting_read_at_request_time(settings):
    """Cookie names based on settings resolve at request time, not import time"""

    class SettingsCookieView(AuthRedirectView):
        def get_next_url_cookie_names(self):
            return [settings.MITOL_APIGATEWAY_LOGOUT_NEXT_URL_COOKIE_NAME]

    settings.MITOL_APIGATEWAY_LOGOUT_NEXT_URL_COOKIE_NAME = "custom-next"
    request = _make_request("/logout")
    request.COOKIES["custom-next"] = "/custom"

    response = SettingsCookieView.as_view()(request)

    assert response.url == "/custom"


def test_login_anonymous_plain_redirect(client):
    """An anonymous login request is a plain redirect"""
    response = client.get(f"{reverse('login')}?next=/search", follow=False)

    assert response.url == "/search"


def test_login_authenticated_not_first_login(user):
    """With the default is_first_login (False), login is a plain redirect"""
    request = _make_request("/login?next=/search", user=user)

    response = LoginRedirectView.as_view()(request)

    assert response.url == "/search"


@pytest.mark.parametrize("has_signup_next", [True, False])
def test_login_first_login_onboarding_redirect(settings, user, has_signup_next):
    """A first login is routed through onboarding with the signup next URL"""
    settings.MITOL_NEW_USER_LOGIN_URL = "/onboarding"

    if has_signup_next:
        path = "/login?next=/plain&signup_next=/signup"
        expected_next = "/signup"
    else:
        path = "/login?next=/plain"
        expected_next = "/plain"

    request = _make_request(path, user=user)
    response = FirstLoginRedirectView.as_view()(request)

    assert response.url == f"/onboarding?next={expected_next.replace('/', '%2F')}"
    assert request.first_login_handled == 1


def test_login_first_login_skip_onboarding(settings, user):
    """skip_onboarding bypasses the onboarding redirect but still handles first login"""
    settings.MITOL_NEW_USER_LOGIN_URL = "/onboarding"

    request = _make_request(
        "/login?next=/plain&signup_next=/signup&skip_onboarding=1", user=user
    )
    response = FirstLoginRedirectView.as_view()(request)

    assert response.url == "/signup"
    assert request.first_login_handled == 1


def test_login_first_login_onboarding_disabled(settings, user):
    """With no onboarding URL configured, first login is a plain redirect"""
    settings.MITOL_NEW_USER_LOGIN_URL = ""

    request = _make_request("/login?next=/plain", user=user)
    response = FirstLoginRedirectView.as_view()(request)

    assert response.url == "/plain"
    assert request.first_login_handled == 1
