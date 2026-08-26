"""Tests for the API gateway authentication backends."""

import datetime
import json
from base64 import b64encode

import pytest
from asgiref.sync import sync_to_async
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from main.utils import generate_apisix_request, generate_fake_apisix_payload
from mitol.apigateway.backends import ApisixRemoteUserBackend
from mitol.common.factories.defaults import SsoUserFactory, UserFactory

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.mark.django_db
@pytest.mark.parametrize("override", [False, True])
@pytest.mark.parametrize("has_value", [False, True])
def test_configure_user_updates_fields(settings, override, has_value):
    """configure_user applies the field map, honoring the tuple override flag"""
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


@pytest.fixture
def _apisix_backend(settings):
    """Use only the APISIX backend."""
    settings.AUTHENTICATION_BACKENDS = [
        "mitol.apigateway.backends.ApisixRemoteUserBackend",
    ]


def _authenticate(payload, user_info):
    """Authenticate a generated request through the APISIX backend."""
    request = generate_apisix_request("request", payload)
    backend = ApisixRemoteUserBackend()
    return backend.authenticate(
        request, remote_user=user_info[settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD]
    )


@pytest.mark.usefixtures("_apisix_backend")
@pytest.mark.parametrize("update_enabled", [True, False])
def test_email_fallback_backfills_lookup_field(settings, update_enabled):
    """A user matched by email gets the lookup field backfilled despite updates off"""
    settings.MITOL_APIGATEWAY_USERINFO_EMAIL_FALLBACK = True
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = update_enabled

    legacy_user = UserFactory.create(global_id="")
    payload, user_info = generate_fake_apisix_payload(
        extra={"email": legacy_user.email}
    )

    result = _authenticate(payload, user_info)

    assert result is not None
    assert result.pk == legacy_user.pk

    legacy_user.refresh_from_db()
    assert legacy_user.global_id == user_info["sub"]


@pytest.mark.usefixtures("_apisix_backend")
def test_email_fallback_disabled_ignores_email_match(settings):
    """Without the fallback, an email match is ignored and a new user is created"""
    settings.MITOL_APIGATEWAY_USERINFO_EMAIL_FALLBACK = False

    legacy_user = UserFactory.create(global_id="")
    payload, user_info = generate_fake_apisix_payload(
        extra={"email": legacy_user.email}
    )

    result = _authenticate(payload, user_info)

    assert result is not None
    assert result.pk != legacy_user.pk

    legacy_user.refresh_from_db()
    assert legacy_user.global_id == ""


@pytest.mark.usefixtures("_apisix_backend")
def test_email_fallback_ambiguous_fails_closed(settings):
    """An ambiguous identity match resolves to no user, and nothing is written"""
    settings.MITOL_APIGATEWAY_USERINFO_EMAIL_FALLBACK = True

    exact_user = SsoUserFactory.create()
    legacy_user = UserFactory.create(global_id="", email="legacy@example.com")

    payload, user_info = generate_fake_apisix_payload(
        extra={"sub": exact_user.global_id, "email": legacy_user.email}
    )

    result = _authenticate(payload, user_info)

    assert result is None

    legacy_user.refresh_from_db()
    exact_user_email = exact_user.email
    exact_user.refresh_from_db()
    assert legacy_user.global_id == ""
    assert exact_user.email == exact_user_email


@pytest.mark.usefixtures("_apisix_backend")
def test_configure_user_dirty_skip(mocker):
    """A sync with unchanged data saves nothing but still runs the hooks"""
    test_user = SsoUserFactory.create()
    payload, user_info = generate_fake_apisix_payload(user=test_user)

    save_spy = mocker.spy(User, "save")

    result = _authenticate(payload, user_info)

    assert result is not None
    assert result.pk == test_user.pk
    save_spy.assert_not_called()


@pytest.mark.usefixtures("_apisix_backend")
def test_configure_user_update_fields_and_updated_on():
    """A changed field is saved with update_fields, bumping updated_on"""
    test_user = SsoUserFactory.create()
    backdated = test_user.updated_on - datetime.timedelta(days=1)
    User.objects.filter(pk=test_user.pk).update(updated_on=backdated)

    payload, user_info = generate_fake_apisix_payload(
        user=test_user, extra={"email": "changed@example.com"}
    )

    result = _authenticate(payload, user_info)

    assert result is not None
    test_user.refresh_from_db()
    assert test_user.email == "changed@example.com"
    assert test_user.updated_on > backdated


