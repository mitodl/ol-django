"""Tests for the API gateway authentication backends."""

import base64
import json

import faker
import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import is_password_usable
from django.db import connection
from django.test.utils import CaptureQueriesContext
from main.utils import generate_apisix_request, generate_fake_apisix_payload
from mitol.apigateway.backends import (
    ApisixRemoteUserBackend,
    RemoteUserCustomFieldBackend,
)
from mitol.common.factories.defaults import SsoUserFactory
from users.models import UserProfile

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


def _userinfo_request(user_info):
    """Build a request carrying user_info as the encoded userinfo header."""
    payload = base64.b64encode(json.dumps(user_info).encode()).decode()
    return generate_apisix_request("request", payload)


def _user_updates(queries):
    """Return the UPDATE statements on the user table."""
    table = User._meta.db_table  # noqa: SLF001
    return [q["sql"] for q in queries if q["sql"].startswith(f'UPDATE "{table}"')]


@pytest.mark.django_db
def test_configure_user_skips_absent_header_keys(settings):
    """A mapped key missing from the userinfo leaves the field alone."""
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = True
    test_user = SsoUserFactory.create()
    email = test_user.email
    request = _userinfo_request(
        {"sub": test_user.global_id, "preferred_username": "renamed"}
    )

    ApisixRemoteUserBackend().configure_user(request, test_user, created=False)

    test_user.refresh_from_db()
    assert test_user.email == email
    assert test_user.username == "renamed"


@pytest.mark.django_db
def test_configure_user_writes_nothing_when_unchanged(settings):
    """Headers matching the stored user don't write the row."""
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = True
    test_user = SsoUserFactory.create()
    payload, _ = generate_fake_apisix_payload(user=test_user)
    request = generate_apisix_request("request", payload)

    with CaptureQueriesContext(connection) as queries:
        ApisixRemoteUserBackend().configure_user(request, test_user, created=False)

    assert _user_updates(queries.captured_queries) == []


@pytest.mark.django_db
def test_configure_user_updates_only_changed_columns(settings):
    """A changed header writes that column and updated_on, nothing else."""
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = True
    test_user = SsoUserFactory.create()
    updated_on = test_user.updated_on
    _, user_info = generate_fake_apisix_payload(user=test_user)
    request = _userinfo_request({**user_info, "email": "changed@example.com"})

    with CaptureQueriesContext(connection) as queries:
        ApisixRemoteUserBackend().configure_user(request, test_user, created=False)

    [update] = _user_updates(queries.captured_queries)
    assert '"email"' in update
    assert '"updated_on"' in update
    assert '"username"' not in update
    assert '"first_name"' not in update
    test_user.refresh_from_db()
    assert test_user.email == "changed@example.com"
    assert test_user.updated_on > updated_on


@pytest.mark.django_db
def test_authenticate_creates_user_from_header_values(settings):
    """A new user is inserted with its mapped values, active, without a password."""
    settings.MITOL_APIGATEWAY_USERINFO_CREATE = True
    _, user_info = generate_fake_apisix_payload()
    request = _userinfo_request(user_info)

    result = ApisixRemoteUserBackend().authenticate(
        request, remote_user=user_info["sub"]
    )

    user = User.objects.get(global_id=user_info["sub"])
    assert result == user
    assert user.username == user_info["preferred_username"]
    assert user.email == user_info["email"]
    assert user.is_active
    assert not user.has_usable_password()


@pytest.mark.django_db
def test_authenticate_creates_user_beside_a_blank_username(settings):
    """
    Creating a user doesn't insert placeholder values first.

    An insert with username="" would collide with an existing blank username,
    as two concurrent first logins collide with each other.
    """
    settings.MITOL_APIGATEWAY_USERINFO_CREATE = True
    SsoUserFactory.create(username="")
    _, user_info = generate_fake_apisix_payload()
    request = _userinfo_request(user_info)

    result = ApisixRemoteUserBackend().authenticate(
        request, remote_user=user_info["sub"]
    )

    assert result is not None
    assert result.username == user_info["preferred_username"]


@pytest.mark.django_db
def test_authenticate_refuses_unknown_identity_with_inactive_email(settings, caplog):
    """An unknown identity with an inactive account's email gets no new account."""
    settings.MITOL_APIGATEWAY_USERINFO_CREATE = True
    inactive = SsoUserFactory.create(is_active=False, email="Someone@Example.com")
    _, user_info = generate_fake_apisix_payload()
    request = _userinfo_request({**user_info, "email": "someone@example.com"})

    result = ApisixRemoteUserBackend().authenticate(
        request, remote_user=user_info["sub"]
    )

    assert result is None
    assert User.objects.count() == 1
    assert "refused_inactive_email_match" in caplog.text
    assert f"inactive_user_id={inactive.pk}" in caplog.text


@pytest.mark.django_db
def test_authenticate_known_identity_unaffected_by_inactive_email(settings):
    """The inactive-email refusal applies only to identities with no user."""
    settings.MITOL_APIGATEWAY_USERINFO_CREATE = True
    SsoUserFactory.create(
        is_active=False, email="someone@example.com", username="retired"
    )
    test_user = SsoUserFactory.create(email="someone@example.com")
    payload, _ = generate_fake_apisix_payload(user=test_user)
    request = generate_apisix_request("request", payload)

    result = ApisixRemoteUserBackend().authenticate(
        request, remote_user=test_user.global_id
    )

    assert result == test_user


