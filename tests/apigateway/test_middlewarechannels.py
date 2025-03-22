"""Test the Django Channels middleware."""

import pytest
from django.contrib.auth.models import AnonymousUser
from mitol.apigateway.middleware_channels import ApisixUserMiddleware

from testapp.main.utils import generate_fake_apisix_payload

pytestmark = [pytest.mark.django_db]


class MockApplication:
    """Mock Channels application."""

    async def __call__(self, scope, receive, send):
        """Start the mocked application."""

        return (scope, receive, send)


@pytest.fixture()
def application():
    """Return a fake application."""

    return MockApplication()


@pytest.fixture()
def scope():
    """Return a fake scope."""

    payload = generate_fake_apisix_payload()
    return {
        "user": AnonymousUser,
        "session": {},
        "headers": [
            (b"host", b"localhost:8000"),
            (b"connection", b"upgrade"),
            (b"upgrade", b"websocket"),
            (b"x-userinfo", payload[0]),
        ],
    }


@pytest.mark.asyncio()
async def test_middleware(application, scope):
    """Construct a fake scope and see if the middleware attaches the user."""

    middleware = ApisixUserMiddleware(application)

    (
        result_scope,
        _,
        _,
    ) = await middleware(scope, "", "")
    assert result_scope["user"] is not None
    assert result_scope["user"].is_authenticated
