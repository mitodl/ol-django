"""Test the regular Django middleware."""

import faker
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from mitol.apigateway.middleware import ApisixUserMiddleware
from mitol.common.factories.defaults import SsoUserFactory, UserFactory

from testapp.main.utils import generate_apisix_request, generate_fake_apisix_payload

FAKE = faker.Faker()
pytestmark = [pytest.mark.django_db]
User = get_user_model()


@pytest.mark.parametrize("new_user", [False, True])
def test_middleware(new_user):
    """
    Test that the middleware extracts the data properly.

    This has the side-effect of testing the backend too.
    """

    id_field = settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD
    backends = settings.AUTHENTICATION_BACKENDS
    settings.AUTHENTICATION_BACKENDS = [
        "mitol.apigateway.backends.ApisixRemoteUserBackend",
    ]

    test_user = None if new_user else SsoUserFactory.create()

    payload, user_info = generate_fake_apisix_payload(user=test_user)
    request = generate_apisix_request("request", payload)

    middleware = ApisixUserMiddleware(lambda req: HttpResponse())  # noqa: ARG005

    middleware.process_request(request)

    assert request.META["REMOTE_USER"] == user_info.get(id_field)

    test_user = User.objects.get(global_id=user_info.get(id_field))
    assert request.user == test_user

    settings.AUTHENTICATION_BACKENDS = backends


@pytest.mark.parametrize("new_user", [False, True])
def test_middleware_logs_out(new_user):
    """
    Test that the middleware logs out the user if the header is not present.
    """
    id_field = settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD
    backends = settings.AUTHENTICATION_BACKENDS
    settings.AUTHENTICATION_BACKENDS = [
        "mitol.apigateway.backends.ApisixRemoteUserBackend",
    ]

    test_user = None if new_user else SsoUserFactory.create()

    payload, user_info = generate_fake_apisix_payload(user=test_user)
    request = generate_apisix_request("request", payload)

    middleware = ApisixUserMiddleware(lambda req: HttpResponse())  # noqa: ARG005
    middleware.process_request(request)

    assert request.META["REMOTE_USER"] == user_info.get(id_field)

    test_user = User.objects.get(global_id=user_info.get(id_field))
    assert request.user == test_user

    no_header_request = generate_apisix_request("request", payload)
    no_header_request.META["HTTP_X_USERINFO"] = None
    middleware.process_request(no_header_request)
    assert "REMOTE_USER" not in no_header_request
    assert no_header_request.user.is_anonymous

    settings.AUTHENTICATION_BACKENDS = backends


@pytest.fixture
def _client_gateway(settings):
    """Wire the APISIX backend and middleware for client-level tests."""
    settings.AUTHENTICATION_BACKENDS = [
        "mitol.apigateway.backends.ApisixRemoteUserBackend",
    ]
    if "mitol.apigateway.middleware.ApisixUserMiddleware" not in settings.MIDDLEWARE:
        settings.MIDDLEWARE = [
            *settings.MIDDLEWARE,
            "mitol.apigateway.middleware.ApisixUserMiddleware",
        ]


@pytest.mark.usefixtures("_client_gateway")
def test_same_user_no_session_cycle(client, mocker):
    """A request whose session already matches the header never cycles the session"""
    test_user = SsoUserFactory.create()
    payload, _ = generate_fake_apisix_payload(user=test_user)

    client.force_login(
        test_user, backend="mitol.apigateway.backends.ApisixRemoteUserBackend"
    )
    session_key = client.session.session_key
    last_login = User.objects.get(pk=test_user.pk).last_login

    login_mock = mocker.patch("django.contrib.auth.login")

    response = client.get("/login?next=/dashboard", HTTP_X_USERINFO=payload)

    assert response.status_code == 302  # noqa: PLR2004
    login_mock.assert_not_called()
    assert client.session.session_key == session_key
    assert User.objects.get(pk=test_user.pk).last_login == last_login


@pytest.mark.usefixtures("_client_gateway")
def test_same_user_update_disabled_short_circuits(client, mocker, settings):
    """With updates disabled, a matching session does no auth work at all"""
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = False

    test_user = SsoUserFactory.create()
    payload, _ = generate_fake_apisix_payload(user=test_user)

    client.force_login(
        test_user, backend="mitol.apigateway.backends.ApisixRemoteUserBackend"
    )
    authenticate_mock = mocker.patch("django.contrib.auth.authenticate")

    response = client.get("/login", HTTP_X_USERINFO=payload)

    assert response.status_code == 302  # noqa: PLR2004
    authenticate_mock.assert_not_called()


@pytest.mark.usefixtures("_client_gateway")
def test_mismatched_user_logged_out_then_logged_in(client):
    """A session for a different user is replaced by the header's user"""
    session_user = SsoUserFactory.create()
    header_user = SsoUserFactory.create()
    payload, _ = generate_fake_apisix_payload(user=header_user)

    client.force_login(
        session_user, backend="mitol.apigateway.backends.ApisixRemoteUserBackend"
    )

    client.get("/login", HTTP_X_USERINFO=payload)

    assert client.session["_auth_user_id"] == str(header_user.pk)


@pytest.mark.usefixtures("_client_gateway")
def test_ambiguous_identity_leaves_request_anonymous(client, settings):
    """An ambiguous identity fails closed and logs out a non-matching session"""
    settings.MITOL_APIGATEWAY_USERINFO_EMAIL_FALLBACK = True

    exact_user = SsoUserFactory.create()
    UserFactory.create(global_id="", email=exact_user.email, username="legacy-username")
    session_user = SsoUserFactory.create()
    payload, _ = generate_fake_apisix_payload(
        extra={"sub": exact_user.global_id, "email": exact_user.email}
    )

    client.force_login(
        session_user, backend="mitol.apigateway.backends.ApisixRemoteUserBackend"
    )

    client.get("/login", HTTP_X_USERINFO=payload)

    assert "_auth_user_id" not in client.session


@pytest.mark.usefixtures("_client_gateway")
@pytest.mark.parametrize("cookie_enabled", [True, False])
def test_next_cookie_gated(client, settings, cookie_enabled):
    """The login next-URL cookie write follows the gate setting"""
    settings.MITOL_APIGATEWAY_SET_NEXT_COOKIE = cookie_enabled
    cookie_name = settings.MITOL_APIGATEWAY_LOGIN_NEXT_URL_COOKIE_NAME

    response = client.get("/login?next=/dashboard")

    if cookie_enabled:
        assert response.cookies[cookie_name].value == "/dashboard"
    else:
        assert cookie_name not in response.cookies
