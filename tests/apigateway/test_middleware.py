"""Test the regular Django middleware."""

import base64
import json

import faker
import pytest
from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib import auth
from django.contrib.auth import get_user_model
from django.http import HttpResponse, QueryDict
from mitol.apigateway.backends import ApisixRemoteUserBackend
from mitol.apigateway.middleware import ApisixUserMiddleware
from mitol.common.factories.defaults import SsoUserFactory

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


BACKEND = "mitol.apigateway.backends.ApisixRemoteUserBackend"


def encode_payload(user_info):
    """Encode userinfo the way the gateway does."""

    return base64.b64encode(json.dumps(user_info).encode()).decode()


def logged_in_request(user, payload):
    """Return a request whose session is already logged in as the user."""

    request = generate_apisix_request("request", payload)
    auth.login(request, user, backend=BACKEND)
    request.session.save()
    return request


@pytest.fixture
def apisix_backend(settings):
    """Use the APISIX backend, with userinfo updates off by default."""

    settings.AUTHENTICATION_BACKENDS = [BACKEND]
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = False
    return settings


@pytest.mark.parametrize("update_known_user", [False, True])
def test_middleware_keeps_session_for_same_user(
    mocker, apisix_backend, update_known_user
):
    """
    A session that already belongs to the header user is kept as is.

    RemoteUserMiddleware compares REMOTE_USER against USERNAME_FIELD. REMOTE_USER
    holds the gateway lookup field, so where the two differ it logs the session
    out and back in on every request.
    """
    apisix_backend.MITOL_APIGATEWAY_USERINFO_UPDATE = update_known_user
    test_user = SsoUserFactory.create()
    _, user_info = generate_fake_apisix_payload(user=test_user)
    user_info["email"] = FAKE.unique.email()
    request = logged_in_request(test_user, encode_payload(user_info))

    session_key = request.session.session_key
    csrf_token = request.META["CSRF_COOKIE"]
    last_login = User.objects.get(pk=test_user.pk).last_login

    authenticate = mocker.spy(auth, "authenticate")
    configure_user = mocker.spy(ApisixRemoteUserBackend, "configure_user")
    logout = mocker.spy(auth, "logout")
    login = mocker.spy(auth, "login")

    middleware = ApisixUserMiddleware(lambda req: HttpResponse())  # noqa: ARG005
    middleware.process_request(request)

    assert request.user.pk == test_user.pk
    assert request.session.session_key == session_key
    assert request.META["CSRF_COOKIE"] == csrf_token
    logout.assert_not_called()
    login.assert_not_called()
    authenticate.assert_called_once_with(
        request, remote_user=user_info[settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD]
    )
    configure_user.assert_called_once()
    assert configure_user.call_args.kwargs["created"] is False

    test_user.refresh_from_db()
    assert test_user.last_login == last_login
    if update_known_user:
        assert test_user.email == user_info["email"]
    else:
        assert test_user.email != user_info["email"]


class ReconcilingBackend(ApisixRemoteUserBackend):
    """
    Mimics a downstream backend that reconciles related data in configure_user.

    mitxonline's ApisixRemoteUserOrgBackend does this regardless of
    MITOL_APIGATEWAY_USERINFO_UPDATE.
    """

    reconciled = []

    def configure_user(self, request, user, *, created=True):
        """Configure the user, then record a reconcile."""
        user = super().configure_user(request, user, created=created)
        self.reconciled.append(user.pk)
        return user


def test_middleware_same_user_reconciles_every_request(apisix_backend):
    """With updates off, a subclass's configure_user still runs per request."""
    apisix_backend.AUTHENTICATION_BACKENDS = [
        f"{ReconcilingBackend.__module__}.ReconcilingBackend"
    ]
    ReconcilingBackend.reconciled = []
    test_user = SsoUserFactory.create()
    payload, _ = generate_fake_apisix_payload(user=test_user)
    request = generate_apisix_request("request", payload)
    auth.login(request, test_user, backend=apisix_backend.AUTHENTICATION_BACKENDS[0])
    request.session.save()
    session_key = request.session.session_key

    middleware = ApisixUserMiddleware(lambda req: HttpResponse())  # noqa: ARG005
    middleware.process_request(request)
    middleware.process_request(request)

    assert ReconcilingBackend.reconciled == [test_user.pk, test_user.pk]
    assert request.user.pk == test_user.pk
    assert request.session.session_key == session_key


