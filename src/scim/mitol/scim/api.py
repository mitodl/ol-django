import http
import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django_scim.adapters import SCIMUser
from django_scim.utils import get_user_adapter
from mitol.scim.constants import SchemaURI
from mitol.scim.requests import InMemoryHttpRequest
from more_itertools import chunked, first
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

User = get_user_model()
UserAdapter: type[SCIMUser] = get_user_adapter()


log = logging.getLogger()


@dataclass()
class UserState:
    user: "User"
    external_id: str


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
        found_states = _user_search_by_email(session, users)
        found_user_ids = {state.user.id for state in found_states}
        missing_users = [user for user in users if user.id not in found_user_ids]
        created_states = _create_users(session, missing_users)
        _update_users(found_states + created_states)


def _user_search_by_email(
    session: OAuth2Session, users: list["User"]
) -> list[UserState]:
    states: list[UserState] = []
    for users_batch in chunked(users, settings.MITOL_SCIM_KEYCLOAK_SEARCH_BATCH_SIZE):
        states.extend(_user_search_by_email_batch(session, users_batch))
    return states


def _user_search_by_email_batch(
    session: OAuth2Session, users: list["User"]
) -> list[UserState]:
    """Perform a search for a set of users by email"""
    states: list[UserState] = []
    users_by_email = {user.email.lower(): user for user in users}

    payload = {
        "schemas": [SchemaURI.SERACH_REQUEST],  # typo in upstream lib
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

        resources = data.get("Resources", [])

        for resource in resources:
            email = first(
                [
                    email["value"].lower()
                    for email in resource.get("emails", [])
                    if email.get("primary", False)
                ]
            )
            if email is None:
                log.error("Unexpected user result with no email")
            elif email not in users_by_email:
                log.error(
                    "Received an email in search results that does not match: %s", email
                )
            else:
                states.append(UserState(users_by_email[email], resource["id"]))

        if not resources:
            break

        start_index += len(resources)

    return states


def _parse_external_id_from_location(location: str) -> str:
    """Get the external id by taking the last part of the url path"""
    path = urlsplit(location).path
    return path.split("/")[-1]


def _create_users(session: OAuth2Session, users: list["User"]) -> list[UserState]:
    """Bulk-create users that don't already exist on the SCIM remote"""
    states: list[UserState] = []

    for chunk in chunked(users, settings.MITOL_SCIM_KEYCLOAK_BULK_OPERATIONS_COUNT):
        if not chunk:
            # skip to the next chunk because this one had no operations
            # NOTE: this is not an indication we're at the end of chunks
            continue

        operations = []
        users_by_bulk_id: dict[str, User] = {}

        for user in chunk:
            bulk_id = str(user.id)
            adapter = UserAdapter(
                # The request is only necessary because `SCIMUser.location`
                # accesses `SCIMUser.request`, whch raises an exception if
                # the request is `None` (yay side-effecting properties).
                # However, the default location getter doesn't even use the
                # request. We create an in-memory request that would be
                # correct if it's ever used just in case.
                user,
                InMemoryHttpRequest.stub(),
            )
            operations.append(
                {
                    "method": "POST",
                    "path": "/Users",
                    "bulkId": bulk_id,
                    "data": {
                        **adapter.to_dict(),
                        "emailVerified": True,
                    },
                }
            )
            users_by_bulk_id[bulk_id] = user

        response = session.post(
            scim_api_url("/Users/Bulk"),
            json={
                "schemas": [SchemaURI.BULK_REQUEST],
                "Operations": operations,
            },
            timeout=settings.MITOL_SCIM_REQUESTS_TIMEOUT_SECONDS,
        )

        if response.status_code != http.HTTPStatus.OK:
            log.error("Error response: %s", response.json())

        response.raise_for_status()

        data = response.json()

        for operation in data["Operations"]:
            bulk_id = operation["bulkId"]
            user = users_by_bulk_id[bulk_id]

            if int(operation["status"]) != http.HTTPStatus.CREATED:
                log.error(
                    "Unable to perform operation for user: %s, response: %s",
                    str(user),
                    str(operation),
                )
                continue

            location = operation["location"]
            external_id = _parse_external_id_from_location(location)

            states.append(UserState(user, external_id))

    return states


def _update_users(states: list[UserState]):
    """Update the users to store the scim ids"""
    for batch in chunked(states, settings.MITOL_SCIM_KEYCLOAK_BULK_OPERATIONS_COUNT):
        updates = []
        for state in batch:
            user = state.user
            user.scim_id = str(user.id)  # normally done in User.save()
            user.scim_external_id = state.external_id
            user.global_id = state.external_id
            updates.append(user)

        User.objects.bulk_update(updates, ["global_id", "scim_id", "scim_external_id"])
