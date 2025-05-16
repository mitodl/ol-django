import math
import random
import uuid
from dataclasses import dataclass

import pytest
from django.contrib.auth import get_user_model
from mitol.common.factories import UserFactory
from mitol.scim import api
from mitol.scim.adapters import UserAdapter
from mitol.scim.requests import InMemoryHttpRequest
from more_itertools import chunked
from responses import BaseResponse, RequestsMock, matchers

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
    existing_user_ids: list[int]
    external_ids_by_user_id: dict[int, str]


@pytest.fixture
def users(request):
    users: list[User] = UserFactory.create_batch(request.param)
    existing_user_ids = [
        user.id
        for user in users
        # simulate a random selection of users already in keycloak
        if bool(random.getrandbits(1))
    ]
    external_ids_by_user_id = {user.id: str(uuid.uuid4()) for user in users}
    return Users(
        users=users,
        external_ids_by_user_id=external_ids_by_user_id,
        existing_user_ids=existing_user_ids,
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
    search_responses: list[BaseResponse] = []
    items_per_page = 10
    for search_page_num in range(math.ceil(len(users.users) / items_per_page)):
        offset = search_page_num * items_per_page
        search_result_users = users.users[
            offset : (search_page_num + 1) * items_per_page
        ]

        response = responses.post(
            url="https://keycloak:8080/realms/ol-local/scim/v2/Users/.search",
            json={
                "Resources": [
                    {
                        "location": f"https://keycloak:8080/realms/ol-local/scim/v2/Users/{users.external_ids_by_user_id[user.id]}",
                        "emails": [
                            {
                                "value": user.email,
                                "primary": True,
                            }
                        ],
                    }
                    for user in search_result_users
                    if user in search_result_users and user in users.existing_user_ids
                ],
                "itemsPerPage": items_per_page,
            },
            match=[
                matchers.json_params_matcher(
                    {
                        "schemas": [
                            "urn:ietf:params:scim:api:messages:2.0:SearchRequest"
                        ],
                        "filter": " OR ".join(
                            [f'emails.value EQ "{user.email}"' for user in users.users]
                        ),
                        "startIndex": offset + 1,
                    }
                )
            ],
        )
        search_responses.append(response)
    return search_responses


@pytest.fixture
def bulk_operations_count(request, settings):
    settings.MITOL_SCIM_KEYCLOAK_BULK_OPERATIONS_COUNT = request.param
    return request.param


@pytest.fixture
def mock_bulk_requests(
    users: Users, responses: RequestsMock, bulk_operations_count: int
):
    bulk_responses: list[BaseResponse] = []
    users_to_create = [
        user for user in users.users if user not in users.existing_user_ids
    ]

    for chunk in chunked(users_to_create, bulk_operations_count):
        response = responses.post(
            url="https://keycloak:8080/realms/ol-local/scim/v2/Users/Bulk",
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:BulkResponse"],
                "Resources": [
                    {
                        "location": f"https://keycloak:8080/realms/ol-local/scim/v2/Users/{users.external_ids_by_user_id[user.id]}",
                        "bulkId": str(user.id),
                    }
                    for user in chunk
                ],
            },
            match=[
                matchers.json_params_matcher(
                    {
                        "schemas": [
                            "urn:ietf:params:scim:api:messages:2.0:BulkRequest"
                        ],
                        "Operations": [
                            {
                                "method": "POST",
                                "path": "/Users",
                                "bulkId": str(user.id),
                                "data": UserAdapter(
                                    user, InMemoryHttpRequest.stub()
                                ).to_dict(),
                            }
                            for user in chunk
                        ],
                    }
                )
            ],
        )
        bulk_responses.append(response)
    return bulk_responses


@pytest.mark.django_db
@pytest.mark.parametrize("users", [5], indirect=True)
@pytest.mark.parametrize("bulk_operations_count", [3], indirect=True)
@pytest.mark.usefixtures(
    "responses",
    "mock_client_init_requests",
    "mock_search_requests",
    "mock_bulk_requests",
    "bulk_operations_count",
)
def test_sync_users_to_scim_remote(users: Users):
    api.sync_users_to_scim_remote(users.users)

    for user in users.users:
        user.refresh_from_db()

        assert user.scim_id == str(user.id)
        assert user.scim_external_id == users.external_ids_by_user_id[user.id]
