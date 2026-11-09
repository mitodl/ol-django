"""Deciding which versions still need uploading"""

import json
import urllib.error
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from mitol.release_tools.cli import cli
from mitol.release_tools.project import Project
from mitol.release_tools.publish import ATTEMPTS, is_published

from tests.release_tools.conftest import add_package, write_workspace

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


@patch("mitol.release_tools.publish.is_published", new=lambda *_: False)
def test_a_private_distribution_is_never_in_the_matrix(repo_root):
    """`Private :: Do Not Upload` means never upload, whatever PyPI says

    The already-published check cannot catch this: an unpublished private
    package looks exactly like one that is due for release.
    """
    add_package(
        repo_root,
        "alpha",
        dist_name="alpha",
        version="1.0.0",
        module="alpha",
        bumpver=False,
        extra='classifiers = ["Private :: Do Not Upload"]\n',
    )
    add_package(
        repo_root,
        "beta",
        dist_name="beta",
        version="1.0.0",
        module="beta",
        bumpver=False,
    )
    write_workspace(repo_root, ["src/*"])

    result = CliRunner().invoke(cli, ["publish", "matrix"], obj=Project())

    assert result.exit_code == 0, result.output
    assert [e["package"] for e in json.loads(result.stdout)["include"]] == ["beta"]


@patch("mitol.release_tools.publish.is_published", new=lambda *_: False)
def test_the_skip_is_reported_without_corrupting_the_matrix(repo_root):
    """CI pipes stdout to jq, so the explanation has to go to stderr"""
    add_package(
        repo_root,
        "alpha",
        dist_name="alpha",
        version="1.0.0",
        module="alpha",
        bumpver=False,
        extra='classifiers = ["Private :: Do Not Upload"]\n',
    )
    write_workspace(repo_root, ["src/*"])

    # click 8.5 keeps the streams separate; there is no mix_stderr any more.
    result = CliRunner().invoke(cli, ["publish", "matrix"], obj=Project())

    assert json.loads(result.stdout) == {"include": []}
    assert "Private :: Do Not Upload" in result.stderr
