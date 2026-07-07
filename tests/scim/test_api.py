import json
import math
import random
import uuid
from dataclasses import dataclass
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from mitol.common.factories import UserFactory
from mitol.common.factories.defaults import ScimUserFactory
from mitol.scim import api
from mitol.scim.adapters import UserAdapter
from mitol.scim.constants import SchemaURI
from mitol.scim.requests import InMemoryHttpRequest
from more_itertools import chunked, distribute
from responses import RequestsMock, matchers

User = get_user_model()


@pytest.mark.usefixtures("mock_client_init_requests")
def test_get_session(responses: RequestsMock):
    _ = responses.get(
        url="https://keycloak:8080/realms/ol-local/scim/v2/",
        json={"success": True},
        match=[matchers.header_matcher({"Authorization": "Bearer abc123"})],
    )

    session = api.get_session()

    response = session.get("https://keycloak:8080/realms/ol-local/scim/v2/")

    assert response.json() == {"success": True}


@dataclass
class Users:
    users: list["User"]
    users_by_id: dict[int, "User"]
    users_in_remote: list["User"]
    users_to_create: list["User"]
    users_to_error: list["User"]
    external_ids_by_user_id: dict[int, str]


@pytest.fixture
def users(request):
    users: list[User] = UserFactory.create_batch(request.param)
    # simulate a random selection of users already in keycloak
    users_in_remote, users_to_create = map(list, distribute(2, users))

    users_to_error = list(
        random.sample(
            users_to_create,
            # 10% of requested users, rounded up, will result in an error
            math.ceil(len(users_to_create) * 0.1),
        )
    )
    external_ids_by_user_id = {user.id: str(uuid.uuid4()) for user in users}
    return Users(
        users=sorted(users, key=lambda u: u.id),
        users_by_id={user.id: user for user in users},
        users_in_remote=sorted(users_in_remote, key=lambda u: u.id),
        users_to_create=sorted(users_to_create, key=lambda u: u.id),
        users_to_error=sorted(users_to_error, key=lambda u: u.id),
        external_ids_by_user_id=external_ids_by_user_id,
    )


@pytest.fixture
def mock_client_init_requests(responses: RequestsMock):
    _ = responses.get(
        "https://keycloak:8080/realms/ol-local/.well-known/openid-configuration",
        json={
            "token_endpoint": "https://keycloak:8080/realms/ol-local/protocol/openid/token",
        },
    )
    _ = responses.post(
        "https://keycloak:8080/realms/ol-local/protocol/openid/token",
        json={
            "access_token": "abc123",
            "grant_type": "client_credentials",
        },
    )


@pytest.fixture
def mock_search_requests(settings, users: Users, responses: RequestsMock):
    items_per_page = 10

    def _mk_callback(batch):
        batch_users_in_remote = [
            user for user in users.users_in_remote if user in batch
        ]

        def _callback(request):
            payload = json.loads(request.body)

            # remap to 0-based index
            start_index = payload["startIndex"] - 1

            return (
                200,
                {},
                json.dumps(
                    {
                        "schemas": [SchemaURI.LIST_RESPONSE],
                        "Resources": [
                            {
                                "id": users.external_ids_by_user_id[user.id],
                                "emails": [
                                    {
                                        "value": user.email.lower(),
                                        "primary": True,
                                    }
                                ],
                            }
                            for user in batch_users_in_remote[
                                start_index : start_index + items_per_page
                            ]
                        ],
                        "itemsPerPage": items_per_page,
                        "totalResults": len(batch_users_in_remote),
                        "startIndex": start_index,
                    }
                ),
            )

        return _callback

    for batch in chunked(users.users, settings.MITOL_SCIM_KEYCLOAK_SEARCH_BATCH_SIZE):
        responses.add_callback(
            responses.POST,
            url="https://keycloak:8080/realms/ol-local/scim/v2/Users/.search",
            callback=_mk_callback(batch),
            match=[
                matchers.json_params_matcher(
                    params={
                        "schemas": [SchemaURI.SERACH_REQUEST],
                        "filter": " OR ".join(
                            [
                                f'emails.value EQ "{user.email.lower()}"'
                                for user in batch
                            ]
                        ),
                    },
                    strict_match=False,
                )
            ],
        )


@pytest.fixture
def bulk_operations_count(request, settings):
    settings.MITOL_SCIM_KEYCLOAK_BULK_OPERATIONS_COUNT = request.param
    return request.param


