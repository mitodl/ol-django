"""URLs utils tests"""
import pytest

from mitol.common.utils.urls import ensure_trailing_slash, remove_password_from_url


def test_ensure_trailing_slash():
    """Verify ensure_trailing_slash() enforces a single slash on the end"""
    assert ensure_trailing_slash("http://example.com") == "http://example.com/"
    assert ensure_trailing_slash("http://example.com/") == "http://example.com/"


@pytest.mark.parametrize(
    "url, expected",
    [
        ["", ""],
        ["http://url.com/url/here#other", "http://url.com/url/here#other"],
        ["https://user:pass@sentry.io/12345", "https://user@sentry.io/12345"],
    ],
)
def test_remove_password_from_url(url, expected):
    """Assert that the url is parsed and the password is not present in the returned value, if provided"""
    assert remove_password_from_url(url) == expected
