"""Utils tests"""
import operator as op
from math import ceil
from types import SimpleNamespace

import pytest

from mitol.common.utils.collections import (
    all_equal,
    all_unique,
    chunks,
    dict_without_keys,
    filter_dict_by_key_set,
    find_object_with_matching_attr,
    first_matching_item,
    first_or_none,
    group_into_dict,
    has_all_keys,
    has_equal_properties,
    item_at_index_or_blank,
    item_at_index_or_none,
    matching_item_index,
    max_or_none,
    partition,
    partition_to_lists,
    replace_null_values,
    unique,
    unique_ignore_case,
)


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

    class Car:
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


def test_chunks():
    """
    test for chunks
    """
    input_list = list(range(113))
    output_list = []
    for nums in chunks(input_list):
        output_list += nums
    assert output_list == input_list

    output_list = []
    for nums in chunks(input_list, chunk_size=1):
        output_list += nums
    assert output_list == input_list

    output_list = []
    for nums in chunks(input_list, chunk_size=124):
        output_list += nums
    assert output_list == input_list


def test_chunks_iterable():
    """
    test that chunks works on non-list iterables too
    """
    count = 113
    input_range = range(count)
    chunk_output = []
    for chunk in chunks(input_range, chunk_size=10):
        chunk_output.append(chunk)
    assert len(chunk_output) == ceil(113 / 10)

    range_list = []
    for chunk in chunk_output:
        range_list += chunk
    assert range_list == list(range(count))


def test_matching_item_index():
    """matching_item_index should return the index of an item equal to the given value, or raises an exception"""
    assert matching_item_index(["a", "b", "c", "d"], "b") == 1
    with pytest.raises(StopIteration):
        matching_item_index(["a", "b", "c", "d"], "e")
    number_iter = (i for i in [0, 1, 2, 3, 4])
    assert matching_item_index(number_iter, 2) == 2


def test_replace_null_values():
    """Invalid values should be replaced"""
    assert replace_null_values({"a": 1, "b": None, "c": "N/A"}, "nodata") == {
        "a": 1,
        "b": "nodata",
        "c": "N/A",
    }
    assert replace_null_values([1, None, "N/A"], "") == [1, "", "N/A"]
    assert replace_null_values([1, None, "N/A"], 0) == [1, 0, "N/A"]
