"""Test the Django Channels middleware."""

import base64
import json

import pytest
from asgiref.sync import sync_to_async
from channels.auth import UserLazyObject
from django.contrib.auth import get_user_model
from mitol.apigateway.middleware_channels import ApisixUserMiddleware
from mitol.common.factories.defaults import SsoUserFactory

from testapp.main.utils import generate_fake_apisix_payload

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]
User = get_user_model()


async def application(scope, receive, send):
    """Stand in for the Channels application, returning what it was called with."""

    return (scope, receive, send)


def make_scope(userinfo_header=None):
    """
    Build a websocket scope as Channels' SessionMiddleware would pass it on.

    The user is a real UserLazyObject, so a user that never gets resolved raises
    instead of passing for authenticated.
    """

    headers = [
        (b"host", b"localhost:8000"),
        (b"connection", b"upgrade"),
        (b"upgrade", b"websocket"),
    ]
    if userinfo_header is not None:
        headers.append((b"x-userinfo", userinfo_header.encode()))

    return {"user": UserLazyObject(), "session": {}, "headers": headers}


async def run_middleware(scope):
    """Run the scope through the middleware, returning the resolved user."""

    result_scope, _, _ = await ApisixUserMiddleware(application)(scope, None, None)
    user = result_scope["user"]
    # Force the lazy object to resolve here, while still in the test.
    user.is_authenticated  # noqa: B018
    return user


async def test_middleware_creates_user():
    """A new gateway user is created and attached to the scope."""

    payload, user_info = generate_fake_apisix_payload()

    user = await run_middleware(make_scope(payload))

    assert user.is_authenticated
    assert user.global_id == user_info["sub"]
    assert await User.objects.filter(global_id=user_info["sub"]).aexists()


async def test_middleware_existing_user():
    """An existing gateway user is resolved and attached to the scope."""

    test_user = await sync_to_async(SsoUserFactory.create)()
    payload, _ = generate_fake_apisix_payload(user=test_user)

    user = await run_middleware(make_scope(payload))

    assert user.is_authenticated
    assert user.pk == test_user.pk


async def test_middleware_no_header():
    """Without the header the scope user is anonymous."""

    user = await run_middleware(make_scope())

    assert user.is_anonymous


async def test_middleware_malformed_header():
    """A header that isn't a base64-encoded JSON object leaves the user anonymous."""

    header = base64.b64encode(json.dumps(["a", "list"]).encode()).decode()

    user = await run_middleware(make_scope(header))

    assert user.is_anonymous


async def test_middleware_rejected_user(settings):
    """A header user the backend rejects leaves the scope user anonymous."""

    settings.MITOL_APIGATEWAY_USERINFO_CREATE = False
    payload, _ = generate_fake_apisix_payload()

    user = await run_middleware(make_scope(payload))

    assert user.is_anonymous
