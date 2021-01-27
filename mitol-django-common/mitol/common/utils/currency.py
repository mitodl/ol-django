"""Currency utilities"""
from decimal import Decimal


def format_price(amount: Decimal) -> str:
    """
    Format a price in USD

    Args:
        amount (decimal.Decimal): A decimal value

    Returns:
        str: A currency string
    """
    return f"${amount:0,.2f}"
