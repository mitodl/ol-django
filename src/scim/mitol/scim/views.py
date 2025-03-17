"""SCIM view customizations"""

import copy
import json
import logging
from http import HTTPStatus
from urllib.parse import urljoin, urlparse

from django.http import HttpRequest, HttpResponse
from django.urls import Resolver404, resolve, reverse
from django_scim import constants as djs_constants
from django_scim import exceptions
from django_scim import views as djs_views
from django_scim.utils import get_base_scim_location_getter

from mitol.scim import constants

log = logging.getLogger()


class InMemoryHttpRequest(HttpRequest):
    """
    A spoofed HttpRequest that only exists in-memory.
    It does not implement all features of HttpRequest and is only used
    for the bulk SCIM operations here so we can reuse view implementations.
    """

    def __init__(self, request, path, method, body):
        super().__init__()

        self.META = copy.deepcopy(
            {
                key: value
                for key, value in request.META.items()
                if not key.startswith(("wsgi", "uwsgi"))
            }
        )
        self.path = path
        self.method = method
        self.content_type = djs_constants.SCIM_CONTENT_TYPE

        # normally HttpRequest would read this in, but we already have the value
        self._body = body


class BulkView(djs_views.SCIMView):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):  # noqa: ARG002
        body = self.load_body(request.body)

        if body.get("schemas") != [constants.SchemaURI.BULK_REQUEST]:
            msg = "Invalid schema uri. Must be SearchRequest."
            raise exceptions.BadRequestError(msg)

        fail_on_errors = body.get("failOnErrors", None)

        if fail_on_errors is not None and isinstance(int, fail_on_errors):
            msg = "Invalid failOnErrors. Must be an integer."
            raise exceptions.BaseRequestError(msg)

        operations = body.get("Operations")

        results = self._attempt_operations(request, operations, fail_on_errors)

        response = {
            "schemas": [constants.SchemaURI.BULK_RESPONSE],
            "Operations": results,
        }

        content = json.dumps(response)

        return HttpResponse(
            content=content,
            content_type=djs_constants.SCIM_CONTENT_TYPE,
            status=HTTPStatus.OK,
        )

    def _attempt_operations(self, request, operations, fail_on_errors):
        """Attempt to run the operations that were passed"""
        responses = []
        num_errors = 0

        for operation in operations:
            # per-spec,if we've hit the error threshold stop processing and return
            if fail_on_errors is not None and num_errors >= fail_on_errors:
                break

            op_response = self._attempt_operation(request, operation)

            # if the operation returned a non-2xx status code, record it as a failure
            if int(op_response.get("status")) >= HTTPStatus.MULTIPLE_CHOICES:
                num_errors += 1

            responses.append(op_response)

        return responses

    def _attempt_operation(self, bulk_request, operation):
        """Attempt an operation as part of a bulk request"""

        method = operation.get("method")
        bulk_id = operation.get("bulkId")
        path = operation.get("path")
        data = operation.get("data")

        try:
            url_match = resolve(path, urlconf="django_scim.urls")
        except Resolver404:
            return self._operation_error(
                bulk_id,
                HTTPStatus.NOT_IMPLEMENTED,
                "Endpoint is not supported for /Bulk",
            )

        # this is an ephemeral request not tied to the real request directly
        op_request = InMemoryHttpRequest(
            bulk_request, path, method, json.dumps(data).encode(djs_constants.ENCODING)
        )

        op_response = url_match.func(op_request, *url_match.args, **url_match.kwargs)
        result = {
            "method": method,
            "bulkId": bulk_id,
            "status": str(op_response.status_code),
        }

        location = None

        if op_response.status_code >= HTTPStatus.BAD_REQUEST and op_response.content:
            result["response"] = json.loads(op_response.content.decode("utf-8"))

        location = op_response.headers.get("Location", None)

        if location is not None:
            result["location"] = location
            # this is a custom field that the scim-for-keycloak plugin requires
            try:
                path = urlparse(location).path
                location_match = resolve(path)
                # this URL will be something like /scim/v2/Users/12345
                # resolving it gives the uuid
                result["id"] = location_match.kwargs["uuid"]
            except Resolver404:
                log.exception("Unable to resolve resource url: %s", location)

        return result

    def _operation_error(self, method, bulk_id, status_code, detail):
        """Return a failure response"""
        status_code = str(status_code)
        return {
            "method": method,
            "status": status_code,
            "bulkId": bulk_id,
            "response": {
                "schemas": [djs_constants.SchemaURI.ERROR],
                "status": status_code,
                "detail": detail,
            },
        }


class SearchView(djs_views.UserSearchView):
    """
    View for /.search endpoint
    """

    def post(self, request, *args, **kwargs):  # noqa: ARG002
        body = self.load_body(request.body)
        if body.get("schemas") != [djs_constants.SchemaURI.SERACH_REQUEST]:
            msg = "Invalid schema uri. Must be SearchRequest."
            raise exceptions.BadRequestError(msg)

        # cast to ints because scim-for-keycloak sends strings
        start = int(body.get("startIndex", 1))
        count = int(body.get("count", 50))
        sort_by = body.get("sortBy", "id")
        sort_order = body.get("sortOrder", "ascending")
        query = body.get("filter", None)

        if sort_by not in constants.VALID_SORTS:
            msg = f"Sorting only supports: {', '.join(constants.VALID_SORTS)}"
            raise exceptions.BadRequestError(msg)
        else:
            sort_by = constants.SORT_MAPPING[sort_by]

        if sort_order not in ("ascending", "descending"):
            msg = "Sorting only supports ascending or descending"
            raise exceptions.BadRequestError(msg)

        if not query:
            msg = "No filter query specified"
            raise exceptions.BadRequestError(msg)

        try:
            qs = self.__class__.parser_getter().search(query, request)
        except ValueError as e:
            msg = "Invalid filter/search query: " + str(e)
            raise exceptions.BadRequestError(msg) from e

        qs = qs.order_by(sort_by)

        if sort_order == "descending":
            qs = qs.reverse()

        response = self._build_response(request, qs, start, count)

        path = reverse(self.scim_adapter.url_name)
        url = urljoin(get_base_scim_location_getter()(request=request), path).rstrip(
            "/"
        )
        response["Location"] = url + "/.search"
        return response
