import json
import math
import random
import uuid
from dataclasses import dataclass
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from mitol.common.factories import UserFactory
from mitol.scim import api
from mitol.scim.adapters import UserAdapter
from mitol.scim.constants import SchemaURI
from mitol.scim.requests import InMemoryHttpRequest
from more_itertools import distribute
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
def mock_search_requests(users: Users, responses: RequestsMock):
    items_per_page = 10

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
                        for user in users.users_in_remote[
                            start_index : start_index + items_per_page
                        ]
                    ],
                    "itemsPerPage": items_per_page,
                    "totalResults": len(users.users_in_remote),
                    "startIndex": start_index,
                }
            ),
        )

    responses.add_callback(
        responses.POST,
        url="https://keycloak:8080/realms/ol-local/scim/v2/Users/.search",
        callback=_callback,
        match=[
            matchers.json_params_matcher(
                params={
                    "schemas": [SchemaURI.SERACH_REQUEST],
                    "filter": " OR ".join(
                        [
                            f'emails.value EQ "{user.email.lower()}"'
                            for user in users.users
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
