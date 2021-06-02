"""Requests utilities"""
import logging
from http import HTTPStatus

import requests
from requests import Response

log = logging.getLogger(__name__)


def get_error_response_summary(response: Response) -> str:
    """
    Returns a summary of an error raised from a failed HTTP request using the requests library

    Args:
        response (requests.Response): The requests library response object

    Returns:
        str: A summary of the error response
    """
    # If the response is an HTML document, include the URL in the summary but not the raw HTML
    if "text/html" in response.headers.get("Content-Type", ""):
        summary_dict = {"url": response.url, "content": "(HTML body ignored)"}
    else:
        summary_dict = {"content": response.text}
    summary_dict_str = ", ".join([f"{k}: {v}" for k, v in summary_dict.items()])
    return f"Response - code: {response.status_code}, {summary_dict_str}"


def is_json_response(response: Response) -> bool:
    """
    Returns True if the given response object is JSON-parseable

    Args:
        response (requests.Response): The requests library response object

    Returns:
        bool: True if this response is JSON-parseable
    """
    return response.headers.get("Content-Type") == "application/json"


def request_get_with_timeout_retry(url: str, retries: int) -> Response:
    """
    Makes a GET request, and retries if the server responds with a 504 (timeout)

    Args:
        url (str): The URL of the Mailgun API endpoint
        retries (int): The number of times to retry the request

    Returns:
        response (requests.models.Response): The requests library response object

    Raises:
        requests.exceptions.HTTPError: Raised if the response has a status code indicating an error
    """
    resp = requests.get(url)
    # If there was a timeout (504), retry before giving up
    tries = 1
    while resp.status_code == HTTPStatus.GATEWAY_TIMEOUT and tries <= retries:
        tries += 1
        log.warning(
            "GET request timed out (%s). Retrying for attempt %d...", url, tries
        )
        resp = requests.get(url)
    resp.raise_for_status()
    return resp
