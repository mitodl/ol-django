"""SCIM view customizations"""

import json
import logging
from contextlib import contextmanager
from http import HTTPStatus
from urllib.parse import urljoin, urlparse

from django.db import transaction
from django.db.utils import IntegrityError as DatabaseIntegrityError
from django.http import HttpResponse
from django.urls import Resolver404, resolve, reverse
from django_scim import constants as djs_constants
from django_scim import exceptions
from django_scim import views as djs_views
from django_scim.settings import scim_settings
from django_scim.utils import get_base_scim_location_getter
from mitol.scim import constants
from mitol.scim.requests import InMemoryHttpRequest

log = logging.getLogger(__name__)

INTEGRITY_ERROR_DETAIL = "The write conflicts with a constraint on the resource."


@contextmanager
def redact_integrity_errors(request):
    """
    Turn a failed database constraint into a SCIM 409 that carries no row data.

    ``django_scim`` puts ``str(e)`` from the database driver into the response
    body. On Postgres that is the whole error, including the ``DETAIL`` line
    echoing the failing row, and ``EXPOSE_SCIM_EXCEPTIONS`` does not gate it
    because ``django_scim.exceptions.IntegrityError`` is already a
    ``SCIMException``. The database text goes to the application log instead,
    and the client gets a status it can act on rather than the row it sent.

    The ``PATCH`` path has no such cast at all, so this is also what keeps an
    integrity error there from becoming a 500 that a client will retry.

    :param request: the request being handled, named in the log message
    """
    try:
        yield
    except (DatabaseIntegrityError, exceptions.IntegrityError) as exc:
        detail = exc.detail if isinstance(exc, exceptions.SCIMException) else str(exc)
        log.exception(
            "SCIM %s %s failed a database constraint: %s",
            request.method,
            request.path,
            detail,
        )
        if not scim_settings.EXPOSE_SCIM_EXCEPTIONS:
            detail = INTEGRITY_ERROR_DETAIL
        raise exceptions.IntegrityError(detail) from exc


class SCIMWriteMixin:
    """
    Run every write verb in a transaction and redact its integrity errors.

    ``SCIMView.dispatch`` holds the try/except that turns an exception into a
    response, so there is no hook between it and the handler to put this on.
    Each verb has to be wrapped where it is defined.
    """

    def post(self, request, *args, **kwargs):
        with redact_integrity_errors(request), transaction.atomic():
            return super().post(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        with redact_integrity_errors(request), transaction.atomic():
            return super().put(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        with redact_integrity_errors(request), transaction.atomic():
            return super().patch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        with redact_integrity_errors(request), transaction.atomic():
            return super().delete(request, *args, **kwargs)


class UsersView(SCIMWriteMixin, djs_views.UsersView):
    """Users endpoint"""


class GroupsView(SCIMWriteMixin, djs_views.GroupsView):
    """
    Groups endpoint.

    ``mitol.scim.urls`` mounts ``django_scim.urls`` alongside its own patterns,
    so without this the Groups endpoint is live on the stock view and leaks the
    driver's error text exactly as Users did.
    """


class BulkView(djs_views.SCIMView):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):  # noqa: ARG002
        body = self.load_body(request.body)

        if body.get("schemas") != [constants.SchemaURI.BULK_REQUEST]:
            msg = "Invalid schema uri. Must be SearchRequest."
            raise exceptions.BadRequestError(msg)

        fail_on_errors = body.get("failOnErrors", None)

        if fail_on_errors is not None and not isinstance(fail_on_errors, int):
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
            url_match = resolve(path, urlconf="mitol.scim.bulk_urls")
        except Resolver404:
            return self._operation_error(
                method,
                bulk_id,
                HTTPStatus.NOT_IMPLEMENTED,
                f"Endpoint {method} {path} is not supported for /Bulk",
            )

        # this is an ephemeral request not tied to the real request directly
        op_request = InMemoryHttpRequest.from_request(
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
