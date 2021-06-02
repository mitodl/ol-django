"""Tests for environment variable parsing functions"""
import json

import pytest
from django.core.exceptions import ImproperlyConfigured

from mitol.common import envs

FAKE_ENVIRONS = {
    "TRUE": "True",
    "FALSE": "False",
    "POSITIVE": "123",
    "NEGATIVE": "-456",
    "ZERO": "0",
    "FLOAT": "1.1",
    "EXPRESSION": "123-456",
    "NONE": "None",
    "STRING": "a b c d e f g",
    "LIST_OF_INT": "[3,4,5]",
    "LIST_OF_STR": '["x", "y", \'z\']',
    "LIST_DELIMITED": "x, y, z",
}


@pytest.fixture(autouse=True)
def clean_env(mocker):
    """Clean the configured environment variables before a test"""
    mocker.patch.dict("os.environ", FAKE_ENVIRONS, clear=True)
    envs.env.reload()


def test_get_string():
    """get_string should get the string from the environment variable"""
    for key, value in FAKE_ENVIRONS.items():
        assert (
            envs.get_string(name=key, default="default", description="description")
            == value
        )
    assert (
        envs.get_string(name="missing", default="default", description="description")
        == "default"
    )


def test_get_int():
    """get_int should get the int from the environment variable, or raise an exception if it's not parseable as an int"""
    assert envs.get_int(name="POSITIVE", default=1234, description="description") == 123
    assert (
        envs.get_int(name="NEGATIVE", default=1234, description="description") == -456
    )
    assert envs.get_int(name="ZERO", default=1234, description="description") == 0

    for key, value in FAKE_ENVIRONS.items():
        if key not in ("POSITIVE", "NEGATIVE", "ZERO"):
            with pytest.raises(envs.EnvironmentVariableParseException) as ex:
                envs.get_int(name=key, default=1234, description="description")
            assert ex.value.args[
                0
            ] == "Expected value in {key}={value} to be an int".format(
                key=key, value=value
            )

    assert (
        envs.get_int(name="missing", default=1_234_567_890, description="description")
        == 1_234_567_890
    )


def test_get_bool():
    """get_bool should get the bool from the environment variable, or raise an exception if it's not parseable as a bool"""
    assert envs.get_bool(name="TRUE", default=1234, description="description") is True
    assert envs.get_bool(name="FALSE", default=1234, description="description") is False

    for key, value in FAKE_ENVIRONS.items():
        if key not in ("TRUE", "FALSE"):
            with pytest.raises(envs.EnvironmentVariableParseException) as ex:
                envs.get_bool(name=key, default=1234, description="description")
            assert ex.value.args[
                0
            ] == "Expected value in {key}={value} to be a boolean".format(
                key=key, value=value
            )

    assert (
        envs.get_bool(name="missing_true", default=True, description="description")
        is True
    )
    assert (
        envs.get_bool(name="missing_false", default=False, description="description")
        is False
    )


def test_get_delimited_list():
    """get_delimited_list should parse a list of strings"""
    assert envs.get_delimited_list(
        name="LIST_DELIMITED", default=["noth", "ing"], description="description"
    ) == ["x", "y", "z"]
    assert envs.get_delimited_list(
        name="LIST_MISSING", default=["noth", "ing"], description="description"
    ) == ["noth", "ing"]


def test_get_list_literal():
    """get_list_literal should parse a list of strings"""
    assert envs.get_list_literal(
        name="LIST_OF_STR", default=["noth", "ing"], description="description"
    ) == ["x", "y", "z"]
    assert envs.get_list_literal(
        name="LIST_OF_INT", default=["noth", "ing"], description="description"
    ) == [3, 4, 5]

    for key, value in FAKE_ENVIRONS.items():
        if key not in ("LIST_OF_STR", "LIST_OF_INT"):
            with pytest.raises(envs.EnvironmentVariableParseException) as ex:
                envs.get_list_literal(
                    name=key, default=["noth", "ing"], description="description"
                )
            assert ex.value.args[
                0
            ] == "Expected value in {key}={value} to be a list literal".format(
                key=key, value=value
            )

    assert envs.get_list_literal(
        name="missing_list", default=["default"], description="description"
    ) == ["default"]


def test_list_environment_vars():
    """Verify that list_environment_vars returns a list of parsed values"""
    envs.get_bool(name="TRUE", default=True, description="description")
    envs.get_int(name="ZERO", default=True, description="description")
    envs.get_list_literal(
        name="LIST_OF_STR", default=["1", "2", "3"], description="description"
    )

    assert [var.value for var in envs.list_environment_vars()] == [
        True,
        0,
        ["x", "y", "z"],
    ]


def test_validate():
    """Verify that validate raises an error if a variable was required but absent"""
    envs.get_bool(name="TRUE", description="description", required=True)
    envs.get_int(name="ZERO", description="description", required=True)
    envs.get_list_literal(name="LIST_OF_STR", description="description", required=True)
    envs.validate()  # no exception

    envs.get_string(name="missing", description="description", required=True)
    with pytest.raises(ImproperlyConfigured):
        envs.validate()


def test_duplicate_vars():
    """Verify that trying to parse an environment variable more than once fails"""
    envs.get_bool(name="TRUE", default=True, description="description")
    with pytest.raises(ValueError):
        assert envs.get_bool(name="TRUE", default=True, description="description")


def test_generate_app_json(mocker):
    """Verify that generate_app_json() returns an app.json data structure"""
    base = {
        "description": "base json",
        "env": {"NOT_IN_SETTINGS_PY": {"value": True}, "TRUE": {"key": "value"}},
    }
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(base)))
    envs.get_bool(name="TRUE", description="TRUE description")
    envs.get_bool(name="FALSE", description="ZERO description", dev_only=True)
    envs.get_int(name="ZERO", description="ZERO description", write_app_json=False)
    envs.get_list_literal(
        name="LIST_OF_STR", description="LIST_OF_STR description", required=True
    )

    assert envs.generate_app_json() == {
        "description": "base json",
        "env": {
            "NOT_IN_SETTINGS_PY": {"value": True},
            "TRUE": {
                "description": "TRUE description",
                "required": False,
                "key": "value",
            },
            "LIST_OF_STR": {
                "description": "LIST_OF_STR description",
                "required": True,
            },
        },
    }


def test_get_features(mocker):
    """Verify that get_features() parses dict of feature flags"""
    mocker.patch.dict(
        "os.environ",
        {"FEATURE_ABC": "True", "FEATURE_DEF": "False", "FLAG_GHI": "False"},
        clear=True,
    )
    envs.env.reload()
    assert envs.get_features() == {"ABC": True, "DEF": False}
    assert envs.get_features("FLAG_") == {"GHI": False}


def test_app_namespace():
    """Verify that app_namespaced namespaces an environment variable"""
    with pytest.raises(ImproperlyConfigured):
        envs.app_namespaced("KEY")

    envs.init_app_settings(namespace="PREFIX", site_name="Site Name")
    envs.validate()

    assert envs.app_namespaced("KEY") == "PREFIX_KEY"


def test_get_site_name():
    """Verify that get_site_name returns the site name"""
    with pytest.raises(ImproperlyConfigured):
        envs.get_site_name()

    envs.init_app_settings(namespace="PREFIX", site_name="Site Name")
    envs.validate()

    assert envs.get_site_name() == "Site Name"
