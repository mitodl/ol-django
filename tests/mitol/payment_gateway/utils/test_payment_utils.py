"""Tests for payment_gateway application utils"""  # noqa: INP001

from decimal import Decimal

import pytest
from mitol.payment_gateway.payment_utils import (
    clean_request_data,
    quantize_decimal,
    strip_nones,
)


@pytest.mark.parametrize(
    "request_data_dict, expected_data_dict",  # noqa: PT006
    [
        ({"key1": 1, "key2": 2, "key3": None}, {"key1": 1, "key2": 2}),
        ({"key1": "val1", "key2": None, "key3": 1}, {"key1": "val1", "key3": 1}),
        ({"key1": "val1", "key2": None, "key3": None}, {"key1": "val1"}),
        ({"key1": None, "key2": None, "key3": None}, {}),
    ],
)
def test_clean_data(request_data_dict, expected_data_dict):
    """Test that clean_request_data cleans the requests data payload dictionary and returns it without None Values"""  # noqa: E501

    cleaned_data_dict = clean_request_data(request_data_dict)
    # Just sanity check
    assert None not in cleaned_data_dict.values()
    assert cleaned_data_dict == expected_data_dict


def test_strip_nones():
    """Tests strip_nones to make sure items that are None are stripped, and that colllections with no blank spaces are left alone."""  # noqa: E501

    ds1 = {
        "keyA": "test",
        "keyB": None,
        "keyC": "test",
    }

    ds2 = {
        "keyA": "test",
        "keyB": "test",
        "keyC": "test",
    }

    test_ds1 = strip_nones(ds1)

    assert "keyB" not in test_ds1

    test_ds2 = strip_nones(ds2)

    assert test_ds2 == ds2


def test_quantize_decimal():
    """
    Tests quantize_decimal to make sure that the decimal is quantized to
    the correct precision.
    """

    test_decimal = 1.23456789
    test_precision = 2

    quantized_decimal = quantize_decimal(test_decimal, test_precision)

    assert quantized_decimal == Decimal("1.23")