def test_middleware_same_user_honors_lookup_field(mocker, apisix_backend):
    """The same-user check compares on MITOL_APIGATEWAY_USER_LOOKUP_FIELD."""
    apisix_backend.MITOL_APIGATEWAY_USER_LOOKUP_FIELD = "scim_external_id"
    test_user = SsoUserFactory.create(scim_external_id=FAKE.unique.uuid4())
    _, user_info = generate_fake_apisix_payload(user=test_user)
    user_info[settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD] = test_user.scim_external_id
    request = logged_in_request(test_user, encode_payload(user_info))
    session_key = request.session.session_key

    logout = mocker.spy(auth, "logout")

    middleware = ApisixUserMiddleware(lambda req: HttpResponse())  # noqa: ARG005
    middleware.process_request(request)

    logout.assert_not_called()
    assert request.user.pk == test_user.pk
    assert request.session.session_key == session_key


@pytest.mark.usefixtures("apisix_backend")
def test_middleware_switches_to_different_header_user():
    """A header for a different user replaces the session user."""
    session_user = SsoUserFactory.create()
    header_user = SsoUserFactory.create()
    payload, _ = generate_fake_apisix_payload(user=header_user)
    request = logged_in_request(session_user, payload)
    session_key = request.session.session_key

    middleware = ApisixUserMiddleware(lambda req: HttpResponse())  # noqa: ARG005
    middleware.process_request(request)

    assert request.user.pk == header_user.pk
    assert request.session.session_key != session_key


@pytest.mark.usefixtures("apisix_backend")
def test_middleware_same_user_deactivated_logs_out():
    """A session user the backend now rejects is logged out."""
    test_user = SsoUserFactory.create()
    payload, _ = generate_fake_apisix_payload(user=test_user)
    request = logged_in_request(test_user, payload)
    request.user.is_active = False
    request.user.save()

    middleware = ApisixUserMiddleware(lambda req: HttpResponse())  # noqa: ARG005
    middleware.process_request(request)

    assert request.user.is_anonymous


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@pytest.mark.usefixtures("apisix_backend")
async def test_middleware_aprocess_request():
    """aprocess_request runs the same header handling as process_request."""
    payload, user_info = generate_fake_apisix_payload()
    request = await sync_to_async(generate_apisix_request)("request", payload)

    middleware = ApisixUserMiddleware(lambda req: HttpResponse())  # noqa: ARG005
    await middleware.aprocess_request(request)

    id_field = settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD
    assert request.META["REMOTE_USER"] == user_info[id_field]
    assert request.user.global_id == user_info[id_field]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
@pytest.mark.usefixtures("apisix_backend")
async def test_middleware_async_call():
    """Under an async handler the middleware awaits the response and sets the cookie."""

    async def get_response(request):  # noqa: ARG001
        return HttpResponse()

    payload, user_info = generate_fake_apisix_payload()
    request = await sync_to_async(generate_apisix_request)("request", payload)
    request.GET = QueryDict("next=/somewhere")

    middleware = ApisixUserMiddleware(get_response)
    response = await middleware(request)

    assert isinstance(response, HttpResponse)
    assert response.cookies["next"].value == "/somewhere"
    id_field = settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD
    assert request.user.global_id == user_info[id_field]


@pytest.mark.parametrize("header", ["not base64 json", encode_payload(["a", "list"])])
@pytest.mark.usefixtures("apisix_backend")
def test_middleware_malformed_header(header):
    """A header that doesn't decode to a JSON object leaves the user anonymous."""
    request = generate_apisix_request("request", header)

    middleware = ApisixUserMiddleware(lambda req: HttpResponse())  # noqa: ARG005
    middleware.process_request(request)

    assert request.user.is_anonymous
