"""Test the regular Django middleware."""

import faker
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from mitol.apigateway.middleware import ApisixUserMiddleware

from testapp.main.factories import SsoUserFactory
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
