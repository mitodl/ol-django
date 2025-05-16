import math
import random
import uuid
from dataclasses import dataclass

import pytest
from django.contrib.auth import get_user_model
from mitol.common.factories import UserFactory
from mitol.scim import api
from responses import BaseResponse, RequestsMock, matchers

User = get_user_model()


def test_get_session(responses: RequestsMock):
    _ = responses.get(
        url="http://keycloak:8080/realms/ol-local/scim/v2/",
        json={"success": True},
        match=[matchers.header_matcher({"Authorization": "Bearer not_a_secret"})],
    )

    session = api.get_session()

    response = session.get("/")

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
def mock_search_requests(users: Users, responses: RequestsMock):
    requests: list[BaseResponse] = []
    items_per_page = 10
    for search_page_num in range(math.ceil(len(users.users) / items_per_page)):
        offset = search_page_num * items_per_page
        search_result_users = users.users[
            offset : (search_page_num + 1) * items_per_page
        ]

        request = responses.post(
            url="http://keycloak:8080/realms/ol-local/scim/v2/Users/.search",
            json={
                "Resources": [
                    {
                        "location": f"http://keycloak:8080/realms/ol-local/scim/v2/Users/{users.external_ids_by_user_id[user.id]}",
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
                            [f'email EQ "{user.email}"' for user in users.users]
                        ),
                        "startIndex": offset + 1,
                    }
                )
            ],
        )
        requests.append(request)
    return requests


@pytest.mark.django_db
@pytest.mark.parametrize("users", [50, 100], indirect=True)
@pytest.mark.parametrize("bulk_operations_count", [20])
@pytest.mark.usefixtures("responses", "mock_search_requests")
def test_sync_users_to_scim_remote(users: Users, settings, bulk_operations_count: int):
    settings.MITOL_SCIM_KEYCLOAK_BULK_OPERATIONS_COUNT = bulk_operations_count

    api.sync_users_to_scim_remote(users.users)

    for user, external_id in zip(users.users, users.external_ids):
        user.refresh_from_db()

        assert user.scim_id == user.id
        assert user.scim_external_id == external_id
