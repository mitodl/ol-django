"""Tests for payment_gateway application utils"""

import pytest

from mitol.payment_gateway.payment_utils import clean_request_data


@pytest.mark.parametrize(
    "request_data_dict, expected_data_dict",
    [
        ({"key1": 1, "key2": 2, "key3": None}, {"key1": 1, "key2": 2}),
        ({"key1": "val1", "key2": None, "key3": 1}, {"key1": "val1", "key3": 1}),
        ({"key1": "val1", "key2": None, "key3": None}, {"key1": "val1"}),
        ({"key1": None, "key2": None, "key3": None}, {}),
    ],
)
def test_clean_data(request_data_dict, expected_data_dict):
    """Test that clean_request_data cleans the requests data payload dictionary and returns it without None Values"""

    cleaned_data_dict = clean_request_data(request_data_dict)
    # Just sanity check
    assert None not in cleaned_data_dict.values()
    assert cleaned_data_dict == expected_data_dict