@pytest.fixture
def mock_bulk_requests(users: Users, responses: RequestsMock):
    def _callback(request):
        payload = json.loads(request.body)
        operations = payload["Operations"]
        req_users = []

        for operation in operations:
            bulk_id = int(operation["bulkId"])
            user = users.users_by_id[bulk_id]

            assert operation == {
                "method": "POST",
                "path": "/Users",
                "bulkId": str(user.id),
                "data": {
                    **(UserAdapter(user, InMemoryHttpRequest.stub()).to_dict()),
                    "emailVerified": True,
                },
            }
            req_users.append(user)

        return (
            200,
            {},
            json.dumps(
                {
                    "schemas": [SchemaURI.BULK_RESPONSE],
                    "Operations": [
                        (
                            {
                                "bulkId": str(user.id),
                                "method": "POST",
                                "status": "400",
                                "response": {
                                    "schemas": [SchemaURI.ERROR],
                                    "detail": "Bad data",
                                    "status": str(HTTPStatus.BAD_REQUEST),
                                },
                            }
                            if user in users.users_to_error
                            else {
                                "location": f"https://keycloak:8080/realms/ol-local/scim/v2/Users/{users.external_ids_by_user_id[user.id]}",
                                "bulkId": str(user.id),
                                "method": "POST",
                                "status": HTTPStatus.CREATED,
                            }
                        )
                        for user in req_users
                    ],
                }
            ),
        )

    responses.add_callback(
        responses.POST,
        url="https://keycloak:8080/realms/ol-local/scim/v2/Users/Bulk",
        callback=_callback,
        match=[
            matchers.json_params_matcher(
                params={
                    "schemas": [SchemaURI.BULK_REQUEST],
                },
                strict_match=False,
            )
        ],
    )


@pytest.mark.django_db
@pytest.mark.parametrize("users", [17, 25, 98, 178], indirect=True)
@pytest.mark.parametrize("bulk_operations_count", [13, 50, 75], indirect=True)
@pytest.mark.usefixtures(
    "responses",
    "mock_client_init_requests",
    "mock_search_requests",
    "mock_bulk_requests",
    "bulk_operations_count",
)
def test_sync_users_to_scim_remote(users: Users):
    for user in users.users:
        assert user.scim_external_id is None
        assert user.global_id == ""

    api.sync_users_to_scim_remote(users.users)

    for user in users.users:
        user.refresh_from_db()

        if user in users.users_to_error:
            assert user.scim_external_id is None
        else:
            assert user.scim_external_id == users.external_ids_by_user_id[user.id]
            assert user.global_id == users.external_ids_by_user_id[user.id]


@pytest.mark.django_db
@pytest.mark.usefixtures("responses", "mock_client_init_requests")
def test_sync_users_to_scim_remote_reconciles_known_users_by_id(
    responses: RequestsMock,
):
    """
    A user that was already synced (has a scim_external_id) must be
    reconciled by that id, not by re-searching on email - email can change
    or fail to match, which used to silently create a duplicate remote user.
    """
    known_user = ScimUserFactory()
    unknown_user = UserFactory()
    unknown_external_id = str(uuid.uuid4())

    def _id_search_callback(request):
        payload = json.loads(request.body)
        return (
            200,
            {},
            json.dumps(
                {
                    "schemas": [SchemaURI.LIST_RESPONSE],
                    "Resources": (
                        [
                            {
                                "id": known_user.scim_external_id,
                                "emails": [
                                    {
                                        "value": known_user.email.lower(),
                                        "primary": True,
                                    }
                                ],
                            }
                        ]
                        if payload["startIndex"] == 1
                        else []
                    ),
                    "itemsPerPage": 1,
                    "totalResults": 1,
                    "startIndex": payload["startIndex"],
                }
            ),
        )

    responses.add_callback(
        responses.POST,
        url="https://keycloak:8080/realms/ol-local/scim/v2/Users/.search",
        callback=_id_search_callback,
        match=[
            matchers.json_params_matcher(
                params={"filter": f'id EQ "{known_user.scim_external_id}"'},
                strict_match=False,
            )
        ],
    )

    def _email_search_callback(request):
        payload = json.loads(request.body)
        return (
            200,
            {},
            json.dumps(
                {
                    "schemas": [SchemaURI.LIST_RESPONSE],
                    "Resources": (
                        [
                            {
                                "id": unknown_external_id,
                                "emails": [
                                    {
                                        "value": unknown_user.email.lower(),
                                        "primary": True,
                                    }
                                ],
                            }
                        ]
                        if payload["startIndex"] == 1
                        else []
                    ),
                    "itemsPerPage": 1,
                    "totalResults": 1,
                    "startIndex": payload["startIndex"],
                }
            ),
        )

    responses.add_callback(
        responses.POST,
        url="https://keycloak:8080/realms/ol-local/scim/v2/Users/.search",
        callback=_email_search_callback,
        match=[
            matchers.json_params_matcher(
                params={"filter": f'emails.value EQ "{unknown_user.email.lower()}"'},
                strict_match=False,
            )
        ],
    )

    failed_users = api.sync_users_to_scim_remote([known_user, unknown_user])

    assert failed_users == []

    known_user.refresh_from_db()
    unknown_user.refresh_from_db()

    # unchanged - reconciled by id, no create/update operation needed
    assert known_user.global_id == known_user.scim_external_id
    assert unknown_user.scim_external_id == unknown_external_id
    assert unknown_user.global_id == unknown_external_id


