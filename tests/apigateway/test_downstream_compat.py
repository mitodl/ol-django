"""Compatibility checks for downstream consumers (mitxonline usage patterns)."""

import pytest
from mitol.apigateway.api import decode_x_header
from mitol.apigateway.backends import ApisixRemoteUserBackend
from mitol.common import envs

from testapp.main.utils import generate_apisix_request, generate_fake_apisix_payload

pytestmark = pytest.mark.django_db


def test_env_registration_no_collision():
    """The package must not register env ALLOWED_REDIRECT_HOSTS (consumers do)"""
    # mitxonline main/settings.py:110-114 pattern; raises ValueError if the
    # package had already registered this env name
    assert "ALLOWED_REDIRECT_HOSTS" not in envs.env._configured_vars  # noqa: SLF001
    assert "MITOL_ALLOWED_REDIRECT_HOSTS" in envs.env._configured_vars  # noqa: SLF001


def test_mitxonline_backend_subclass_signature():
    """Keep mitxonline's ApisixRemoteUserOrgBackend subclass pattern working"""
    calls = []

    class ApisixRemoteUserOrgBackend(ApisixRemoteUserBackend):
        # exact signature from mitxonline
        # authentication/backends/apisix_remote_user_org.py
        def configure_user(self, request, user, *args, created=True):
            user = super().configure_user(request, user, *args, created=created)
            apisix_header = decode_x_header(request)
            org_uuids = []
            if apisix_header and "organization" in apisix_header:
                org_uuids = [
                    apisix_header["organization"][org]["id"]
                    for org in apisix_header["organization"]
                ]
            calls.append((created, org_uuids))
            return user

    payload, user_info = generate_fake_apisix_payload(
        extra={"organization": {"org1": {"id": "uuid-1"}}}
    )
    request = generate_apisix_request("request", payload)

    backend = ApisixRemoteUserOrgBackend()
    user = backend.authenticate(request, remote_user=user_info["sub"])

    assert user is not None
    assert calls == [(True, ["uuid-1"])]

    # second request: same-user resolution still calls configure_user (dirty-checked)
    request = generate_apisix_request("request", payload)
    user = backend.authenticate(request, remote_user=user_info["sub"])
    assert user is not None
    assert calls[-1] == (False, ["uuid-1"])


def test_mitxonline_tuple_map_form(settings):
    """Support mitxonline's MODEL_MAP tuple form and empty additional_models"""
    settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP = {
        "user_fields": {
            "preferred_username": "username",
            "email": "email",
            "sub": "global_id",
            "name": ("first_name", False),
        },
        "additional_models": {},
    }
    payload, user_info = generate_fake_apisix_payload()
    request = generate_apisix_request("request", payload)

    backend = ApisixRemoteUserBackend()
    user = backend.authenticate(request, remote_user=user_info["sub"])

    assert user is not None
    assert user.email == user_info["email"]
