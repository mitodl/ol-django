import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from main.utils import generate_apisix_request, generate_fake_apisix_payload
from mitol.apigateway.backends import ApisixRemoteUserBackend
from mitol.common.factories.defaults import SsoUserFactory

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.parametrize("override", [False, True])
@pytest.mark.parametrize("has_value", [False, True])
def test_configure_user_updates_fields(settings, override, has_value):
    # Mock settings
    id_field = settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD
    settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP = {
        "user_fields": {
            "email": ("email", override),
            "preferred_username": "username",
        },
        "additional_models": {},
    }
    settings.MITOL_APIGATEWAY_USERINFO_CREATE = True
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = True

    # Create user and request
    test_user = SsoUserFactory.create()

    payload, user_info = generate_fake_apisix_payload(user=test_user)
    assert test_user.email == user_info.get("email")
    request = generate_apisix_request("request", payload)
    if has_value:
        test_user.email = "updated@email.com"
    else:
        test_user.email = User._meta.get_field("email").get_default()  # noqa: SLF001

    test_user.save()

    backend = ApisixRemoteUserBackend()
    backend.configure_user(request, test_user, created=True)
    test_user = User.objects.get(global_id=user_info.get(id_field))
    if override or not has_value:
        assert test_user.email == user_info.get("email")
    else:
        # If not overriding, the email should remain unchanged
        assert test_user.email == "updated@email.com"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_aauthenticate_existing_user():
    """Async authenticate should resolve an existing user, matching authenticate()."""
    test_user = await sync_to_async(SsoUserFactory.create)()
    payload, _ = generate_fake_apisix_payload(user=test_user)
    request = await sync_to_async(generate_apisix_request)("request", payload)

    backend = ApisixRemoteUserBackend()
    result = await backend.aauthenticate(request, remote_user=test_user.global_id)

    assert result is not None
    assert result.global_id == test_user.global_id


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_aauthenticate_unknown_remote_user():
    """Async authenticate should return None when there's no remote_user."""
    backend = ApisixRemoteUserBackend()
    result = await backend.aauthenticate(None, remote_user=None)

    assert result is None
