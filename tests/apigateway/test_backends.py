"""Tests for the API gateway authentication backends."""

import base64
import json

import faker
import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from main.utils import generate_apisix_request, generate_fake_apisix_payload
from mitol.apigateway.backends import (
    ApisixRemoteUserBackend,
    RemoteUserCustomFieldBackend,
)
from mitol.common.factories.defaults import SsoUserFactory

FAKE = faker.Faker()
User = get_user_model()


@pytest.mark.django_db
@pytest.mark.parametrize("override", [False, True])
@pytest.mark.parametrize("has_value", [False, True])
def test_configure_user_updates_fields(settings, override, has_value):
    """configure_user only overwrites a tuple-mapped field when allowed to."""
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


def test_settings_read_at_call_time(settings):
    """The backend's flags follow settings changed after it was created."""
    backend = ApisixRemoteUserBackend()

    settings.MITOL_APIGATEWAY_USER_LOOKUP_FIELD = "scim_external_id"
    settings.MITOL_APIGATEWAY_USERINFO_CREATE = False
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = True

    assert backend.lookup_field == "scim_external_id"
    assert backend.create_unknown_user is False
    assert backend.update_known_user is True

    settings.MITOL_APIGATEWAY_USER_LOOKUP_FIELD = "global_id"
    settings.MITOL_APIGATEWAY_USERINFO_CREATE = True
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = False

    assert backend.lookup_field == "global_id"
    assert backend.create_unknown_user is True
    assert backend.update_known_user is False


@pytest.mark.django_db
@pytest.mark.parametrize("create_unknown_user", [False, True])
def test_authenticate_honors_lookup_field(settings, create_unknown_user):
    """Existing users are found on MITOL_APIGATEWAY_USER_LOOKUP_FIELD."""
    settings.MITOL_APIGATEWAY_USER_LOOKUP_FIELD = "scim_external_id"
    settings.MITOL_APIGATEWAY_USERINFO_CREATE = create_unknown_user
    test_user = SsoUserFactory.create(scim_external_id=FAKE.unique.uuid4())
    payload, _ = generate_fake_apisix_payload(user=test_user)
    request = generate_apisix_request("request", payload)

    result = ApisixRemoteUserBackend().authenticate(
        request, remote_user=test_user.scim_external_id
    )

    assert result == test_user
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_authenticate_unknown_user_without_create(settings):
    """With creation off, an unknown remote user doesn't authenticate."""
    settings.MITOL_APIGATEWAY_USERINFO_CREATE = False
    payload, user_info = generate_fake_apisix_payload()
    request = generate_apisix_request("request", payload)

    result = ApisixRemoteUserBackend().authenticate(
        request, remote_user=user_info[settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD]
    )

    assert result is None
    assert not User.objects.exists()


@pytest.mark.django_db
def test_authenticate_channels_scope():
    """A Channels scope dict, which has no user attribute, still authenticates."""
    test_user = SsoUserFactory.create()
    payload, _ = generate_fake_apisix_payload(user=test_user)
    scope = generate_apisix_request("scope", payload)

    result = ApisixRemoteUserBackend().authenticate(
        scope, remote_user=test_user.global_id
    )

    assert result == test_user


@pytest.mark.django_db
def test_authenticate_same_user_configures_without_lookup(
    mocker, settings, django_assert_num_queries
):
    """
    A request user matching the remote user is reused but still configured.
    """
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = False
    test_user = SsoUserFactory.create()
    payload, _ = generate_fake_apisix_payload(user=test_user)
    request = generate_apisix_request("request", payload)
    request.user = test_user
    backend = ApisixRemoteUserBackend()
    configure_user = mocker.spy(backend, "configure_user")

    # Only the savepoint from transaction.atomic(), no user lookup.
    with django_assert_num_queries(2):
        result = backend.authenticate(request, remote_user=test_user.global_id)

    assert result is test_user
    configure_user.assert_called_once_with(request, test_user, created=False)


class KeywordCreatedBackend(RemoteUserCustomFieldBackend):
    """Minimal subclass whose configure_user takes created as keyword-only."""

    lookup_field = "global_id"
    create_unknown_user = False

    def configure_user(self, request, user, *, created=True):  # noqa: ARG002
        """Record the call."""
        user.configured_as_created = created
        return user


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_base_aauthenticate_delegates_to_authenticate():
    """RemoteUserCustomFieldBackend.aauthenticate runs the sync path."""
    test_user = await sync_to_async(SsoUserFactory.create)()
    payload, _ = generate_fake_apisix_payload(user=test_user)
    request = await sync_to_async(generate_apisix_request)("request", payload)

    result = await KeywordCreatedBackend().aauthenticate(
        request, remote_user=test_user.global_id
    )

    assert result.pk == test_user.pk
    assert result.configured_as_created is False
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