@pytest.mark.usefixtures("_apisix_backend")
def test_configure_user_missing_header_key_skipped(settings):
    """Fields whose header key is absent are left alone, not nulled out"""
    test_user = SsoUserFactory.create()
    user_info = {settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD: test_user.global_id}
    payload = b64encode(json.dumps(user_info).encode()).decode()

    result = _authenticate(payload, user_info)

    assert result is not None
    test_user.refresh_from_db()
    assert test_user.email
    assert test_user.username


@pytest.mark.usefixtures("_apisix_backend")
def test_new_user_unusable_password_and_active():
    """Newly created gateway users get an unusable password and are active"""
    payload, user_info = generate_fake_apisix_payload()

    result = _authenticate(payload, user_info)

    assert result is not None
    assert result.is_active
    assert not result.has_usable_password()


@pytest.mark.usefixtures("_apisix_backend")
@pytest.mark.parametrize("create_enabled", [True, False])
@pytest.mark.parametrize("update_enabled", [True, False])
@pytest.mark.parametrize("known_user", [True, False])
def test_create_update_flag_matrix(
    settings, create_enabled, update_enabled, known_user
):
    """The CREATE/UPDATE flags are respected at call time"""
    settings.MITOL_APIGATEWAY_USERINFO_CREATE = create_enabled
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = update_enabled

    test_user = SsoUserFactory.create() if known_user else None
    payload, user_info = generate_fake_apisix_payload(
        user=test_user, extra={"email": "changed@example.com"}
    )

    result = _authenticate(payload, user_info)

    if known_user:
        assert result is not None
        test_user.refresh_from_db()
        if update_enabled:
            assert test_user.email == "changed@example.com"
        else:
            assert test_user.email != "changed@example.com"
    elif create_enabled:
        assert result is not None
        assert result.email == "changed@example.com"
    else:
        assert result is None
        assert not User.objects.filter(global_id=user_info["sub"]).exists()


@pytest.mark.usefixtures("_apisix_backend")
def test_additional_models_dirty_check(settings, mocker):
    """additional_models rows are created once and only saved when dirty"""
    UserProfile = apps.get_model("users.UserProfile")

    settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP = {
        "user_fields": dict(
            settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP["user_fields"]
        ),
        "additional_models": {
            "users.UserProfile": [
                ("name", "name", ""),
                ("emailOptIn", "email_optin", False),
            ],
        },
    }

    payload, user_info = generate_fake_apisix_payload(extra={"emailOptIn": True})
    result = _authenticate(payload, user_info)

    profile = UserProfile.objects.get(user=result)
    assert profile.name == user_info["name"]
    assert profile.email_optin is True

    # clean second sync: no profile save
    profile_save_spy = mocker.spy(UserProfile, "save")
    _authenticate(payload, user_info)
    profile_save_spy.assert_not_called()

    # changed header value: targeted save
    payload, user_info = generate_fake_apisix_payload(
        extra={**user_info, "emailOptIn": False}
    )
    _authenticate(payload, user_info)
    profile.refresh_from_db()
    assert profile.email_optin is False


@pytest.mark.usefixtures("_apisix_backend")
def test_sync_hooks_called(settings, mocker):
    """Sync hooks run on create and update, but not when updates are disabled"""
    settings.MITOL_APIGATEWAY_USERINFO_SYNC_HOOKS = ["main.hooks.record_user_sync"]
    hook = mocker.patch("main.hooks.record_user_sync")

    payload, user_info = generate_fake_apisix_payload()
    result = _authenticate(payload, user_info)

    hook.assert_called_once()
    assert hook.call_args.kwargs["created"] is True
    assert hook.call_args.kwargs["user"] == result

    hook.reset_mock()
    _authenticate(payload, user_info)
    hook.assert_called_once()
    assert hook.call_args.kwargs["created"] is False

    hook.reset_mock()
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = False
    _authenticate(payload, user_info)
    hook.assert_not_called()


@pytest.mark.usefixtures("_apisix_backend")
def test_sync_hook_failure_rolls_back(settings, mocker):
    """A hook exception makes authenticate fail closed and rolls back the sync"""
    settings.MITOL_APIGATEWAY_USERINFO_SYNC_HOOKS = ["main.hooks.record_user_sync"]
    mocker.patch("main.hooks.record_user_sync", side_effect=ValueError("boom"))

    test_user = SsoUserFactory.create()
    payload, user_info = generate_fake_apisix_payload(
        user=test_user, extra={"email": "changed@example.com"}
    )

    result = _authenticate(payload, user_info)

    assert result is None
    test_user.refresh_from_db()
    assert test_user.email != "changed@example.com"