@pytest.mark.django_db
@pytest.mark.usefixtures("responses", "mock_client_init_requests")
def test_sync_users_to_scim_remote_isolates_bulk_chunk_failure(
    settings, responses: RequestsMock
):
    """A failed bulk-create chunk must not lose users in other chunks"""
    settings.MITOL_SCIM_KEYCLOAK_BULK_OPERATIONS_COUNT = 1
    good_user_1, bad_user, good_user_2 = UserFactory.create_batch(3)
    external_ids = {
        good_user_1.id: str(uuid.uuid4()),
        good_user_2.id: str(uuid.uuid4()),
    }

    responses.post(
        "https://keycloak:8080/realms/ol-local/scim/v2/Users/.search",
        json={
            "schemas": [SchemaURI.LIST_RESPONSE],
            "Resources": [],
            "itemsPerPage": 0,
            "totalResults": 0,
            "startIndex": 1,
        },
    )

    def _bulk_callback(request):
        payload = json.loads(request.body)
        bulk_id = int(payload["Operations"][0]["bulkId"])

        if bulk_id == bad_user.id:
            return (500, {}, json.dumps({"detail": "boom"}))

        return (
            200,
            {},
            json.dumps(
                {
                    "schemas": [SchemaURI.BULK_RESPONSE],
                    "Operations": [
                        {
                            "location": f"https://keycloak:8080/realms/ol-local/scim/v2/Users/{external_ids[bulk_id]}",
                            "bulkId": str(bulk_id),
                            "method": "POST",
                            "status": HTTPStatus.CREATED,
                        }
                    ],
                }
            ),
        )

    responses.add_callback(
        responses.POST,
        url="https://keycloak:8080/realms/ol-local/scim/v2/Users/Bulk",
        callback=_bulk_callback,
    )

    failed_users = api.sync_users_to_scim_remote([good_user_1, bad_user, good_user_2])

    assert failed_users == [bad_user]

    bad_user.refresh_from_db()
    good_user_1.refresh_from_db()
    good_user_2.refresh_from_db()

    assert bad_user.scim_external_id is None
    assert good_user_1.scim_external_id == external_ids[good_user_1.id]
    assert good_user_2.scim_external_id == external_ids[good_user_2.id]


@pytest.mark.django_db
@pytest.mark.usefixtures("responses", "mock_client_init_requests")
def test_sync_users_to_scim_remote_isolates_search_batch_failure(
    settings, responses: RequestsMock
):
    """A failed search batch must not abort the rest of the sync run"""
    settings.MITOL_SCIM_KEYCLOAK_SEARCH_BATCH_SIZE = 1
    good_user, bad_user = UserFactory.create_batch(2)
    good_external_id = str(uuid.uuid4())

    def _search_callback(request):
        payload = json.loads(request.body)
        if bad_user.email.lower() in payload["filter"]:
            return (500, {}, json.dumps({"detail": "boom"}))

        return (
            200,
            {},
            json.dumps(
                {
                    "schemas": [SchemaURI.LIST_RESPONSE],
                    "Resources": [],
                    "itemsPerPage": 0,
                    "totalResults": 0,
                    "startIndex": payload["startIndex"],
                }
            ),
        )

    responses.add_callback(
        responses.POST,
        url="https://keycloak:8080/realms/ol-local/scim/v2/Users/.search",
        callback=_search_callback,
    )

    def _bulk_callback(request):
        payload = json.loads(request.body)
        operation = payload["Operations"][0]
        assert int(operation["bulkId"]) == good_user.id

        return (
            200,
            {},
            json.dumps(
                {
                    "schemas": [SchemaURI.BULK_RESPONSE],
                    "Operations": [
                        {
                            "location": f"https://keycloak:8080/realms/ol-local/scim/v2/Users/{good_external_id}",
                            "bulkId": str(good_user.id),
                            "method": "POST",
                            "status": HTTPStatus.CREATED,
                        }
                    ],
                }
            ),
        )

    responses.add_callback(
        responses.POST,
        url="https://keycloak:8080/realms/ol-local/scim/v2/Users/Bulk",
        callback=_bulk_callback,
    )

    failed_users = api.sync_users_to_scim_remote([good_user, bad_user])

    assert failed_users == [bad_user]

    good_user.refresh_from_db()
    bad_user.refresh_from_db()

    assert good_user.scim_external_id == good_external_id
    assert bad_user.scim_external_id is None


@pytest.mark.django_db
@pytest.mark.usefixtures("responses", "mock_client_init_requests")
def test_sync_users_to_scim_remote_isolates_duplicate_match_key_batch():
    """
    Two local users that share a match key in the same search batch (e.g.
    duplicate email data) can't be safely reconciled - matching either one
    to a returned resource risks attaching it to the wrong local user, and
    falling through to create risks a duplicate. The whole batch must be
    reported as failed without making a search/create request at all.
    """
    dup_email = "duplicate@example.com"
    dup_user_1 = UserFactory(email=dup_email, username="dup1")
    dup_user_2 = UserFactory(email=dup_email, username="dup2")

    failed_users = api.sync_users_to_scim_remote([dup_user_1, dup_user_2])

    assert set(failed_users) == {dup_user_1, dup_user_2}

    dup_user_1.refresh_from_db()
    dup_user_2.refresh_from_db()

    assert dup_user_1.scim_external_id is None
    assert dup_user_2.scim_external_id is None
