import itertools
import json
import operator
import random
from collections.abc import Callable
from functools import reduce
from http import HTTPStatus
from math import floor
from types import SimpleNamespace

import pytest
from anys import ANY_STR
from deepmerge import always_merger
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from main.factories import UserFactory
from mitol.scim import constants

User = get_user_model()


@pytest.fixture
def scim_client(staff_user):
    """Test client for scim"""
    client = Client()
    client.force_login(staff_user)
    return client


@pytest.fixture(scope="module")
def large_user_set(django_db_blocker):
    """Large set of users"""
    # per https://pytest-django.readthedocs.io/en/latest/database.html#populate-the-test-database-if-you-don-t-use-transactional-or-live-server
    with django_db_blocker.unblock():
        yield UserFactory.create_batch(1100)


def test_scim_user_post(scim_client):
    """Test that we can create a user via SCIM API"""
    user_q = User.objects.filter(scim_external_id="1")
    assert not user_q.exists()

    resp = scim_client.post(
        reverse("scim:users"),
        content_type="application/scim+json",
        data=json.dumps(
            {
                "schemas": [constants.SchemaURI.USER],
                "emails": [{"value": "jdoe@example.com", "primary": True}],
                "active": True,
                "userName": "jdoe",
                "externalId": "1",
                "name": {
                    "familyName": "Doe",
                    "givenName": "John",
                },
            }
        ),
    )

    assert resp.status_code == HTTPStatus.CREATED, f"Error response: {resp.content}"

    user = user_q.first()

    assert user is not None
    assert user.email == "jdoe@example.com"
    assert user.username == "jdoe"
    assert user.first_name == "John"
    assert user.last_name == "Doe"


def test_scim_user_put(scim_client):
    """Test that a user can be updated via PUT"""
    user = UserFactory.create()

    resp = scim_client.put(
        f"{reverse('scim:users')}/{user.scim_id}",
        content_type="application/scim+json",
        data=json.dumps(
            {
                "schemas": [constants.SchemaURI.USER],
                "emails": [{"value": "jsmith@example.com", "primary": True}],
                "active": True,
                "userName": "jsmith",
                "externalId": "1",
                "name": {
                    "familyName": "Smith",
                    "givenName": "Jimmy",
                },
                "fullName": "Jimmy Smith",
                "emailOptIn": 0,
            }
        ),
    )

    assert resp.status_code == HTTPStatus.OK, f"Error response: {resp.content}"

    user.refresh_from_db()

    assert user.email == "jsmith@example.com"
    assert user.username == "jsmith"
    assert user.first_name == "Jimmy"
    assert user.last_name == "Smith"


def test_scim_user_patch(scim_client):
    """Test that a user can be updated via PATCH"""
    user = UserFactory.create()

    resp = scim_client.patch(
        f"{reverse('scim:users')}/{user.scim_id}",
        content_type="application/scim+json",
        data=json.dumps(
            {
                "schemas": [constants.SchemaURI.PATCH_OP],
                "Operations": [
                    {
                        "op": "replace",
                        # yes, the value we get from scim-for-keycloak is a JSON encoded
                        # string...inside JSON...
                        "value": json.dumps(
                            {
                                "schemas": [constants.SchemaURI.USER],
                                "emailOptIn": 1,
                                "fullName": "Billy Bob",
                                "name": {
                                    "givenName": "Billy",
                                    "familyName": "Bob",
                                },
                            }
                        ),
                    }
                ],
            }
        ),
    )

    assert resp.status_code == HTTPStatus.OK, f"Error response: {resp.content}"

    user_updated = User.objects.get(pk=user.id)

    assert user_updated.email == user.email
    assert user_updated.username == user.username
    assert user_updated.first_name == "Billy"
    assert user_updated.last_name == "Bob"


def _user_to_scim_payload(user):
    """Test util to serialize a user to a SCIM representation"""
    return {
        "schemas": [constants.SchemaURI.USER],
        "emails": [{"value": user.email, "primary": True}],
        "userName": user.username,
        "name": {
            "givenName": user.first_name,
            "familyName": user.last_name,
        },
    }


USER_FIELD_TYPES: dict[str, type] = {
    "username": str,
    "email": str,
    "first_name": str,
    "last_name": str,
}

USER_FIELDS_TO_SCIM: dict[str, Callable] = {
    "username": lambda value: {"userName": value},
    "email": lambda value: {"emails": [{"value": value, "primary": True}]},
    "first_name": lambda value: {"name": {"givenName": value}},
    "last_name": lambda value: {"name": {"familyName": value}},
}


def _post_operation(data, bulk_id_gen):
    """Operation for a bulk POST"""
    bulk_id = str(next(bulk_id_gen))
    return SimpleNamespace(
        payload={
            "method": "post",
            "bulkId": bulk_id,
            "path": "/Users",
            "data": _user_to_scim_payload(data),
        },
        user=None,
        expected_user_state=data,
        expected_response={
            "method": "post",
            "location": ANY_STR,
            "bulkId": bulk_id,
            "status": "201",
            "id": ANY_STR,
        },
    )


