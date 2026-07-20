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
from more_itertools import chunked, first, partition
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


def sync_users_to_scim_remote(users: list["User"]) -> list["User"]:
    """
    Sync the given users to the SCIM remote (Keycloak).

    A failure searching or creating a subset of users (a bad chunk, a
    single rejected bulk operation, etc.) does not abort the rest of the
    run. Users that couldn't be confirmed/created are returned so the
    caller can re-queue just that subset instead of losing or blindly
    re-processing the whole batch.
    """
    with get_session() as session:
        # Users we've already synced before have a durable join key
        # (scim_external_id, aka global_id) - use it directly instead of
        # re-matching on email, which silently drops/duplicates users whose
        # email changed or doesn't case-normalize to an exact match.
        # Users we've never synced have no such key yet, so email is the
        # only bootstrap option.
        unknown_users_iter, known_users_iter = partition(
            lambda user: bool(user.scim_external_id), users
        )
        known_users, unknown_users = list(known_users_iter), list(unknown_users_iter)

        found_states: list[UserState] = []
        failed_users: list[User] = []

        id_states, id_failures = _user_search_by_id(session, known_users)
        found_states.extend(id_states)
        failed_users.extend(id_failures)

        email_states, email_failures = _user_search_by_email(session, unknown_users)
        found_states.extend(email_states)
        failed_users.extend(email_failures)

        failed_user_ids = {user.id for user in failed_users}
        found_user_ids = {state.user.id for state in found_states}
        missing_users = [
            user
            for user in users
            if user.id not in found_user_ids and user.id not in failed_user_ids
        ]

        created_states, create_failures = _create_missing_users(session, missing_users)
        found_states.extend(created_states)
        failed_users.extend(create_failures)

        _update_users(found_states)

    return failed_users


def _search_batches(
    session: OAuth2Session,
    users: list["User"],
    *,
    batch_size: int,
    build_filter,
    match_key,
) -> tuple[list[UserState], list["User"]]:
    """
    Shared paging/error-isolation logic for the id- and email-based searches.

    ``build_filter(batch)`` returns the SCIM filter string for a batch of
    users. ``match_key(resource)`` extracts the join key from a returned
    resource so it can be matched back to the requesting user. A batch that
    fails outright (HTTP error) is recorded as failed rather than aborting
    the remaining batches.
    """
    states: list[UserState] = []
    failed: list[User] = []

    for batch in chunked(users, batch_size):
        keys = [match_key(user) for user in batch]
        if len(set(keys)) != len(keys):
            # a duplicate/blank key means we can't safely tell which local
            # user a returned resource belongs to - matching one could
            # silently attach a remote user to the wrong local user, and
            # falling through to create would produce a duplicate for
            # whichever user we guessed wrong. Fail the whole batch instead.
            log.error(
                "Duplicate match key(s) in a batch of %d user(s); "
                "cannot safely reconcile, reporting the batch as failed",
                len(batch),
            )
            failed.extend(batch)
            continue

        users_by_key = dict(zip(keys, batch))

        payload = {
            "schemas": [SchemaURI.SERACH_REQUEST],  # typo in upstream lib
            "filter": build_filter(batch),
        }

        start_index = 1
        batch_failed = False

        while True:
            try:
                resp = session.post(
                    scim_api_url("/Users/.search"),
                    json={
                        **payload,
                        "startIndex": start_index,
                    },
                    timeout=settings.MITOL_SCIM_REQUESTS_TIMEOUT_SECONDS,
                )
                resp.raise_for_status()
            except requests.RequestException:
                log.exception(
                    "SCIM search request failed for a batch of %d user(s); "
                    "will be reported as failed rather than risk a duplicate create",
                    len(batch),
                )
                batch_failed = True
                break

            data = resp.json()
            resources = data.get("Resources", [])

            for resource in resources:
                key = match_key(resource)
                if key is None:
                    log.error("Unexpected user result with no matchable key")
                elif key not in users_by_key:
                    log.error(
                        "Received a SCIM search result that does not match "
                        "any requested user: %s",
                        key,
                    )
                else:
                    states.append(UserState(users_by_key[key], resource["id"]))

            if not resources:
                break

            start_index += len(resources)

        # a genuinely-absent user (search succeeded, remote just doesn't have
        # them yet) is NOT a failure - it falls through to _create_missing_users.
        # only a batch we couldn't get an answer for at all is a failure, since
        # we can't tell whether creating them would produce a duplicate.
        if batch_failed:
            failed.extend(batch)

    return states, failed


def _user_search_by_id(
    session: OAuth2Session, users: list["User"]
) -> tuple[list[UserState], list["User"]]:
    """Look up already-synced users by their SCIM external id (global_id)."""
    return _search_batches(
        session,
        users,
        batch_size=settings.MITOL_SCIM_KEYCLOAK_SEARCH_BATCH_SIZE,
        build_filter=lambda batch: " OR ".join(
            [f'id EQ "{user.scim_external_id}"' for user in batch]
        ),
        match_key=lambda obj: (
            obj.scim_external_id if isinstance(obj, User) else obj.get("id")
        ),
    )


def _user_search_by_email(
    session: OAuth2Session, users: list["User"]
) -> tuple[list[UserState], list["User"]]:
    """Look up never-synced users by email (no other join key exists yet)."""

    def _email_key(obj):
        if isinstance(obj, User):
            return obj.email.lower()

        return first(
            [
                email["value"].lower()
                for email in obj.get("emails", [])
                if email.get("primary", False)
            ],
            default=None,
        )

    return _search_batches(
        session,
        users,
        batch_size=settings.MITOL_SCIM_KEYCLOAK_SEARCH_BATCH_SIZE,
        build_filter=lambda batch: " OR ".join(
            [f'emails.value EQ "{user.email.lower()}"' for user in batch]
        ),
        match_key=_email_key,
    )


def _parse_external_id_from_location(location: str) -> str:
    """Get the external id by taking the last part of the url path"""
    path = urlsplit(location).path
    return path.split("/")[-1]


def _create_missing_users(
    session: OAuth2Session, users: list["User"]
) -> tuple[list[UserState], list["User"]]:
    """Bulk-create users that don't already exist on the SCIM remote"""
    states: list[UserState] = []
    failed: list[User] = []

    for chunk in chunked(users, settings.MITOL_SCIM_KEYCLOAK_BULK_OPERATIONS_COUNT):
        operations = []
        users_by_bulk_id: dict[str, User] = {}

        for user in chunk:
            bulk_id = str(user.id)
            adapter = UserAdapter(
                # The request is only necessary because `SCIMUser.location`
                # accesses `SCIMUser.request`, which raises an exception if
                # the request is `None` (yay side-effecting properties).
                # However, the default location getter doesn't even use the
                # request. We create an in-memory request that would be
                # correct if it's ever used just in case.
                user,
                InMemoryHttpRequest.stub(),
                lock_user=False,
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

        try:
            response = session.post(
                scim_api_url("/Users/Bulk"),
                json={
                    "schemas": [SchemaURI.BULK_REQUEST],
                    "Operations": operations,
                },
                timeout=settings.MITOL_SCIM_REQUESTS_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException:
            # isolate the failure to this chunk - a 5xx/timeout here used to
            # abort every remaining chunk in the batch (up to 1000 users)
            log.exception(
                "SCIM bulk create failed for a chunk of %d user(s)", len(chunk)
            )
            failed.extend(chunk)
            continue

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
                failed.append(user)
                continue

            location = operation["location"]
            external_id = _parse_external_id_from_location(location)

            states.append(UserState(user, external_id))

    return states, failed


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
