from collections.abc import Generator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model

from mitol.common.requests import SessionWithBaseUrl
from mitol.common.utils.collections import chunks

User = get_user_model()


@dataclass()
class UserState:
    user: "User"
    external_id: str


@dataclass()
class UserOperation:
    user: "User"
    bulk_id: str
    operation: dict[str, Any]


StateOrOperation = UserState | UserOperation
StateOrOperationGenerator = Generator[StateOrOperation, Any, Any]
StateGenerator = Generator[UserState, Any, Any]


def get_session() -> SessionWithBaseUrl:
    session = SessionWithBaseUrl(base_url=settings.MITOL_SCIM_KEYCLOAK_BASE_URL)
    session.headers.update(
        {"Authorization": f"Bearer {settings.MITOL_SCIM_KEYCLOAK_API_TOKEN}"}
    )
    return session


def sync_users_to_scim_remote(users: list["User"]):
    with get_session() as session:
        found_users = _user_search_by_email(session, users)
        state_or_operations = _get_sync_operations(users, found_users)
        states = _perform_sync_operations(session, state_or_operations)
        _update_users(states)


def _user_search_by_email(
    session: SessionWithBaseUrl, users: list["User"]
) -> StateOrOperationGenerator:
    """Perform a search for a set of users by email"""
    users_by_email = {user.email: user for user in users}

    payload = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:SearchRequest"],
        "filter": " or ".join([f'email eq "{email}"' for email in users_by_email]),
    }

    start_index = 1
    while True:
        resp = session.post(
            "/Users/.search",
            json={
                **payload,
                "startIndex": start_index,
            },
            timeout=settings.MITOL_SCIM_REQUESTS_TIMEOUT_SECONDS,
        )

        resp.raise_for_status()

        data = resp.json()
        resources = data["Resources"]

        for resource in resources:
            yield UserState(users_by_email[resource["email"]], resource)

        items_per_page = data["itemsPerPage"]

        if len(resources) < items_per_page:
            break

        start_index += items_per_page


def _parse_external_id_from_location(location: str) -> str:
    """Get the external id by taking the last part of the url path"""
    path = urlsplit(location).path
    return path.split("/")[-1]


def _get_sync_operations(users, found_users) -> StateOrOperationGenerator:
    """Generate the operations we need to perform"""
    missing_users = set(users)

    for user_resource in found_users:
        user = user_resource.user
        resource = user_resource.resource

        missing_users.remove(user)

        yield UserState(user, resource["id"])

    for user in missing_users:
        bulk_id = user.id
        yield UserOperation(
            user,
            bulk_id,
            {
                "method": "POST",
                "path": "/Users",
                "bulkId": bulk_id,
                "data": {
                    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
                    "email": user.email,
                    "fullName": user.name,
                    "name": {
                        "familyName": user.profile.last_name,
                        "givenName": user.profile.first_name,
                    },
                },
            },
        )


def _perform_sync_operations(
    session: SessionWithBaseUrl,
    sync_operations: StateOrOperationGenerator,
) -> StateGenerator:
    for chunk in chunks(
        sync_operations,
        chunk_size=settings.MITOL_SCIM_KEYCLOAK_BULK_OPERATIONS_COUNT,
    ):
        operations = []
        users_by_bulk_id = {}

        for state_or_operation in chunk:
            if isinstance(state_or_operation, UserState):
                yield state_or_operation
            elif isinstance(state_or_operation, UserOperation):
                operations.append(state_or_operation.operation)
                users_by_bulk_id[state_or_operation] = state_or_operation

        response = session.post(
            "/Users/Bulk/",
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:BulkRequest"],
                "Operations": operations,
            },
            timeout=settings.MITOL_SCIM_REQUESTS_TIMEOUT_SECONDS,
        )

        response.raise_for_status()

        for resource in response.json()["Resources"]:
            bulk_id = resource["bulkId"]
            location = resource["location"]
            external_id = _parse_external_id_from_location(location)
            user = users_by_bulk_id[bulk_id]

            yield UserState(user, external_id)


def _update_users(states: StateGenerator):
    """Update the users to store the scim ids"""
    updates = []

    for state in states:
        user = state.user
        user.scim_id = user.id
        user.scim_external_id = state.external_id
        updates.append(user)

    User.objects.bulk_update(updates, ["scim_id", "scim_external_id"])