def _put_operation(user, data, bulk_id_gen):
    """Operation for a bulk PUT"""
    bulk_id = str(next(bulk_id_gen))
    return SimpleNamespace(
        payload={
            "method": "put",
            "bulkId": bulk_id,
            "path": f"/Users/{user.scim_id}",
            "data": _user_to_scim_payload(data),
        },
        user=user,
        expected_user_state=data,
        expected_response={
            "method": "put",
            "location": ANY_STR,
            "bulkId": bulk_id,
            "status": "200",
            "id": str(user.scim_id),
        },
    )


def _patch_operation(user, data, fields_to_patch, bulk_id_gen):
    """Operation for a bulk PUT"""

    def _expected_patch_value(field):
        field_getter = operator.attrgetter(field)
        return field_getter(data if field in fields_to_patch else user)

    bulk_id = str(next(bulk_id_gen))
    field_updates = [
        mk_scim_value(operator.attrgetter(user_path)(data))
        for user_path, mk_scim_value in USER_FIELDS_TO_SCIM.items()
        if user_path in fields_to_patch
    ]

    return SimpleNamespace(
        payload={
            "method": "patch",
            "bulkId": bulk_id,
            "path": f"/Users/{user.scim_id}",
            "data": {
                "schemas": [constants.SchemaURI.PATCH_OP],
                "Operations": [
                    {
                        "op": "replace",
                        "value": reduce(always_merger.merge, field_updates, {}),
                    }
                ],
            },
        },
        user=user,
        expected_user_state=SimpleNamespace(
            email=_expected_patch_value("email"),
            username=_expected_patch_value("username"),
            first_name=_expected_patch_value("first_name"),
            last_name=_expected_patch_value("last_name"),
        ),
        expected_response={
            "method": "patch",
            "location": ANY_STR,
            "bulkId": bulk_id,
            "status": "200",
            "id": str(user.scim_id),
        },
    )


def _delete_operation(user, bulk_id_gen):
    """Operation for a bulk DELETE"""
    bulk_id = str(next(bulk_id_gen))
    return SimpleNamespace(
        payload={
            "method": "delete",
            "bulkId": bulk_id,
            "path": f"/Users/{user.scim_id}",
        },
        user=user,
        expected_user_state=None,
        expected_response={
            "method": "delete",
            "bulkId": bulk_id,
            "status": "204",
        },
    )


@pytest.fixture
def bulk_test_data():
    """Test data for the /Bulk API tests"""
    existing_users = UserFactory.create_batch(500)
    remaining_users = set(existing_users)

    users_to_put = random.sample(sorted(remaining_users, key=lambda user: user.id), 100)
    remaining_users = remaining_users - set(users_to_put)

    users_to_patch = random.sample(
        sorted(remaining_users, key=lambda user: user.id), 100
    )
    remaining_users = remaining_users - set(users_to_patch)

    users_to_delete = random.sample(
        sorted(remaining_users, key=lambda user: user.id), 100
    )
    remaining_users = remaining_users - set(users_to_delete)

    user_post_data = UserFactory.build_batch(100)
    user_put_data = UserFactory.build_batch(len(users_to_put))
    user_patch_data = UserFactory.build_batch(len(users_to_patch))

    bulk_id_gen = itertools.count()

    post_operations = [_post_operation(data, bulk_id_gen) for data in user_post_data]
    put_operations = [
        _put_operation(user, data, bulk_id_gen)
        for user, data in zip(users_to_put, user_put_data)
    ]
    patch_operations = [
        _patch_operation(user, patch_data, fields_to_patch, bulk_id_gen)
        for user, patch_data, fields_to_patch in [
            (
                user,
                patch_data,
                # random number of field updates
                list(
                    random.sample(
                        list(USER_FIELDS_TO_SCIM.keys()),
                        random.randint(1, len(USER_FIELDS_TO_SCIM.keys())),  # noqa: S311
                    )
                ),
            )
            for user, patch_data in zip(users_to_patch, user_patch_data)
        ]
    ]
    delete_operations = [
        _delete_operation(user, bulk_id_gen) for user in users_to_delete
    ]

    operations = [
        *post_operations,
        *patch_operations,
        *put_operations,
        *delete_operations,
    ]
    random.shuffle(operations)

    return SimpleNamespace(
        existing_users=existing_users,
        remaining_users=remaining_users,
        post_operations=post_operations,
        patch_operations=patch_operations,
        put_operations=put_operations,
        delete_operations=delete_operations,
        operations=operations,
    )


