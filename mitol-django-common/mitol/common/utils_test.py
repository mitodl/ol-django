"""Utils tests"""
import datetime
import operator as op
from decimal import Decimal
from http import HTTPStatus
from types import SimpleNamespace

import pytest
import pytz

from mitol.common.test_utils import MockResponse
from mitol.common.utils import (
    all_equal,
    all_unique,
    dict_without_keys,
    filter_dict_by_key_set,
    find_object_with_matching_attr,
    first_matching_item,
    first_or_none,
    format_price,
    get_error_response_summary,
    group_into_dict,
    has_all_keys,
    has_equal_properties,
    is_json_response,
    is_near_now,
    item_at_index_or_blank,
    item_at_index_or_none,
    max_or_none,
    now_in_utc,
    partition,
    partition_to_lists,
    remove_password_from_url,
    request_get_with_timeout_retry,
    unique,
    unique_ignore_case,
)


def test_now_in_utc():
    """now_in_utc() should return the current time set to the UTC time zone"""
    now = now_in_utc()
    assert is_near_now(now)
    assert now.tzinfo == pytz.UTC


def test_is_near_now():
    """
    Test is_near_now for now
    """
    now = datetime.datetime.now(tz=pytz.UTC)
    assert is_near_now(now) is True
    later = now + datetime.timedelta(0, 6)
    assert is_near_now(later) is False
    earlier = now - datetime.timedelta(0, 6)
    assert is_near_now(earlier) is False


def test_dict_without_keys():
    """
    Test that dict_without_keys returns a dict with keys omitted
    """
    d = {"a": 1, "b": 2, "c": 3}
    assert dict_without_keys(d, "a") == {"b": 2, "c": 3}
    assert dict_without_keys(d, "a", "b") == {"c": 3}
    assert dict_without_keys(d, "doesnt_exist") == d


def test_filter_dict_by_key_set():
    """
    Test that filter_dict_by_key_set returns a dict with only the given keys
    """
    d = {"a": 1, "b": 2, "c": 3, "d": 4}
    assert filter_dict_by_key_set(d, {"a", "c"}) == {"a": 1, "c": 3}
    assert filter_dict_by_key_set(d, {"a", "c", "nonsense"}) == {"a": 1, "c": 3}
    assert filter_dict_by_key_set(d, {"nonsense"}) == {}


def test_has_equal_properties():
    """
    Assert that has_equal_properties returns True if an object has equivalent properties to a given dict
    """
    obj = SimpleNamespace(a=1, b=2, c=3)
    assert has_equal_properties(obj, {}) is True
    assert has_equal_properties(obj, dict(a=1, b=2)) is True
    assert has_equal_properties(obj, dict(a=1, b=2, c=3)) is True
    assert has_equal_properties(obj, dict(a=2)) is False
    assert has_equal_properties(obj, dict(d=4)) is False


def test_find_object_with_matching_attr():
    """
    Assert that find_object_with_matching_attr returns the first object in an iterable that has the given
    attribute value (or None if there is no match)
    """
    objects = [
        SimpleNamespace(a=0),
        SimpleNamespace(a=1),
        SimpleNamespace(a=2),
        SimpleNamespace(a=3),
        SimpleNamespace(a=None),
    ]
    assert find_object_with_matching_attr(objects, "a", 3) == objects[3]
    assert find_object_with_matching_attr(objects, "a", None) == objects[4]
    assert find_object_with_matching_attr(objects, "a", "bad value") is None
    assert find_object_with_matching_attr(objects, "b", None) is None


def test_partition():
    """
    Assert that partition splits an iterable into two iterables according to a condition
    """
    nums = [1, 2, 1, 3, 1, 4, 0, None, None]
    not_ones, ones = partition(nums, lambda n: n == 1)
    assert list(not_ones) == [2, 3, 4, 0, None, None]
    assert list(ones) == [1, 1, 1]
    # The default predicate is the standard Python bool() function
    falsey, truthy = partition(nums)
    assert list(falsey) == [0, None, None]
    assert list(truthy) == [1, 2, 1, 3, 1, 4]


def test_partition_to_lists():
    """
    Assert that partition_to_lists splits an iterable into two lists according to a condition
    """
    nums = [1, 2, 1, 3, 1, 4, 0, None, None]
    not_ones, ones = partition_to_lists(nums, lambda n: n == 1)
    assert not_ones == [2, 3, 4, 0, None, None]
    assert ones == [1, 1, 1]
    # The default predicate is the standard Python bool() function
    falsey, truthy = partition_to_lists(nums)
    assert falsey == [0, None, None]
    assert truthy == [1, 2, 1, 3, 1, 4]


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


def test_first_or_none():
    """
    Assert that first_or_none returns the first item in an iterable or None
    """
    assert first_or_none([]) is None
    assert first_or_none(set()) is None
    assert first_or_none([1, 2, 3]) == 1
    assert first_or_none(range(1, 5)) == 1


def test_first_matching_item():
    """
    Assert that first_matching_item returns the first item that matches the predicate
    """
    assert first_matching_item(range(10), lambda i: i > 5) == 6


