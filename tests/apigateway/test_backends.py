import base64
import importlib
import json

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from main.utils import generate_apisix_request, generate_fake_apisix_payload
from mitol.apigateway import backends as backends_module
from mitol.apigateway.backends import (
    ApisixRemoteUserBackend,
    RemoteUserCustomFieldBackend,
)
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
    legacy.global_id = None
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
    legacy.global_id = None
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
    matches_by_email.global_id = None
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


@pytest.mark.django_db
def test_resolve_user_yields_to_a_concurrent_create(settings, mocker):
    """
    A row that appears between our get and our insert is resolved, not duplicated.

    resolve_user does its own get so it can offer the adoption branch, which
    reopens the window get_or_create exists to close. Creation has to go back
    through get_or_create: it retries the get inside a savepoint on
    IntegrityError, so the loser of the race returns the winner's row instead
    of duplicating it (no unique constraint) or raising (unique constraint).
    """
    settings.MITOL_APIGATEWAY_ADOPT_UNLINKED_USER_BY = None

    winner = SsoUserFactory.create()
    payload, _ = generate_fake_apisix_payload(user=winner)
    request = generate_apisix_request("request", payload)

    # Miss on resolve_user's own get, as a concurrent insert landing just after
    # it would look, then behave normally.
    real_get = QuerySet.get
    calls = {"n": 0}

    def get_missing_once(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise User.DoesNotExist
        return real_get(self, *args, **kwargs)

    mocker.patch.object(QuerySet, "get", get_missing_once)

    backend = ApisixRemoteUserBackend()
    backend.adopt_unlinked_user_by = None
    user, created = backend.resolve_user(request, winner.global_id)

    assert created is False
    assert user.pk == winner.pk
    assert User.objects.filter(global_id=winner.global_id).count() == 1


class _GlobalIdBackend(RemoteUserCustomFieldBackend):
    """Concrete subclass, to exercise the base class's own aauthenticate."""

    lookup_field = "global_id"
    create_unknown_user = True


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_base_aauthenticate_configures_user():
    """
    RemoteUserCustomFieldBackend.aauthenticate works without an override.

    Nothing exercised this before: ApisixRemoteUserBackend overrides
    aauthenticate and delegates to the sync path, so the base class's async
    path was dead in the test suite while remaining public API. It called
    self.aconfigure_user, which RemoteUserBackend only grew in Django 5.2 -
    an AttributeError on every version this package claims to support below
    that.
    """
    test_user = await sync_to_async(SsoUserFactory.create)()
    payload, _ = generate_fake_apisix_payload(user=test_user)
    request = await sync_to_async(generate_apisix_request)("request", payload)

    backend = _GlobalIdBackend()
    result = await backend.aauthenticate(request, remote_user=test_user.global_id)

    assert result is not None
    assert result.global_id == test_user.global_id


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_aconfigure_user_shim_passes_created_as_a_keyword(settings):
    """
    The shim honours ApisixRemoteUserBackend's keyword-only `created`.

    Django 5.2's own aconfigure_user passes created positionally, which that
    signature rejects, so the shim is load-bearing on 5.2 too - not only on the
    versions missing the method.
    """
    settings.MITOL_APIGATEWAY_USERINFO_MODEL_MAP = {
        "user_fields": {"email": "email", "preferred_username": "username"},
        "additional_models": {},
    }
    settings.MITOL_APIGATEWAY_USERINFO_UPDATE = True

    test_user = await sync_to_async(SsoUserFactory.create)()
    payload, user_info = generate_fake_apisix_payload(user=test_user)
    request = await sync_to_async(generate_apisix_request)("request", payload)

    await sync_to_async(User.objects.filter(pk=test_user.pk).update)(
        email="stale@example.com"
    )
    test_user = await User.objects.aget(pk=test_user.pk)

    backend = ApisixRemoteUserBackend()
    result = await backend._aconfigure_user(request, test_user, created=False)  # noqa: SLF001

    assert result.email == user_info["email"]


@pytest.mark.django_db
def test_unset_lookup_field_filter_skips_empty_string_for_non_text_fields():
    """
    The "" branch is only built for a field that can hold an empty string.

    lookup_field is configurable and need not be textual. Comparing a
    UUIDField or IntegerField against "" raises while the query is being
    built, and authenticate()'s blanket except would turn that into a rejected
    login for every user, adopted or already linked.
    """
    backend = ApisixRemoteUserBackend()

    backend.lookup_field = "global_id"
    assert User._meta.get_field("global_id").empty_strings_allowed  # noqa: SLF001
    assert "global_id" in str(backend.unset_lookup_field_filter())

    backend.lookup_field = "id"
    assert not User._meta.get_field("id").empty_strings_allowed  # noqa: SLF001
    # Would raise on a non-text field if the "" branch were built anyway.
    assert User.objects.filter(backend.unset_lookup_field_filter()).count() == 0


@pytest.mark.django_db
def test_ambiguity_log_names_the_adoption_field(settings, caplog):
    """The ambiguity log names the criterion that actually collided."""
    settings.MITOL_APIGATEWAY_ADOPT_UNLINKED_USER_BY = "email"

    payload, user_info = generate_fake_apisix_payload()
    global_id = user_info[settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD]

    for _ in range(2):
        clash = SsoUserFactory.create()
        clash.global_id = None
        clash.email = user_info["email"]
        clash.save()

    request = generate_apisix_request("request", payload)
    backend = ApisixRemoteUserBackend()
    backend.adopt_unlinked_user_by = "email"

    user, _ = backend.resolve_user(request, global_id)

    assert user is None
    assert "email" in caplog.text
    assert "unlinked row" in caplog.text


@pytest.mark.django_db
def test_resolve_user_loses_the_adoption_race_without_stealing_the_row(
    settings, mocker
):
    """
    The loser of an adoption race creates its own user, it does not overwrite.

    Two identities carrying the same adoption value both select the one
    unlinked row. A blind save would let the second overwrite the first's
    lookup id while both requests returned that same account. The conditional
    update makes the claim atomic, so the loser matches nothing, re-resolves,
    and ends up with its own user.
    """
    settings.MITOL_APIGATEWAY_ADOPT_UNLINKED_USER_BY = "email"

    contested = SsoUserFactory.create()
    contested.global_id = None
    contested.save()

    payload, user_info = generate_fake_apisix_payload()
    user_info["email"] = contested.email
    payload = base64.b64encode(json.dumps(user_info).encode()).decode()
    request = generate_apisix_request("request", payload)
    loser_id = user_info[settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD]

    # The row as it looked when our get ran, before the winner claimed it.
    stale = User.objects.get(pk=contested.pk)

    winner_id = "winner-global-id"
    User.objects.filter(pk=contested.pk).update(global_id=winner_id)

    real_get = QuerySet.get
    calls = {"n": 0}

    def stale_get_once(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return stale
        return real_get(self, *args, **kwargs)

    mocker.patch.object(QuerySet, "get", stale_get_once)

    backend = ApisixRemoteUserBackend()
    backend.adopt_unlinked_user_by = "email"
    user, created = backend.resolve_user(request, loser_id)

    # The winner keeps the row.
    contested.refresh_from_db()
    assert contested.global_id == winner_id

    # The loser gets its own account rather than the winner's.
    assert created is True
    assert user.pk != contested.pk
    assert getattr(user, backend.lookup_field) == loser_id


@pytest.mark.django_db
def test_resolve_user_adopts_unlinked_account_case_insensitively(settings):
    """Adoption matches the unlinked account regardless of email case.

    Identity providers do not preserve the case a user typed at signup, so a
    pre-gateway row holding 'Legacy.User@Example.COM' must still be adopted by
    a header carrying 'legacy.user@example.com'. Matching exactly creates the
    duplicate this feature exists to prevent.
    """
    settings.MITOL_APIGATEWAY_ADOPT_UNLINKED_USER_BY = "email"

    legacy = SsoUserFactory.create(email="Legacy.User@Example.COM")
    legacy.global_id = None
    legacy.save()

    payload, user_info = generate_fake_apisix_payload()
    user_info["email"] = "legacy.user@example.com"
    payload = base64.b64encode(json.dumps(user_info).encode()).decode()
    request = generate_apisix_request("request", payload)

    backend = ApisixRemoteUserBackend()
    backend.adopt_unlinked_user_by = "email"
    user, created = backend.resolve_user(
        request, user_info[settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD]
    )

    assert created is False
    assert user.pk == legacy.pk
    assert User.objects.count() == 1


def test_backend_lookup_field_is_read_from_settings(settings):
    """ApisixRemoteUserBackend.lookup_field comes from the setting, not a
    hardcoded "global_id".

    Asserting the attribute in place cannot catch a regression here: the class
    body reads the setting at import, so under the test settings a hardcoded
    "global_id" is indistinguishable from the configured value. Reloading the
    module against a different setting is what actually pins it — revert the
    class-body read to a literal and this is the test that fails.
    """
    settings.MITOL_APIGATEWAY_USER_LOOKUP_FIELD = "scim_external_id"
    try:
        reloaded = importlib.reload(backends_module)
        assert reloaded.ApisixRemoteUserBackend.lookup_field == "scim_external_id"
    finally:
        # Restore the module other tests hold references into. The settings
        # fixture has already rolled the setting back by the time this runs in
        # a later test, but this module object is process-global.
        settings.MITOL_APIGATEWAY_USER_LOOKUP_FIELD = "global_id"
        importlib.reload(backends_module)


@pytest.mark.django_db
def test_adoption_lookup_stays_exact_for_non_text_fields():
    """A non-textual adoption field keeps an exact match.

    adopt_unlinked_user_by is configurable and need not be a string. __iexact
    against an integer or UUID column raises while the query is built, and
    authenticate()'s blanket except would turn that into a rejected login for
    every user, linked or not.
    """
    backend = ApisixRemoteUserBackend()

    backend.adopt_unlinked_user_by = "email"
    assert backend.adoption_lookup() == "email__iexact"

    backend.adopt_unlinked_user_by = "id"
    assert backend.adoption_lookup() == "id"
    # Building the query is the part that would raise.
    assert User.objects.filter(**{backend.adoption_lookup(): 1}).count() == 0