def test_bulk_post(scim_client, bulk_test_data):
    """Verify that bulk operations work as expected"""
    user_count = User.objects.count()

    resp = scim_client.post(
        reverse("ol-scim:bulk"),
        content_type="application/scim+json",
        data=json.dumps(
            {
                "schemas": [constants.SchemaURI.BULK_REQUEST],
                "Operations": [
                    operation.payload for operation in bulk_test_data.operations
                ],
            }
        ),
    )

    assert resp.status_code == HTTPStatus.OK

    # singular user is the staff user
    assert User.objects.count() == user_count + len(bulk_test_data.post_operations)

    results_by_bulk_id = {
        op_result["bulkId"]: op_result for op_result in resp.json()["Operations"]
    }

    for operation in bulk_test_data.operations:
        assert (
            results_by_bulk_id[operation.payload["bulkId"]]
            == operation.expected_response
        )

        if operation in bulk_test_data.delete_operations:
            user = User.objects.get(id=operation.user.id)
            assert not user.is_active
        else:
            if operation in bulk_test_data.post_operations:
                user = User.objects.get(username=operation.expected_user_state.username)
            else:
                user = User.objects.get(id=operation.user.id)

            for key, key_type in USER_FIELD_TYPES.items():
                attr_getter = operator.attrgetter(key)

                actual_value = attr_getter(user)
                expected_value = attr_getter(operation.expected_user_state)

                if key_type is bool or key_type is None:
                    assert actual_value is expected_value
                else:
                    assert actual_value == expected_value


def _randomize_local_part_casing(email: str) -> str:
    """Randomize the casing of the local part of the email"""
    local, hostname = email.split("@")

    local = "".join(random.choice((str.lower, str.upper))(char) for char in local)  # noqa: S311

    return f"{local}@{hostname}"


@pytest.mark.parametrize(
    ("sort_by", "sort_order"),
    [
        (None, None),
        ("id", None),
        ("id", "ascending"),
        ("id", "descending"),
        ("email", None),
        ("email", "ascending"),
        ("email", "descending"),
        ("userName", None),
        ("userName", "ascending"),
        ("userName", "descending"),
    ],
)
@pytest.mark.parametrize("count", [None, 100, 500])
def test_user_search(large_user_set, scim_client, sort_by, sort_order, count):
    """Test the user search endpoint"""
    search_users = large_user_set[: floor(len(large_user_set) / 2)]
    emails = [_randomize_local_part_casing(user.email) for user in search_users]

    expected = search_users

    effective_count = count or 50
    effective_sort_by = constants.SORT_MAPPING[sort_by or "id"]
    effective_sort_order = sort_order or "ascending"

    def _sort(user):
        value = getattr(user, effective_sort_by)

        # postgres sort is case-insensitive
        return value.lower() if isinstance(value, str) else value

    expected = sorted(
        expected,
        key=_sort,
        reverse=effective_sort_order == "descending",
    )

    for page in range(int(len(emails) / effective_count)):
        start_index = page * effective_count  # zero based index
        resp = scim_client.post(
            reverse("ol-scim:users-search"),
            content_type="application/scim+json",
            data=json.dumps(
                {
                    "schemas": [constants.SchemaURI.SERACH_REQUEST],
                    "filter": " OR ".join(
                        [f'emails.value EQ "{email}"' for email in emails]
                    ),
                    # SCIM API is 1-based index
                    # Additionally, scim-for-keycloak sends this as a string,
                    # but spec examples have ints
                    "startIndex": str(start_index + 1),
                    **({"sortBy": sort_by} if sort_by is not None else {}),
                    **({"sortOrder": sort_order} if sort_order is not None else {}),
                    **({"count": str(count)} if count is not None else {}),
                }
            ),
        )

        expected_in_resp = expected[start_index : start_index + effective_count]

        assert resp.status_code == HTTPStatus.OK, f"Got error: {resp.content}"
        assert resp.json() == {
            "totalResults": len(emails),
            "itemsPerPage": effective_count,
            "startIndex": start_index + 1,
            "schemas": [constants.SchemaURI.LIST_RESPONSE],
            "Resources": [
                {
                    "id": user.scim_id,
                    "active": user.is_active,
                    "userName": user.username,
                    "displayName": f"{user.first_name} {user.last_name}",
                    "emails": [{"value": user.email, "primary": True}],
                    "externalId": None,
                    "name": {
                        "givenName": user.first_name,
                        "familyName": user.last_name,
                    },
                    "meta": {
                        "resourceType": "User",
                        "location": f"https://localhost/scim/v2/Users/{user.scim_id}",
                        "lastModified": user.updated_on.isoformat(
                            timespec="milliseconds"
                        ),
                        "created": user.created_on.isoformat(timespec="milliseconds"),
                    },
                    "groups": [],
                    "schemas": [constants.SchemaURI.USER],
                }
                for user in expected_in_resp
            ],
        }
