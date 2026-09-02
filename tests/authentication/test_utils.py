"""Tests for mitol.authentication.utils"""

import pytest
from django.test import RequestFactory
from mitol.authentication.utils import get_redirect_url


@pytest.fixture
def factory():
    """Request factory"""
    return RequestFactory()


def test_get_redirect_url_no_kwargs(settings, factory):
    """Callable with no kwargs; falls back to the setting, then '/'"""
    request = factory.get("/")

    assert get_redirect_url(request) == settings.MITOL_DEFAULT_POST_LOGOUT_URL

    settings.MITOL_DEFAULT_POST_LOGOUT_URL = ""
    assert get_redirect_url(request) == "/"


def test_get_redirect_url_default_kwarg(factory):
    """The default kwarg wins over the setting"""
    request = factory.get("/")

    assert get_redirect_url(request, default="/custom") == "/custom"


def test_get_redirect_url_param_beats_cookie(factory):
    """Params take precedence over cookies"""
    request = factory.get("/?next=/param")
    request.COOKIES["next"] = "/cookie"

    assert (
        get_redirect_url(request, param_names=["next"], cookie_names=["next"])
        == "/param"
    )


def test_get_redirect_url_name_ordering(factory):
    """The first matching name wins"""
    request = factory.get("/?next=/second&signup_next=/first")

    assert get_redirect_url(request, param_names=["signup_next", "next"]) == "/first"


def test_get_redirect_url_cookie_fallback(factory):
    """Cookies are used when no param matches"""
    request = factory.get("/")
    request.COOKIES["logout-next"] = "/from-cookie"

    assert (
        get_redirect_url(request, param_names=["next"], cookie_names=["logout-next"])
        == "/from-cookie"
    )


def test_get_redirect_url_disallowed_host_skipped(settings, factory):
    """A disallowed host is skipped and the next name is tried"""
    settings.MITOL_ALLOWED_REDIRECT_HOSTS = ["good.example.com"]
    request = factory.get(
        "/?signup_next=https://evil.example.com&next=https://good.example.com"
    )

    assert (
        get_redirect_url(request, param_names=["signup_next", "next"])
        == "https://good.example.com"
    )


def test_get_redirect_url_all_disallowed(settings, factory):
    """All-disallowed values fall through to the default"""
    settings.MITOL_ALLOWED_REDIRECT_HOSTS = []
    request = factory.get("/?next=https://evil.example.com")

    assert (
        get_redirect_url(request, param_names=["next"])
        == settings.MITOL_DEFAULT_POST_LOGOUT_URL
    )
