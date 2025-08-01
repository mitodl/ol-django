"""Pytest testing utils"""

import abc
import json
import logging
import traceback
from contextlib import contextmanager

import pytest


def any_instance_of(*cls):
    """
    Returns a type that evaluates __eq__ in isinstance terms

    Args:
        cls (list of types): variable list of types to ensure equality against

    Returns:
        AnyInstanceOf: dynamic class type with the desired equality
    """  # noqa: D401

    class AnyInstanceOf(metaclass=abc.ABCMeta):  # noqa: B024, PLW1641
        """Dynamic class type for __eq__ in terms of isinstance"""

        def __eq__(self, other):
            return isinstance(other, cls)

    for c in cls:
        AnyInstanceOf.register(c)
    return AnyInstanceOf()


@contextmanager
def assert_not_raises():
    """Used to assert that the context does not raise an exception"""  # noqa: D401
    try:
        yield
    except AssertionError:
        raise
    except Exception:  # noqa: BLE001
        pytest.fail(f"An exception was not raised: {traceback.format_exc()}")


class MockResponse:
    """
    Mock requests.Response
    """

    def __init__(
        self, content, status_code=200, content_type="application/json", url=None
    ):
        if isinstance(content, dict | list):
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


def test_app_json_modified():
    """
    Pytest test that verifies app.json is up-to-date

    To use this, you should import this into a test file somewhere in your project:

    from mitol.common.pytest_utils import test_app_json_modified
    """
    from mitol.common import envs  # noqa: PLC0415

    envs.reload()

    with open("app.json") as app_json_file:  # noqa: PTH123
        app_json = json.load(app_json_file)

    generated_app_json = envs.generate_app_json()

    if app_json != generated_app_json:
        logging.error(
            "Generated app.json does not match the app.json file. To fix this, run `./manage.py generate_app_json`"  # noqa: E501
        )

    # pytest will print the difference
    assert json.dumps(app_json, sort_keys=True, indent=2) == json.dumps(  # noqa: S101
        generated_app_json, sort_keys=True, indent=2
    )
