"""Deciding which versions still need uploading"""

import urllib.error
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from mitol.release_tools.publish import ATTEMPTS, is_published

# `new=` rather than a bare @patch so the sleep is not injected as an argument:
# the tests care that retrying happens, not how long it waits.
no_delay = patch("time.sleep", new=MagicMock())


def response(status):
    """Stand in for urlopen's return value, which is a context manager"""
    reply = MagicMock()
    reply.__enter__.return_value.status = status

    return reply


def http_error(code):
    """Build the HTTPError urlopen raises for a non-2xx response"""
    return urllib.error.HTTPError("url", code, "", {}, None)


@patch("urllib.request.urlopen")
def test_a_published_version_is_published(urlopen):
    urlopen.return_value = response(HTTPStatus.OK)

    assert is_published("mitol-django-common", "2026.10.30") is True


@no_delay
@patch("urllib.request.urlopen")
def test_a_missing_version_is_not_published(urlopen):
    """404 is the one error that answers the question, so it is not retried"""
    urlopen.side_effect = http_error(HTTPStatus.NOT_FOUND)

    assert is_published("mitol-django-common", "3000.1.1") is False
    assert urlopen.call_count == 1


@no_delay
@patch("urllib.request.urlopen")
def test_a_blip_is_retried_then_answered(urlopen):
    urlopen.side_effect = [http_error(HTTPStatus.BAD_GATEWAY), response(HTTPStatus.OK)]

    assert is_published("mitol-django-common", "2026.10.30") is True


@pytest.mark.parametrize(
    "error",
    [http_error(HTTPStatus.TOO_MANY_REQUESTS), urllib.error.URLError("down")],
)
@no_delay
@patch("urllib.request.urlopen")
def test_an_unreachable_pypi_raises_rather_than_guessing(urlopen, error):
    """Anything but a 404 leaves the answer unknown

    Guessing "unpublished" would republish an existing release; guessing
    "published" would silently skip a real one.
    """
    urlopen.side_effect = error

    with pytest.raises((urllib.error.HTTPError, urllib.error.URLError)):
        is_published("mitol-django-common", "2026.10.30")

    assert urlopen.call_count == ATTEMPTS
