import copy

from django.http import HttpRequest
from django_scim import constants as djs_constants


class InMemoryHttpRequest(HttpRequest):
    """
    A spoofed HttpRequest that only exists in-memory.
    It does not implement all features of HttpRequest and is only used
    for the bulk SCIM operations here so we can reuse view implementations.
    """

    @classmethod
    def from_request(cls, request: HttpRequest, path: str, method: str, body: str):
        return cls(request.META, path, method, body)

    def __init__(self, meta: dict[str, str], path: str, method: str, body: str):
        super().__init__()

        self.META = copy.deepcopy(
            {
                key: value
                for key, value in meta.items()
                if not key.startswith(("wsgi", "uwsgi"))
            }
        )
        self.path = path
        self.method = method
        self.content_type = djs_constants.SCIM_CONTENT_TYPE

        # normally HttpRequest would read this in, but we already have the value
        self._body = body
