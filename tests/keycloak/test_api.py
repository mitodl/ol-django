import json
from http import HTTPStatus
from uuid import uuid4

from mitol.keycloak import api
from mitol.keycloak.data_models import UserAttributes
from responses import RequestsMock


def test_update_user(responses: RequestsMock, settings):
    """Test that update user makes API calls correctly"""
    uuid = uuid4()
    initial = {
        "email": "test@example.com",
        "attributes": {
            "fullName": ["old_name"],
        },
    }

    user_get = responses.add(
        responses.GET,
        f"{settings.MITOL_KEYCLOAK_BASE_URL}/admin/realms/olapps/users/{uuid}?userProfileMetadata=False",
        json=initial,
    )
    user_put = responses.add(
        responses.PUT,
        f"{settings.MITOL_KEYCLOAK_BASE_URL}/admin/realms/olapps/users/{uuid}",
        status=HTTPStatus.NO_CONTENT,
    )

    api.update_user(uuid, attributes=UserAttributes())

    assert user_get.call_count == 1
    assert user_put.call_count == 1
    assert json.loads(user_put.calls[0].request.body) == initial

    api.update_user(uuid, attributes=UserAttributes(full_name="new_name"))

    assert user_get.call_count == 2  # noqa: PLR2004
    assert user_put.call_count == 2  # noqa: PLR2004
    assert json.loads(user_put.calls[1].request.body) == {
        **initial,
        "attributes": {
            **initial["attributes"],
            "fullName": ["new_name"],
        },
    }

    api.update_user(uuid, attributes=UserAttributes(email_optin=True))

    assert user_get.call_count == 3  # noqa: PLR2004
    assert user_put.call_count == 3  # noqa: PLR2004
    assert json.loads(user_put.calls[2].request.body) == {
        **initial,
        "attributes": {
            **initial["attributes"],
            "emailOptIn": [True],
        },
    }

    api.update_user(
        uuid, attributes=UserAttributes(full_name="new_name", email_optin=False)
    )

    assert user_get.call_count == 4  # noqa: PLR2004
    assert user_put.call_count == 4  # noqa: PLR2004
    assert json.loads(user_put.calls[3].request.body) == {
        **initial,
        "attributes": {
            **initial["attributes"],
            "fullName": ["new_name"],
            "emailOptIn": [False],
        },
    }
