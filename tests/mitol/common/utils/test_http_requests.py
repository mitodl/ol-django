"""Utils tests"""

from http import HTTPStatus

import pytest
import responses
from mitol.common.pytest_utils import MockResponse
from mitol.common.utils.http_requests import (
    get_error_response_summary,
    is_json_response,
    request_get_with_timeout_retry,
)
from requests.exceptions import HTTPError


@pytest.mark.parametrize(
    "content,content_type,exp_summary_content,exp_url_in_summary",  # noqa: PT006
    [
        ['{"bad": "response"}', "application/json", '{"bad": "response"}', False],  # noqa: PT007
        ["plain text", "text/plain", "plain text", False],  # noqa: PT007
        [  # noqa: PT007
            "<div>HTML content</div>",
            "text/html; charset=utf-8",
            "(HTML body ignored)",
            True,
        ],
    ],
)
def test_get_error_response_summary(
    content, content_type, exp_summary_content, exp_url_in_summary
):
    """
    get_error_response_summary should provide a summary of an error HTTP response object with the correct bits of
    information depending on the type of content.
    """  # noqa: E501
    status_code = 400
    url = "http://example.com"
    mock_response = MockResponse(
        status_code=status_code, content=content, content_type=content_type, url=url
    )
    summary = get_error_response_summary(mock_response)
    assert f"Response - code: {status_code}" in summary
    assert f"content: {exp_summary_content}" in summary
    assert (f"url: {url}" in summary) is exp_url_in_summary


@pytest.mark.parametrize(
    "content,content_type,expected",  # noqa: PT006
    [
        ['{"bad": "response"}', "application/json", True],  # noqa: PT007
        ["plain text", "text/plain", False],  # noqa: PT007
        ["<div>HTML content</div>", "text/html; charset=utf-8", False],  # noqa: PT007
    ],
)
def test_is_json_response(content, content_type, expected):
    """
    is_json_response should return True if the given response's content type indicates JSON content
    """  # noqa: E501
    mock_response = MockResponse(
        status_code=400, content=content, content_type=content_type
    )
    assert is_json_response(mock_response) is expected


@responses.activate
@pytest.mark.parametrize("num_failures", range(4))
def test_request_get_with_timeout_retry(mocker, num_failures):
    """request_get_with_timeout_retry should make a GET request and retry if the response status is 504 (timeout)"""  # noqa: E501
    patched_log = mocker.patch("mitol.common.utils.http_requests.log")
    url = "http://example.com/retry"
    retries = 3
    data = {"data": 1}
    for num_retry in range(retries):
        if num_retry < num_failures:
            responses.add(responses.GET, url, status=HTTPStatus.GATEWAY_TIMEOUT)
        else:
            responses.add(responses.GET, url, json=data)

    if num_failures < retries:
        result = request_get_with_timeout_retry(url, retries=retries)
        assert len(responses.calls) == num_failures + 1

        assert result.status_code == HTTPStatus.OK
        assert result.json() == data
    else:
        with pytest.raises(HTTPError):
            request_get_with_timeout_retry(url, retries=retries)

    assert patched_log.warning.call_count == num_failures
