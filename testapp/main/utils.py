"""Testing utils"""

import base64
import json

import faker
from django.conf import settings
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

FAKE = faker.Faker()


def set_request_session(request, session_dict):
    """
    Sets session variables on a RequestFactory object. Uses a fake response (empty
    string) for compatibility with Django 4, which no longer defaults to None.

    Args:
        request (WSGIRequest): A RequestFactory-produced request object (from RequestFactory.get(), et. al.)
        session_dict (dict): Key/value pairs of session variables to set

    Returns:
        RequestFactory: The same request object with session variables set
    """  # noqa: E501, D401
    middleware = SessionMiddleware("")
    middleware.process_request(request)
    for key, value in session_dict.items():
        request.session[key] = value
    request.session.save()
    return request


def generate_fake_apisix_payload(*, user=None):
    """Generate a faked payload for the userinfo header."""

    if user:
        user_info = {
            settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD: user.global_id,
            "email": user.email,
            "preferred_username": user.username,
            "name": user.get_full_name(),
        }
    else:
        user_info = {
            settings.MITOL_APIGATEWAY_USERINFO_ID_FIELD: FAKE.unique.uuid4(),
            "email": FAKE.unique.email(),
            "preferred_username": FAKE.unique.user_name(),
            "name": FAKE.unique.name(),
        }

    return base64.b64encode(json.dumps(user_info).encode()).decode(), user_info


def generate_apisix_request(obj_type, payload):
    """Generate a fake request object."""

    if obj_type == "request":
        # it doesn't really matter what the request URL is
        request = set_request_session(
            RequestFactory().get("/"),
            {},
        )
        AuthenticationMiddleware("").process_request(request)

        request.META = {"HTTP_X_USERINFO": payload}
        return request

    return {"headers": [(b"x-userinfo", payload.encode())]}
