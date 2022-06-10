"""Testing utils"""

from django.contrib.sessions.middleware import SessionMiddleware


def set_request_session(request, session_dict):
    """
    Sets session variables on a RequestFactory object
    Args:
        request (WSGIRequest): A RequestFactory-produced request object (from RequestFactory.get(), et. al.)
        session_dict (dict): Key/value pairs of session variables to set

    Returns:
        RequestFactory: The same request object with session variables set
    """
    middleware = SessionMiddleware()
    middleware.process_request(request)
    for key, value in session_dict.items():
        request.session[key] = value
    request.session.save()
    return request
