"""Tests for test utils"""

import json

import pytest
from mitol.common.pytest_utils import MockResponse, any_instance_of, assert_not_raises
from mitol.common.pytest_utils import test_app_json_modified as _test_app_json_modified


def test_any_instance_of():
    """Tests any_instance_of()"""
    any_number = any_instance_of(int, float)

    assert any_number == 0.405
    assert any_number == 8_675_309
    assert any_number != "not a number"
    assert any_number != {}
    assert any_number != []


def test_assert_not_raises_none():
    """
    assert_not_raises should do nothing if no exception is raised
    """
    with assert_not_raises():
        pass


def test_assert_not_raises_exception(mocker):
    """assert_not_raises should fail the test"""
    # Here there be dragons
    fail_mock = mocker.patch("pytest.fail", autospec=True)
    with assert_not_raises():
        raise TabError
    assert fail_mock.called is True


def test_assert_not_raises_failure():
    """assert_not_raises should reraise an AssertionError"""
    with pytest.raises(AssertionError):
        with assert_not_raises():
            assert 1 == 2


@pytest.mark.parametrize(
    "content,expected_content,expected_json",
    [
        ['{"test": "content"}', '{"test": "content"}', {"test": "content"}],
        [{"test": "content"}, '{"test": "content"}', {"test": "content"}],
        [["test", "content"], '["test", "content"]', ["test", "content"]],
        [123, "123", 123],
    ],
)
def test_mock_response(content, expected_content, expected_json):
    """Assert MockResponse returns correct values"""
    response = MockResponse(content, 404)
    assert response.status_code == 404
    assert response.content == expected_content
    assert response.json() == expected_json


def test_test_app_json_modified_passes(mocker):
    """
    This is a test for a function that itself is a pytest test,
    usually imported into projects for reuse.
    """
    data = dict(a=1243)

    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(data)))
    mocker.patch("mitol.common.envs.generate_app_json", return_value=data)

    _test_app_json_modified()


def test_test_app_json_modified_fails(mocker):
    """
    This is a test for a function that itself is a pytest test,
    usually imported into projects for reuse.
    """
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(dict(a=1))))
    mocker.patch("mitol.common.envs.generate_app_json", return_value=dict(a=1243))

    with pytest.raises(AssertionError):
        _test_app_json_modified()
