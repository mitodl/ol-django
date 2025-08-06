

from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory, override_settings

from main.utils import generate_apisix_request, generate_fake_apisix_payload
from mitol.apigateway.backends import ApisixRemoteUserBackend
from mitol.common.factories.defaults import SsoUserFactory

User = get_user_model()

@pytest.mark.django_db
def test_configure_user_updates_fields(settings):
    # Mock settings
    id_field = settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD
    settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP = {
        "user_fields": {
            "name": ("name", False),
            "email": ("email", True),
        },
        "additional_models": {},
    }
    settings.MITOL_APIGATEWAY_USERINFO_CREATE = True
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = True

    # Create user and request
    test_user = SsoUserFactory.create()
    payload, user_info = generate_fake_apisix_payload(user=test_user)
    request = generate_apisix_request("request", payload)

    # Patch decode_x_header to return test headers
    with mock.patch("mitol.apigateway.api.decode_x_header") as decode_mock:
        decode_mock.return_value = {"X-Name": "Test User", "X-Email": "test@example.com"}
        backend = ApisixRemoteUserBackend()
        backend.configure_user(request, test_user, created=True)

    test_user = User.objects.get(global_id=user_info.get(id_field))
    assert test_user.name == "Test User"
    assert test_user.email == "test@example.com"