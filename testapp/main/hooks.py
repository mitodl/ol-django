"""Hooks for exercising the apigateway user sync hook mechanism in tests."""


def record_user_sync(*, request, user, decoded_headers, created):
    """No-op sync hook; tests patch this to assert hook invocations."""
