"""URLs utils tests"""

import pytest

from django.urls import path, re_path, include, reverse, URLPattern, URLResolver

from mitol.common.utils.urls import ensure_trailing_slash, remove_password_from_url, prefix_url_patterns



def test_ensure_trailing_slash():
    """Verify ensure_trailing_slash() enforces a single slash on the end"""
    assert ensure_trailing_slash("http://example.com") == "http://example.com/"
    assert ensure_trailing_slash("http://example.com/") == "http://example.com/"


@pytest.mark.parametrize(
    "url, expected",  # noqa: PT006
    [
        ["", ""],  # noqa: PT007
        ["http://url.com/url/here#other", "http://url.com/url/here#other"],  # noqa: PT007
        ["https://user:pass@sentry.io/12345", "https://user@sentry.io/12345"],  # noqa: PT007
    ],
)
def test_remove_password_from_url(url, expected):
    """Assert that the url is parsed and the password is not present in the returned value, if provided"""  # noqa: E501
    assert remove_password_from_url(url) == expected

# Create a simple URL pattern for testing


@pytest.mark.parametrize("prefix, expected_regex", [
     ("foo", "^foo/"),
     ("bar/", "^bar/"), 
     (None, "^"),
     ("", "^"),
])
def test_prefix_url_patterns(settings, prefix, expected_regex):
    """Test get_path_prefix_patterns with and without a prefix"""
    from django.views import View
    from django.http import HttpResponse

    def mock_view(request):
            return HttpResponse("Test")

    sub_urlpatterns = [
        re_path("^subpath-1/", mock_view, name="sub-view-1"),
    ]
    urlpatterns = [
        path("", include(sub_urlpatterns)),
        re_path("^test-1/", mock_view, name="test-view-1"),
    ]

    settings.MITOL_APP_PATH_PREFIX = prefix
    url_patterns = prefix_url_patterns(urlpatterns)
    assert url_patterns[0].pattern.regex.pattern == expected_regex
    assert urlpatterns[0].url_patterns[0].pattern.regex.pattern == "^subpath-1/"
    assert urlpatterns[1].pattern.regex.pattern == "^test-1/"