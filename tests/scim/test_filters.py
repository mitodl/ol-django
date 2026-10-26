"""Tests for the SCIM filter queries"""

from http import HTTPStatus

import pytest
from django.test import Client
from django.urls import reverse
from main.factories import UserFactory
from mitol.scim.filters import UserFilterQuery

pytestmark = [pytest.mark.django_db]


@pytest.fixture
def handle_user():
    """Create a user whose username is a handle rather than their email"""
    return UserFactory.create(username="jdoe", email="John.Doe@example.com")


def _search(filter_query):
    return list(UserFilterQuery.search(filter_query))


def test_username_matches_only_username_by_default(handle_user):
    """Without aliases a userName filter compares against username alone"""
    assert _search('userName eq "jdoe"') == [handle_user]
    assert _search('userName eq "john.doe@example.com"') == []


def test_username_matches_configured_fields(settings, handle_user):
    """UserName also matches each configured field, case-insensitively"""
    settings.MITOL_SCIM_USERNAME_FILTER_FIELDS = ["scim_username", "email"]
    other = UserFactory.create(username="other", scim_username="Other@Example.com")

    assert _search('userName eq "jdoe"') == [handle_user]
    assert _search('userName eq "JOHN.DOE@example.com"') == [handle_user]
    assert _search('userName eq "other@example.com"') == [other]


def test_username_ne_excludes_every_alias(settings, handle_user):
    """A negated comparison excludes a user that matches through any alias"""
    settings.MITOL_SCIM_USERNAME_FILTER_FIELDS = ["email"]
    other = UserFactory.create()

    results = _search('userName ne "john.doe@example.com"')

    assert handle_user not in results
    assert other in results


def test_username_matching_two_users_returns_both(settings, handle_user):
    """A value matching two users returns both rather than picking one"""
    settings.MITOL_SCIM_USERNAME_FILTER_FIELDS = ["email"]
    other = UserFactory.create(username="john.doe@example.com")

    assert set(_search('userName eq "john.doe@example.com"')) == {handle_user, other}


@pytest.mark.parametrize(
    "filter_query",
    [
        'userName co "DOE@EXAMPLE"',
        'userName sw "JOHN.DOE"',
        'userName ew "@EXAMPLE.COM"',
    ],
)
def test_alias_substring_ops_ignore_case(settings, handle_user, filter_query):
    """Substring comparisons against an alias are case-insensitive too"""
    settings.MITOL_SCIM_USERNAME_FILTER_FIELDS = ["email"]

    assert handle_user in _search(filter_query)


def test_aliases_do_not_apply_to_ordering_ops(settings):
    """An ordering comparison on userName compares against username alone"""
    settings.MITOL_SCIM_USERNAME_FILTER_FIELDS = ["email"]
    user = UserFactory.create(username="zzz", email="aaa@example.com")

    assert user not in _search('userName lt "m"')


@pytest.mark.usefixtures("handle_user")
def test_aliases_do_not_apply_to_other_attributes(settings):
    """Only userName gets the configured aliases"""
    settings.MITOL_SCIM_USERNAME_FILTER_FIELDS = ["email"]

    assert _search('name.givenName eq "john.doe@example.com"') == []


def test_list_filter_finds_user_by_email(settings, staff_user, handle_user):
    """The lookup scim-for-keycloak makes finds a user whose username differs"""
    settings.MITOL_SCIM_USERNAME_FILTER_FIELDS = ["scim_username", "email"]
    client = Client()
    client.force_login(staff_user)

    resp = client.get(
        reverse("scim:users"),
        {"filter": 'userName EQ "john.doe@example.com"'},
    )

    assert resp.status_code == HTTPStatus.OK, f"Error response: {resp.content}"
    data = resp.json()
    assert data["totalResults"] == 1
    assert data["Resources"][0]["id"] == handle_user.scim_id
