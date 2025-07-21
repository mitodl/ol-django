from mitol.scim.requests import InMemoryHttpRequest


def test_from_request(rf):
    """Should be able to make an in-memory http request"""
    request = rf.get("/")
    request.META["not-str-value"] = object()

    req = InMemoryHttpRequest.from_request(
        request, request.path, request.method, "data"
    )

    assert "not-str-value" not in req.META