def test_max_or_none():
    """
    Assert that max_or_none returns the max of some iterable, or None if the iterable has no items
    """
    assert max_or_none(i for i in [5, 4, 3, 2, 1]) == 5
    assert max_or_none([1, 3, 5, 4, 2]) == 5
    assert max_or_none([]) is None


def test_unique():
    """
    Assert that unique() returns a generator of unique elements from a provided iterable
    """
    assert list(unique([1, 2, 2, 3, 3, 0, 3])) == [1, 2, 3, 0]
    assert list(unique(("a", "b", "a", "c", "C", None))) == ["a", "b", "c", "C", None]


def test_unique_ignore_case():
    """
    Assert that unique_ignore_case() returns a generator of unique lowercase strings from a
    provided iterable
    """
    assert list(unique_ignore_case(["ABC", "def", "AbC", "DEf"])) == ["abc", "def"]


def test_item_at_index_or_none():
    """
    Assert that item_at_index_or_none returns an item at a given index, or None if that index
    doesn't exist
    """
    arr = [1, 2, 3]
    assert item_at_index_or_none(arr, 1) == 2
    assert item_at_index_or_none(arr, 10) is None


def test_item_at_index_or_blank():
    """
    Assert that item_at_index_or_blank returns an item at a given index, or a blank string if that index
    doesn't exist
    """
    arr = ["string 1", "string 2"]
    assert item_at_index_or_blank(arr, 0) == "string 1"
    assert item_at_index_or_blank(arr, 1) == "string 2"
    assert item_at_index_or_blank(arr, 10) == ""


def test_all_equal():
    """
    Assert that all_equal returns True if all of the provided args are equal to each other
    """
    assert all_equal(1, 1, 1) is True
    assert all_equal(1, 2, 1) is False
    assert all_equal() is True


def test_all_unique():
    """
    Assert that all_unique returns True if all of the items in the iterable argument are unique
    """
    assert all_unique([1, 2, 3, 4]) is True
    assert all_unique((1, 2, 3, 4)) is True
    assert all_unique([1, 2, 3, 1]) is False


def test_has_all_keys():
    """
    Assert that has_all_keys returns True if the given dict has all of the specified keys
    """
    d = {"a": 1, "b": 2, "c": 3}
    assert has_all_keys(d, ["a", "c"]) is True
    assert has_all_keys(d, ["a", "z"]) is False


def test_group_into_dict():
    """
    Assert that group_into_dict takes an iterable of items and returns a dictionary of those items
    grouped by generated keys
    """

    class Car:  # pylint: disable=missing-docstring
        def __init__(self, make, model):
            self.make = make
            self.model = model

    cars = [
        Car(make="Honda", model="Civic"),
        Car(make="Honda", model="Accord"),
        Car(make="Ford", model="F150"),
        Car(make="Ford", model="Focus"),
        Car(make="Jeep", model="Wrangler"),
    ]
    grouped_cars = group_into_dict(cars, key_fn=op.attrgetter("make"))
    assert set(grouped_cars.keys()) == {"Honda", "Ford", "Jeep"}
    assert set(grouped_cars["Honda"]) == set(cars[0:2])
    assert set(grouped_cars["Ford"]) == set(cars[2:4])
    assert grouped_cars["Jeep"] == [cars[4]]

    nums = [1, 2, 3, 4, 5, 6]
    grouped_nums = group_into_dict(nums, key_fn=lambda num: (num % 2 == 0))
    assert grouped_nums.keys() == {True, False}
    assert set(grouped_nums[True]) == {2, 4, 6}
    assert set(grouped_nums[False]) == {1, 3, 5}


@pytest.mark.parametrize(
    "price,expected",
    [[Decimal("0"), "$0.00"], [Decimal("1234567.89"), "$1,234,567.89"]],
)
def test_format_price(price, expected):
    """Format a decimal value into a price"""
    assert format_price(price) == expected


@pytest.mark.parametrize(
    "content,content_type,exp_summary_content,exp_url_in_summary",
    [
        ['{"bad": "response"}', "application/json", '{"bad": "response"}', False],
        ["plain text", "text/plain", "plain text", False],
        [
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
    """
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
    "content,content_type,expected",
    [
        ['{"bad": "response"}', "application/json", True],
        ["plain text", "text/plain", False],
        ["<div>HTML content</div>", "text/html; charset=utf-8", False],
    ],
)
def test_is_json_response(content, content_type, expected):
    """
    is_json_response should return True if the given response's content type indicates JSON content
    """
    mock_response = MockResponse(
        status_code=400, content=content, content_type=content_type
    )
    assert is_json_response(mock_response) is expected


def test_request_get_with_timeout_retry(mocker):
    """request_get_with_timeout_retry should make a GET request and retry if the response status is 504 (timeout)"""
    mock_response = mocker.Mock(status_code=HTTPStatus.GATEWAY_TIMEOUT)
    patched_request_get = mocker.patch(
        "mitol.common.utils.requests.get", return_value=mock_response
    )
    patched_log = mocker.patch("mitol.common.utils.log")
    url = "http://example.com/retry"
    retries = 4

    result = request_get_with_timeout_retry(url, retries=retries)
    assert patched_request_get.call_count == retries
    assert patched_log.warning.call_count == (retries - 1)
    mock_response.raise_for_status.assert_called_once()
    assert result == mock_response