@pytest.fixture
def profile_map(settings):
    """Map country_code and email_optin onto users.UserProfile."""
    settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP = {
        **settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP,
        "additional_models": {
            "users.UserProfile": [
                ("country_code", "country_code", ""),
                ("email_optin", "email_optin", False),
            ],
        },
    }
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = True


@pytest.mark.django_db
@pytest.mark.usefixtures("profile_map")
def test_configure_user_creates_additional_model_with_defaults():
    """An absent key takes the mapped default when the related row is created."""
    test_user = SsoUserFactory.create()
    _, user_info = generate_fake_apisix_payload(user=test_user)
    request = _userinfo_request({**user_info, "country_code": "US"})

    ApisixRemoteUserBackend().configure_user(request, test_user, created=False)

    profile = UserProfile.objects.get(user=test_user)
    assert profile.country_code == "US"
    assert profile.email_optin is False


@pytest.mark.django_db
@pytest.mark.usefixtures("profile_map")
def test_configure_user_additional_model_keeps_absent_and_unchanged():
    """An existing related row isn't written for absent or matching keys."""
    test_user = SsoUserFactory.create()
    UserProfile.objects.create(user=test_user, country_code="US", email_optin=True)
    _, user_info = generate_fake_apisix_payload(user=test_user)
    request = _userinfo_request({**user_info, "country_code": "US"})

    with CaptureQueriesContext(connection) as queries:
        ApisixRemoteUserBackend().configure_user(request, test_user, created=False)

    table = UserProfile._meta.db_table  # noqa: SLF001
    assert not [
        q for q in queries.captured_queries if q["sql"].startswith(f'UPDATE "{table}"')
    ]
    assert UserProfile.objects.get(user=test_user).email_optin is True


@pytest.mark.django_db
@pytest.mark.usefixtures("profile_map")
def test_configure_user_additional_model_updates_changed_field():
    """A changed key on an existing related row writes only that field."""
    test_user = SsoUserFactory.create()
    UserProfile.objects.create(user=test_user, country_code="US", email_optin=True)
    _, user_info = generate_fake_apisix_payload(user=test_user)
    request = _userinfo_request({**user_info, "country_code": "CA"})

    ApisixRemoteUserBackend().configure_user(request, test_user, created=False)

    profile = UserProfile.objects.get(user=test_user)
    assert profile.country_code == "CA"
    assert profile.email_optin is True


def _display_name(user):
    """Join the name columns, as a settable name property's getter would."""
    return f"{user.first_name} {user.last_name}"


def _set_display_name(user, value):
    """Split a full name into the name columns, normalizing whitespace."""
    user.first_name, _, user.last_name = " ".join(value.split()).partition(" ")


@pytest.mark.django_db
def test_configure_user_settable_property_saves_its_columns(settings, monkeypatch):
    """
    A mapped settable property saves the columns it changed, once.

    The getter normalizes whitespace, so it never returns the header value
    as given; a second request with the same header must not write again.
    """
    monkeypatch.setattr(
        User, "display_name", property(_display_name, _set_display_name), raising=False
    )
    settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP = {
        "user_fields": {"name": "display_name"},
        "additional_models": {},
    }
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = True
    test_user = SsoUserFactory.create(first_name="Old", last_name="Name")
    request = _userinfo_request({"sub": test_user.global_id, "name": "Mary  Smith"})
    backend = ApisixRemoteUserBackend()

    with CaptureQueriesContext(connection) as first:
        backend.configure_user(request, test_user, created=False)
    with CaptureQueriesContext(connection) as second:
        backend.configure_user(request, test_user, created=False)

    [update] = _user_updates(first.captured_queries)
    assert '"first_name"' in update
    assert '"last_name"' in update
    assert '"email"' not in update
    assert _user_updates(second.captured_queries) == []
    test_user.refresh_from_db()
    assert (test_user.first_name, test_user.last_name) == ("Mary", "Smith")


@pytest.mark.django_db
def test_authenticate_creates_user_when_an_active_account_shares_the_email(settings):
    """An inactive match is not refused when an active account has the email too."""
    settings.MITOL_APIGATEWAY_USERINFO_CREATE = True
    SsoUserFactory.create(
        is_active=False, email="someone@example.com", username="retired"
    )
    SsoUserFactory.create(email="someone@example.com", username="current")
    _, user_info = generate_fake_apisix_payload()
    request = _userinfo_request({**user_info, "email": "someone@example.com"})

    result = ApisixRemoteUserBackend().authenticate(
        request, remote_user=user_info["sub"]
    )

    assert result is not None
    assert result.global_id == user_info["sub"]


@pytest.mark.django_db
def test_new_user_defaults_are_active_without_a_usable_password():
    """A gateway-created user starts active, with an unusable password."""
    _, user_info = generate_fake_apisix_payload()
    request = _userinfo_request(user_info)

    defaults = ApisixRemoteUserBackend().new_user_defaults(request)

    assert defaults["is_active"] is True
    assert not is_password_usable(defaults["password"])
    assert defaults["username"] == user_info["preferred_username"]
    assert "global_id" not in defaults
