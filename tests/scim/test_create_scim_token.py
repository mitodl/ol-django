"""Tests for the create_scim_token management command"""

from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from mitol.scim import api
from mitol.scim.constants import is_service_account_email
from mitol.scim.utils import is_authenticated_predicate
from oauth2_provider.models import get_access_token_model
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauthlib.common import Request

User = get_user_model()
AccessToken = get_access_token_model()

pytestmark = pytest.mark.django_db


def _run(**options) -> tuple[str, str]:
    out, err = StringIO(), StringIO()
    call_command("create_scim_token", stdout=out, stderr=err, **options)
    return out.getvalue(), err.getvalue()


def test_creates_staff_service_account_and_token():
    """The token authenticates through DOT as a user the SCIM views accept"""
    _run(username="scim-service", token="local-token")  # noqa: S106

    request = Request("/scim/v2/Users")
    assert OAuth2Validator().validate_bearer_token("local-token", ["scim"], request)
    assert request.user.username == "scim-service"
    assert is_authenticated_predicate(request.user)
    assert not request.user.has_usable_password()
    assert request.user.email == "scim-service@scim.invalid"
    token = AccessToken.objects.get(token="local-token")  # noqa: S106
    assert token.expires > timezone.now() + timedelta(days=364)


def test_email_is_the_username_local_part_at_the_service_domain():
    """The email is always the service-account marker, never a person's address"""
    _run(username="a@ol.test", token="t1")  # noqa: S106

    assert User.objects.get(username="a@ol.test").email == "a@scim.invalid"
    assert is_service_account_email("a@scim.invalid")
    assert is_service_account_email("A@SCIM.INVALID")
    assert not is_service_account_email("a@scim.invalid.example.com")
    assert not is_service_account_email(None)


def test_refuses_a_username_whose_email_is_taken():
    """Two usernames with one local part would share an email; the second is refused"""
    _run(username="scim@ol.test", token="t1")  # noqa: S106

    with pytest.raises(CommandError, match="already has the email"):
        _run(username="scim@other.test", token="t2")  # noqa: S106

    assert not User.objects.filter(username="scim@other.test").exists()


def test_sync_skips_service_accounts(monkeypatch: pytest.MonkeyPatch):
    """The client sync never sends a service account to Keycloak"""
    _run(username="scim-service", token="t")  # noqa: S106
    person = User.objects.create(username="person", email="person@example.com")
    synced = []

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def search(_session, users):
        synced.extend(users)
        return []

    monkeypatch.setattr(api, "get_session", Session)
    monkeypatch.setattr(api, "_user_search_by_email", search)
    monkeypatch.setattr(api, "_get_sync_operations", lambda *_args: [])
    monkeypatch.setattr(api, "_perform_sync_operations", lambda *_args: [])

    list(api.sync_users_to_scim_remote(list(User.objects.all())))

    assert synced == [person]


def test_rerun_refreshes_instead_of_duplicating():
    """A second run with the same token updates the row and restores staff"""
    _run(username="scim-service", token="local-token", expires_days=1)  # noqa: S106
    User.objects.filter(username="scim-service").update(is_staff=False)

    out, _ = _run(username="scim-service", token="local-token", scope="scim read")  # noqa: S106

    assert AccessToken.objects.filter(token="local-token").count() == 1  # noqa: S106
    token = AccessToken.objects.get(token="local-token")  # noqa: S106
    assert token.scope == "scim read"
    assert token.expires > timezone.now() + timedelta(days=364)
    assert is_authenticated_predicate(token.user)
    assert "refreshed token" in out


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"email": "person@example.com"}, "email outside"),
        ({"password": "pbkdf2_sha256$1$salt$hash"}, "usable password"),
        ({"last_login": timezone.now()}, "logged in"),
        ({"global_id": "a1b2"}, "global_id"),
        ({"is_active": False}, "inactive"),
    ],
)
def test_refuses_an_account_that_is_not_a_service_account(changes, reason):
    """An existing person is never promoted to staff or given a token"""
    _run(username="scim-service", token="local-token")  # noqa: S106
    User.objects.filter(username="scim-service").update(**changes)
    before = User.objects.get(username="scim-service")

    with pytest.raises(CommandError, match=reason):
        _run(username="scim-service", token="other-token")  # noqa: S106

    after = User.objects.get(username="scim-service")
    assert (after.is_staff, after.is_active, after.password) == (
        before.is_staff,
        before.is_active,
        before.password,
    )
    assert not AccessToken.objects.filter(token="other-token").exists()  # noqa: S106


def test_refuses_a_token_owned_by_someone_else():
    """A token value already issued to another user keeps its owner"""
    other = User.objects.create(username="learner", email="learner@example.com")
    AccessToken.objects.create(
        user=other,
        token="taken",  # noqa: S106
        scope="read",
        expires=timezone.now() + timedelta(days=1),
    )

    with pytest.raises(CommandError, match="another user"):
        _run(username="scim-service", token="taken")  # noqa: S106

    token = AccessToken.objects.get(token="taken")  # noqa: S106
    assert (token.user, token.scope) == (other, "read")
    assert not User.objects.filter(username="scim-service").exists()


def test_generated_token_is_printed_and_stored():
    """Without --token a random value is written and printed on the last line"""
    out, _ = _run(username="scim-service")

    generated = out.strip().splitlines()[-1]
    assert len(generated) >= 30  # noqa: PLR2004
    assert AccessToken.objects.get(token=generated).user.username == "scim-service"


def test_supplied_token_is_not_printed():
    """A caller-supplied token stays out of the output"""
    out, err = _run(username="scim-service", token="do-not-echo")  # noqa: S106

    assert "do-not-echo" not in out + err


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"token": ""}, "must not be empty"),
        ({"token": "t", "expires_days": 0}, "must be positive"),
    ],
)
def test_rejects_invalid_input(options, message):
    """An empty token or an already-expired one is refused"""
    with pytest.raises(CommandError, match=message):
        _run(username="scim-service", **options)


def test_warns_when_scope_lacks_scim():
    """A token without the scim scope still gets written, with a warning"""
    _, err = _run(username="scim-service", token="t", scope="read")  # noqa: S106

    assert "lacks 'scim'" in err
