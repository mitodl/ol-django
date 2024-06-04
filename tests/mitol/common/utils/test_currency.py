"""Utils tests"""

from decimal import Decimal

import pytest
from mitol.common.utils.currency import format_price


@pytest.mark.parametrize(
    "price,expected",  # noqa: PT006
    [[Decimal("0"), "$0.00"], [Decimal("1234567.89"), "$1,234,567.89"]],  # noqa: PT007
)
def test_format_price(price, expected):
    """Format a decimal value into a price"""
    assert format_price(price) == expected
