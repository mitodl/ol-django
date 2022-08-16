"""Pytest testing utils"""
import abc
import json
import logging
import traceback
from contextlib import contextmanager

import pytest

from mitol.common.envs import generate_app_json


def any_instance_of(*cls):
    """
    Returns a type that evaluates __eq__ in isinstance terms

    Args:
        cls (list of types): variable list of types to ensure equality against

    Returns:
        AnyInstanceOf: dynamic class type with the desired equality
    """

    class AnyInstanceOf(metaclass=abc.ABCMeta):
        """Dynamic class type for __eq__ in terms of isinstance"""

        def __eq__(self, other):
            return isinstance(other, cls)

    for c in cls:
        AnyInstanceOf.register(c)
    return AnyInstanceOf()


@contextmanager
def assert_not_raises():
    """Used to assert that the context does not raise an exception"""
    try:
        yield
    except AssertionError:
        raise
    except Exception:
        pytest.fail(f"An exception was not raised: {traceback.format_exc()}")


class MockResponse:
    """
    Mock requests.Response
    """

    def __init__(
        self, content, status_code=200, content_type="application/json", url=None
    ):
        if isinstance(content, (dict, list)):
            self.content = json.dumps(content)
        else:
            self.content = str(content)
        self.text = self.content
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        if url:
            self.url = url

    def json(self):
        """Return json content"""
        return json.loads(self.content)


def test_app_json_modified():  # pragma: no cover
    """
    Pytest test that verifies app.json is up-to-date

    To use this, you should import this into a test file somewhere in your project:

    from mitol.common.pytest_utils import test_app_json_modified
    """
    from mitol.common import envs

    envs.reload_settings()

    with open("app.json") as app_json_file:
        app_json = json.load(app_json_file)

    generated_app_json = generate_app_json()

    if app_json != generated_app_json:
        logging.error(
            "Generated app.json does not match the app.json file. To fix this, run `./manage.py generate_app_json`"
        )

    # pytest will print the difference
    assert json.dumps(app_json, sort_keys=True, indent=2) == json.dumps(
        generated_app_json, sort_keys=True, indent=2
    )
