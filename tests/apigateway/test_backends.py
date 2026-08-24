import base64
import json

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


@pytest.mark.django_db
def test_resolve_user_adopts_unlinked_account(settings):
    """A pre-gateway account is adopted by email, not duplicated."""
    settings.MITOL_APIGATEWAY_ADOPT_UNLINKED_USER_BY = "email"

    legacy = SsoUserFactory.create()
    legacy.global_id = ""
    legacy.save()

    payload, user_info = generate_fake_apisix_payload()
    user_info["email"] = legacy.email
    payload = base64.b64encode(json.dumps(user_info).encode()).decode()
    request = generate_apisix_request("request", payload)

    backend = ApisixRemoteUserBackend()
    backend.adopt_unlinked_user_by = "email"
    user, created = backend.resolve_user(
        request, user_info[settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD]
    )

    assert created is False
    assert user.pk == legacy.pk
    # The lookup field is stamped, so the next request matches directly.
    assert user.global_id == user_info[settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD]
    assert User.objects.filter(email=legacy.email).count() == 1


@pytest.mark.django_db
def test_resolve_user_creates_when_adoption_is_off(settings):
    """With adoption off, an unmatched remote id creates a new account."""
    settings.MITOL_APIGATEWAY_ADOPT_UNLINKED_USER_BY = None

    legacy = SsoUserFactory.create()
    legacy.global_id = ""
    legacy.save()

    payload, user_info = generate_fake_apisix_payload()
    user_info["email"] = legacy.email
    payload = base64.b64encode(json.dumps(user_info).encode()).decode()
    request = generate_apisix_request("request", payload)

    backend = ApisixRemoteUserBackend()
    backend.adopt_unlinked_user_by = None
    user, created = backend.resolve_user(
        request, user_info[settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD]
    )

    assert created is True
    assert user.pk != legacy.pk


@pytest.mark.django_db
def test_resolve_user_refuses_ambiguous_identity(settings):
    """More than one match returns None rather than picking one."""
    settings.MITOL_APIGATEWAY_ADOPT_UNLINKED_USER_BY = "email"

    payload, user_info = generate_fake_apisix_payload()
    global_id = user_info[settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD]

    matches_by_global_id = SsoUserFactory.create()
    matches_by_global_id.global_id = global_id
    matches_by_global_id.save()

    matches_by_email = SsoUserFactory.create()
    matches_by_email.global_id = ""
    matches_by_email.email = user_info["email"]
    matches_by_email.save()

    request = generate_apisix_request("request", payload)

    backend = ApisixRemoteUserBackend()
    backend.adopt_unlinked_user_by = "email"
    user, created = backend.resolve_user(request, global_id)

    assert user is None
    assert created is False


@pytest.mark.django_db
def test_configure_user_skips_write_when_unchanged(settings, mocker):
    """An already-current user row is not rewritten on every request."""
    settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP = {
        "user_fields": {
            "email": "email",
            "preferred_username": "username",
        },
        "additional_models": {},
    }
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = True

    test_user = SsoUserFactory.create()
    payload, _ = generate_fake_apisix_payload(user=test_user)
    request = generate_apisix_request("request", payload)

    save = mocker.patch.object(User, "save")

    backend = ApisixRemoteUserBackend()
    backend.configure_user(request, test_user, created=False)

    save.assert_not_called()


@pytest.mark.django_db
def test_configure_user_writes_only_changed_fields(settings, mocker):
    """A changed field is saved, and only that field."""
    settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP = {
        "user_fields": {
            "email": "email",
            "preferred_username": "username",
        },
        "additional_models": {},
    }
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = True

    test_user = SsoUserFactory.create()
    payload, _ = generate_fake_apisix_payload(user=test_user)
    request = generate_apisix_request("request", payload)

    test_user.email = "stale@example.com"
    save = mocker.patch.object(User, "save")

    backend = ApisixRemoteUserBackend()
    backend.configure_user(request, test_user, created=False)

    save.assert_called_once_with(update_fields=["email"])


@pytest.mark.django_db
def test_resolve_user_adopts_account_whose_lookup_field_is_null(settings):
    """
    Adoption matches a NULL lookup field, not only an empty string.

    Apps differ on how "no value yet" is stored: UserGlobalIdMixin declares
    blank=True default="", mit-learn and mitxonline declare null=True. A single
    `__in=("", None)` cannot cover both - SQL never matches NULL through IN, and
    Django drops the None, so the filter silently matched nothing for exactly
    the nullable apps this feature exists to serve.

    testapp's global_id is not nullable, so this drives the check through the
    configurable lookup field on a column that is.
    """
    settings.MITOL_APIGATEWAY_USER_LOOKUP_FIELD = "scim_external_id"
    settings.MITOL_APIGATEWAY_ADOPT_UNLINKED_USER_BY = "email"
    settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP = {
        "user_fields": {
            "email": "email",
            "preferred_username": "username",
            "sub": "scim_external_id",
        },
        "additional_models": {},
    }

    legacy = SsoUserFactory.create()
    legacy.scim_external_id = None
    legacy.save()
    assert User.objects.filter(pk=legacy.pk, scim_external_id__isnull=True).exists()

    payload, user_info = generate_fake_apisix_payload()
    user_info["email"] = legacy.email
    payload = base64.b64encode(json.dumps(user_info).encode()).decode()
    request = generate_apisix_request("request", payload)

    backend = ApisixRemoteUserBackend()
    backend.lookup_field = "scim_external_id"
    backend.adopt_unlinked_user_by = "email"

    remote_id = user_info[settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD]
    user, created = backend.resolve_user(request, remote_id)

    assert created is False
    assert user.pk == legacy.pk
    assert user.scim_external_id == remote_id
    assert User.objects.filter(email=legacy.email).count() == 1
