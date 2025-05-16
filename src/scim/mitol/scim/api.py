import http
import logging
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django_scim.adapters import SCIMUser
from django_scim.utils import get_user_adapter
from more_itertools import chunked, first
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

from mitol.scim.requests import InMemoryHttpRequest

User = get_user_model()
UserAdapter: type[SCIMUser] = get_user_adapter()


log = logging.getLogger()


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


def realm_api_url(path: str) -> str:
    base_url: str = settings.MITOL_SCIM_KEYCLOAK_BASE_URL
    base_url = base_url.rstrip("/")
    path = path.lstrip("/")
    return f"{base_url}/{path}"


def scim_api_url(path: str) -> str:
    path = path.lstrip("/")
    return realm_api_url(f"/scim/v2/{path}")


def oidc_discovery_url():
    return realm_api_url("/.well-known/openid-configuration")


def get_openid_configuration():
    response = requests.get(
        oidc_discovery_url(), timeout=settings.MITOL_SCIM_REQUESTS_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    return response.json()


def get_session() -> OAuth2Session:
    openid_config = get_openid_configuration()
    client_id = settings.MITOL_SCIM_KEYCLOAK_CLIENT_ID
    client_secret = settings.MITOL_SCIM_KEYCLOAK_CLIENT_SECRET

    token_url = openid_config["token_endpoint"]
    client = BackendApplicationClient(client_id=client_id)
    oauth = OAuth2Session(client=client)
    token = oauth.fetch_token(
        token_url=token_url,
        client_id=client_id,
        client_secret=client_secret,
    )

    return OAuth2Session(token=token)


def sync_users_to_scim_remote(users: list["User"]):
    with get_session() as session:
        found_users = _user_search_by_email(session, users)
        state_or_operations = _get_sync_operations(users, found_users)
        states = _perform_sync_operations(session, state_or_operations)
        _update_users(states)


def _user_search_by_email(
    session: OAuth2Session, users: list["User"]
) -> StateOrOperationGenerator:
    """Perform a search for a set of users by email"""
    users_by_email = {user.email: user for user in users}

    payload = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:SearchRequest"],
        "filter": " OR ".join(
            [f'emails.value EQ "{email}"' for email in users_by_email]
        ),
    }

    start_index = 1
    while True:
        resp = session.post(
            scim_api_url("/Users/.search"),
            json={
                **payload,
                "startIndex": start_index,
            },
            timeout=settings.MITOL_SCIM_REQUESTS_TIMEOUT_SECONDS,
        )

        if resp.status_code != http.HTTPStatus.OK:
            log.error("Error response: %s", resp.json())

        resp.raise_for_status()

        data = resp.json()
        print(data)

        resources = data["Resources"]

        for resource in resources:
            email = first(
                [
                    email["value"]
                    for email in resource.get("emails", [])
                    if email.get("primary", False)
                ]
            )
            if email is not None:
                yield UserState(users_by_email[email], resource)

        items_per_page = data["itemsPerPage"]

        if len(resources) < items_per_page:
            break

        start_index += items_per_page


def _parse_external_id_from_location(location: str) -> str:
    """Get the external id by taking the last part of the url path"""
    path = urlsplit(location).path
    return path.split("/")[-1]


def _get_sync_operations(
    users: list["User"], found_users: StateOrOperationGenerator
) -> StateOrOperationGenerator:
    """Generate the operations we need to perform"""
    missing_users = set(users)

    for user_resource in found_users:
        user = user_resource.user

        missing_users.remove(user)

        yield UserState(user=user, external_id=user_resource.external_id)

    for user in missing_users:
        bulk_id = str(user.id)
        adapter = UserAdapter(
            # The request is only necessary because `SCIMUser.location` accesses
            # `SCIMUser.request`, whch raises an exception if the request is
            # `None` (yay side-effecting properties). However, the default
            # location getter doesn't even use the request. We create an in-memory
            # request that would be correct if it's ever used just in case.
            user,
            InMemoryHttpRequest.stub(),
        )
        yield UserOperation(
            user,
            bulk_id,
            {
                "method": "POST",
                "path": "/Users",
                "bulkId": bulk_id,
                "data": adapter.to_dict(),
            },
        )


def _perform_sync_operations(
    session: OAuth2Session,
    sync_operations: StateOrOperationGenerator,
) -> StateGenerator:
    for chunk in chunked(
        sync_operations,
        settings.MITOL_SCIM_KEYCLOAK_BULK_OPERATIONS_COUNT,
    ):
        operations = []
        users_by_bulk_id: dict[int, User] = {}

        for state_or_operation in chunk:
            if isinstance(state_or_operation, UserState):
                yield state_or_operation
            elif isinstance(state_or_operation, UserOperation):
                operations.append(state_or_operation.operation)
                users_by_bulk_id[state_or_operation.bulk_id] = state_or_operation.user

        response = session.post(
            scim_api_url("/Users/Bulk"),
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:BulkRequest"],
                "Operations": operations,
            },
            timeout=settings.MITOL_SCIM_REQUESTS_TIMEOUT_SECONDS,
        )

        response.raise_for_status()

        data = response.json()

        for resource in data["Operations"]:
            bulk_id = resource["bulkId"]
            user = users_by_bulk_id[bulk_id]

            if resource["status"] != http.HTTPStatus.CREATED:
                log.error(
                    "Unable to create user %s, response: %s",
                    user.email,
                    str(resource["response"]),
                )
                continue

            location = resource["location"]
            external_id = _parse_external_id_from_location(location)

            yield UserState(user, external_id)


def _update_users(states: StateGenerator):
    """Update the users to store the scim ids"""
    updates = []

    for state in states:
        user = state.user
        user.scim_id = str(user.id)  # normally done in User.save()
        user.scim_external_id = state.external_id
        updates.append(user)

    User.objects.bulk_update(updates, ["scim_id", "scim_external_id"])
